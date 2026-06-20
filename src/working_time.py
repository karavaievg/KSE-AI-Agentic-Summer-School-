"""Step 6 - overlap of alert intervals with the user's working schedule.

We work in local wall-clock time here. The UTC->Kyiv conversion already
happened in preprocessing, and Ukraine's summer/winter clock changes occur at
night (around 03:00-04:00), outside normal daytime working hours, so they do
not affect the working-window overlap. This keeps the logic simple and
correct for this tool.

Weekday convention: Monday=0 ... Sunday=6 (Python's datetime.weekday()).
Assumption: the working window is a single daytime block with
work_start < work_end (overnight shifts are out of scope).
"""
from __future__ import annotations

from datetime import time

import numpy as np
import pandas as pd


def _minutes(t: time) -> int:
    """Minutes since local midnight for a time, e.g. 08:30 -> 510."""
    return t.hour * 60 + t.minute


def clip_intervals_to_range(
    intervals: pd.DataFrame,
    range_start: pd.Timestamp,
    range_end: pd.Timestamp,
) -> pd.DataFrame:
    """Keep only the parts of intervals that fall inside [range_start, range_end].

    Intervals fully outside the range are dropped; partially overlapping ones
    are trimmed to the range boundaries. This makes sure working-time hours can
    never exceed the nominal hours of the selected period.

    range_start / range_end must carry the same timezone as the intervals.
    """
    cols = ["oblast", "started_at", "finished_at"]
    if intervals.empty:
        return intervals[cols].copy()

    iv = intervals[cols].copy()
    # Drop intervals entirely outside the window.
    iv = iv[(iv["finished_at"] > range_start) & (iv["started_at"] < range_end)]
    if iv.empty:
        return iv

    # Trim the edges to the window.
    iv["started_at"] = iv["started_at"].clip(lower=range_start)
    iv["finished_at"] = iv["finished_at"].clip(upper=range_end)
    return iv.reset_index(drop=True)


def working_time_overlap(
    intervals: pd.DataFrame,
    working_days: list[int],
    work_start: time,
    work_end: time,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """How many alert hours fall inside the working schedule, per oblast.

    Parameters
    ----------
    intervals:
        Merged alert intervals with oblast, started_at, finished_at (Kyiv tz).
    working_days:
        Working weekdays, e.g. [0, 1, 2, 3, 4] for Monday-Friday.
    work_start, work_end:
        Daily working window, e.g. time(8, 0) and time(18, 0).

    Returns
    -------
    (per_oblast, per_oblast_month)
        per_oblast: oblast, working_alert_hours
        per_oblast_month: oblast, month (YYYY-MM), working_alert_hours
    """
    empty_total = pd.DataFrame(columns=["oblast", "working_alert_hours"])
    empty_month = pd.DataFrame(columns=["oblast", "month", "working_alert_hours"])
    if intervals.empty:
        return empty_total, empty_month

    iv = intervals[["oblast", "started_at", "finished_at"]].copy()

    # Switch to naive local wall-clock time (see module docstring).
    start = iv["started_at"].dt.tz_localize(None)
    end = iv["finished_at"].dt.tz_localize(None)
    oblast = iv["oblast"].to_numpy()

    start_np = start.to_numpy()  # datetime64[ns]
    end_np = end.to_numpy()
    start_day = start.dt.normalize().to_numpy()  # local midnight of each start

    # Number of calendar days each interval touches.
    n_days = ((end.dt.normalize() - start.dt.normalize()).dt.days + 1).to_numpy()

    # Vectorised "explode": repeat each interval n_days times and build, for
    # each copy, the specific day it represents (start_day + 0, +1, +2, ...).
    total = int(n_days.sum())
    rep_idx = np.repeat(np.arange(len(iv)), n_days)
    group_start = np.repeat(np.cumsum(n_days) - n_days, n_days)
    day_offset = (np.arange(total) - group_start).astype("timedelta64[D]")
    day = start_day[rep_idx] + day_offset  # datetime64[ns], local midnight per day

    # Working window bounds for each day.
    win_start = day + np.timedelta64(_minutes(work_start), "m")
    win_end = day + np.timedelta64(_minutes(work_end), "m")

    # Overlap of [start, end] with the day's working window, in hours.
    lo = np.maximum(start_np[rep_idx], win_start)
    hi = np.minimum(end_np[rep_idx], win_end)
    overlap_h = np.clip((hi - lo) / np.timedelta64(1, "h"), 0.0, None)

    # Keep only working weekdays. numpy epoch (1970-01-01) is a Thursday, so
    # (days_since_epoch + 3) % 7 gives Monday=0 .. Sunday=6.
    weekday = (day.astype("datetime64[D]").astype("int64") + 3) % 7
    is_working = np.isin(weekday, working_days)
    overlap_h = np.where(is_working, overlap_h, 0.0)

    out = pd.DataFrame(
        {
            "oblast": oblast[rep_idx],
            "month": day.astype("datetime64[M]").astype(str),
            "working_alert_hours": overlap_h,
        }
    )

    per_oblast = out.groupby("oblast", as_index=False)["working_alert_hours"].sum()
    per_oblast_month = (
        out.groupby(["oblast", "month"], as_index=False)["working_alert_hours"].sum()
    )
    return per_oblast, per_oblast_month


def nominal_working_hours(
    range_start: pd.Timestamp,
    range_end: pd.Timestamp,
    working_days: list[int],
    work_start: time,
    work_end: time,
) -> float:
    """Total scheduled working hours in the period (how many hours *should*
    have been worked), used as the denominator for availability and the
    downtime index.
    """
    hours_per_day = (_minutes(work_end) - _minutes(work_start)) / 60.0
    if hours_per_day <= 0:
        return 0.0

    # Count working days by calendar date (inclusive of both endpoints' dates).
    days = pd.date_range(range_start.normalize(), range_end.normalize(), freq="D")
    n_working = int(pd.Series(days.weekday).isin(working_days).sum())
    return n_working * hours_per_day
