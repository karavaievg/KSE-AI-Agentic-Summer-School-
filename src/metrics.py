"""Step 7 - business metrics per oblast.

Turns alert hours into the numbers a business cares about. All formulas follow
the project spec:

    lost_labor_hours   = working_time_alert_hours * workers * downtime_factor
    lost_labor_cost    = lost_labor_hours * hourly_labor_cost
    machine_idle_cost  = working_time_alert_hours * machine_idle_cost_per_hour
    total_downtime_cost= lost_labor_cost + machine_idle_cost
    availability_ratio = 1 - working_time_alert_hours / nominal_working_hours
    downtime_index     = working_time_alert_hours / nominal_working_hours * 1000
                         (working-time alert hours per 1,000 scheduled hours)

The machine idle cost is multiplied by hours only (not by worker count),
because a machine sits idle for the duration of the stoppage regardless of how
many people would have operated it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time

import numpy as np
import pandas as pd

from .working_time import nominal_working_hours, working_time_overlap

# Final column order for the comparison table.
METRIC_COLUMNS = [
    "oblast",
    "total_alert_hours",
    "working_time_alert_hours",
    "nominal_working_hours",
    "lost_labor_hours",
    "lost_labor_cost",
    "machine_idle_cost",
    "total_downtime_cost",
    "availability_ratio",
    "downtime_index",
]


def total_alert_hours_by_oblast(intervals: pd.DataFrame) -> pd.DataFrame:
    """Total alert duration per oblast (24/7, the whole merged coverage)."""
    if intervals.empty:
        return pd.DataFrame(columns=["oblast", "total_alert_hours"])
    iv = intervals.copy()
    hours = (iv["finished_at"] - iv["started_at"]).dt.total_seconds() / 3600.0
    iv = iv.assign(total_alert_hours=hours)
    return iv.groupby("oblast", as_index=False)["total_alert_hours"].sum()


def compute_metrics(
    intervals: pd.DataFrame,
    range_start: pd.Timestamp,
    range_end: pd.Timestamp,
    working_days: list[int],
    work_start: time,
    work_end: time,
    n_workers: int,
    hourly_labor_cost: float,
    downtime_factor: float = 1.0,
    machine_idle_cost_per_hour: float = 0.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build the per-oblast metrics table and the monthly breakdown.

    `intervals` should already be filtered to the selected regions and clipped
    to the selected date range.

    Returns
    -------
    (metrics, monthly)
        metrics: one row per oblast with all columns in METRIC_COLUMNS.
        monthly: oblast, month, working_alert_hours (for the line chart).
    """
    empty = pd.DataFrame(columns=METRIC_COLUMNS)
    empty_month = pd.DataFrame(columns=["oblast", "month", "working_alert_hours"])
    if intervals.empty:
        return empty, empty_month

    total = total_alert_hours_by_oblast(intervals)
    working, monthly = working_time_overlap(intervals, working_days, work_start, work_end)
    working = working.rename(columns={"working_alert_hours": "working_time_alert_hours"})

    nominal = nominal_working_hours(
        range_start, range_end, working_days, work_start, work_end
    )

    df = total.merge(working, on="oblast", how="outer")
    df[["total_alert_hours", "working_time_alert_hours"]] = df[
        ["total_alert_hours", "working_time_alert_hours"]
    ].fillna(0.0)

    df["nominal_working_hours"] = nominal
    df["lost_labor_hours"] = (
        df["working_time_alert_hours"] * n_workers * downtime_factor
    )
    df["lost_labor_cost"] = df["lost_labor_hours"] * hourly_labor_cost
    df["machine_idle_cost"] = (
        df["working_time_alert_hours"] * machine_idle_cost_per_hour
    )
    df["total_downtime_cost"] = df["lost_labor_cost"] + df["machine_idle_cost"]

    if nominal > 0:
        df["availability_ratio"] = (
            1.0 - df["working_time_alert_hours"] / nominal
        ).clip(lower=0.0, upper=1.0)
        df["downtime_index"] = df["working_time_alert_hours"] / nominal * 1000.0
    else:
        # No scheduled working time in the period: these ratios are undefined.
        df["availability_ratio"] = np.nan
        df["downtime_index"] = np.nan

    df = df[METRIC_COLUMNS].sort_values(
        "working_time_alert_hours", ascending=False
    ).reset_index(drop=True)
    return df, monthly


@dataclass
class BestWorst:
    """Best vs worst region comparison for the summary block."""

    metric: str
    best_oblast: str
    best_value: float
    worst_oblast: str
    worst_value: float
    difference: float
    comparable: bool  # False if fewer than 2 regions


def best_worst_comparison(
    metrics: pd.DataFrame, by: str = "downtime_index"
) -> BestWorst | None:
    """Find the best and worst region by a chosen metric.

    Lower is better for downtime/loss metrics, so best = lowest value.
    """
    if metrics.empty or by not in metrics.columns:
        return None

    valid = metrics.dropna(subset=[by])
    if valid.empty:
        return None

    best_row = valid.loc[valid[by].idxmin()]
    worst_row = valid.loc[valid[by].idxmax()]

    return BestWorst(
        metric=by,
        best_oblast=best_row["oblast"],
        best_value=float(best_row[by]),
        worst_oblast=worst_row["oblast"],
        worst_value=float(worst_row[by]),
        difference=float(worst_row[by] - best_row[by]),
        comparable=len(valid) >= 2,
    )
