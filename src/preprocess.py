"""Steps 2-5 - clean the raw alerts and turn them into merged, oblast-level
alert intervals in Kyiv local time.

Pipeline:
    parse timestamps as UTC  ->  convert to Kyiv time  ->  drop anomalies
    (>24h alerts, Decision 1)  ->  merge overlapping intervals per oblast
    (Decision 2, to avoid double-counting).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# Ukraine local timezone. Using the IANA name lets Python handle summer/winter
# time automatically, so we never add hours by hand.
KYIV_TZ = "Europe/Kyiv"

# Any single alert longer than this is treated as a data error (a "stuck"
# siren record) and removed. Agreed with the user as Decision 1.
MAX_ALERT_HOURS = 24.0


@dataclass
class PreprocessResult:
    """Cleaned intervals plus a few diagnostics for transparency."""

    intervals: pd.DataFrame  # columns: oblast, started_at, finished_at (Kyiv tz)
    n_raw: int  # raw records read from the file
    n_after_anomaly: int  # records remaining after dropping >24h alerts
    n_anomalies_removed: int  # how many >24h alerts were removed
    n_intervals: int  # number of merged intervals produced


def _parse_times_utc(df: pd.DataFrame) -> pd.DataFrame:
    """Parse the text timestamps into real UTC datetimes."""
    df = df.copy()
    df["started_at"] = pd.to_datetime(df["started_at"], utc=True, errors="coerce")
    df["finished_at"] = pd.to_datetime(df["finished_at"], utc=True, errors="coerce")
    # Drop rows where a timestamp could not be parsed (defensive; the official
    # file currently has none).
    df = df.dropna(subset=["started_at", "finished_at"])
    return df


def _to_kyiv(df: pd.DataFrame) -> pd.DataFrame:
    """Convert UTC datetimes to Kyiv local time (DST-aware)."""
    df = df.copy()
    df["started_at"] = df["started_at"].dt.tz_convert(KYIV_TZ)
    df["finished_at"] = df["finished_at"].dt.tz_convert(KYIV_TZ)
    return df


def _drop_anomalies(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Remove alerts that are negative-length or longer than MAX_ALERT_HOURS."""
    duration_h = (df["finished_at"] - df["started_at"]).dt.total_seconds() / 3600.0
    keep = (duration_h >= 0) & (duration_h <= MAX_ALERT_HOURS)
    removed = int((~keep).sum())
    return df[keep].copy(), removed


def _merge_intervals(df: pd.DataFrame) -> pd.DataFrame:
    """Merge overlapping or touching intervals within each oblast.

    Why: from late 2025 most alerts are recorded at raion/hromada level, so a
    single oblast can have several simultaneous records. Adding their
    durations would double-count downtime. We instead merge them into single
    coverage intervals: if Kharkiv oblast is covered 14:00-15:00 (one raion)
    and 14:30-16:00 (another), that is one interval 14:00-16:00 for the oblast.

    Implementation: a vectorised sweep. Sort by (oblast, start); a new merged
    interval begins whenever a record starts after the running maximum end
    seen so far within the same oblast.
    """
    cols = ["oblast", "started_at", "finished_at"]
    if df.empty:
        return df[cols].copy()

    df = df.sort_values(["oblast", "started_at"]).copy()

    # Running max end time within each oblast, then look at the previous row.
    prev_end = df.groupby("oblast")["finished_at"].cummax().shift()
    same_oblast = df["oblast"].eq(df["oblast"].shift())

    # Start a new interval group when the oblast changes, or when this record
    # begins after the coverage so far ends (i.e. there is a real gap).
    new_group = (~same_oblast) | (df["started_at"] > prev_end)
    df["_group_id"] = new_group.cumsum()

    merged = (
        df.groupby(["oblast", "_group_id"], as_index=False)
        .agg(started_at=("started_at", "min"), finished_at=("finished_at", "max"))
        .drop(columns="_group_id")
    )
    return merged[cols]


def preprocess_alerts(raw: pd.DataFrame) -> PreprocessResult:
    """Run the full cleaning pipeline on a raw alerts DataFrame."""
    n_raw = len(raw)

    df = _parse_times_utc(raw)
    df = _to_kyiv(df)
    df, removed = _drop_anomalies(df)
    n_after = len(df)

    merged = _merge_intervals(df).reset_index(drop=True)

    return PreprocessResult(
        intervals=merged,
        n_raw=n_raw,
        n_after_anomaly=n_after,
        n_anomalies_removed=removed,
        n_intervals=len(merged),
    )
