"""Step 9 - the four dashboard charts, themed per the style guide.

All charts use a transparent background (so the dark card shows through), a 2px
visual weight, faint gridlines, and rounded tooltips with tabular numbers.
Accent blue is the main-metric color; red/green are not used as categorical
colors. Availability is colored on a status scale (green / amber / red), which
the style guide allows for status and risk.
"""
from __future__ import annotations

import plotly.graph_objects as go

from .theme import COLORS, SERIES_PALETTE, fmt_hours, fmt_money_full, fmt_pct, style_fig


def _availability_color(ratio: float) -> str:
    if ratio != ratio:  # NaN
        return COLORS["text_tertiary"]
    if ratio >= 0.9:
        return COLORS["positive"]
    if ratio >= 0.7:
        return COLORS["warning"]
    return COLORS["negative"]


def bar_working_hours(metrics) -> go.Figure:
    """Working-time alert hours by region (the core downtime measure)."""
    df = metrics.sort_values("working_time_alert_hours", ascending=True)
    fig = go.Figure(
        go.Bar(
            x=df["working_time_alert_hours"],
            y=df["oblast"],
            orientation="h",
            marker_color=COLORS["accent"],
            customdata=[fmt_hours(v) for v in df["working_time_alert_hours"]],
            hovertemplate="%{y}<br>%{customdata} год<extra></extra>",
        )
    )
    return style_fig(fig, height=max(260, 36 * len(df) + 60))


def bar_cost(metrics) -> go.Figure:
    """Estimated downtime cost by region."""
    df = metrics.sort_values("total_downtime_cost", ascending=True)
    fig = go.Figure(
        go.Bar(
            x=df["total_downtime_cost"],
            y=df["oblast"],
            orientation="h",
            marker_color=COLORS["cyan"],
            customdata=[fmt_money_full(v) for v in df["total_downtime_cost"]],
            hovertemplate="%{y}<br>%{customdata}<extra></extra>",
        )
    )
    return style_fig(fig, height=max(260, 36 * len(df) + 60))


def bar_availability(metrics) -> go.Figure:
    """Production availability ratio by region, colored on a status scale."""
    df = metrics.sort_values("availability_ratio", ascending=True)
    colors = [_availability_color(v) for v in df["availability_ratio"]]
    fig = go.Figure(
        go.Bar(
            x=df["availability_ratio"],
            y=df["oblast"],
            orientation="h",
            marker_color=colors,
            customdata=[fmt_pct(v) for v in df["availability_ratio"]],
            hovertemplate="%{y}<br>Доступність %{customdata}<extra></extra>",
        )
    )
    fig = style_fig(fig, height=max(260, 36 * len(df) + 60))
    fig.update_xaxes(range=[0, 1], tickformat=".0%")
    return fig


def line_monthly(monthly) -> go.Figure:
    """Monthly working-time alert hours, one line per region."""
    fig = go.Figure()
    if not monthly.empty:
        regions = list(monthly["oblast"].unique())
        for i, region in enumerate(regions):
            sub = monthly[monthly["oblast"] == region].sort_values("month")
            color = SERIES_PALETTE[i % len(SERIES_PALETTE)]
            fig.add_trace(
                go.Scatter(
                    x=sub["month"],
                    y=sub["working_alert_hours"],
                    mode="lines+markers",
                    name=region,
                    line=dict(color=color, width=2),
                    marker=dict(size=5, color=color),
                    customdata=[fmt_hours(v) for v in sub["working_alert_hours"]],
                    hovertemplate=f"{region}<br>%{{x}}<br>%{{customdata}} год<extra></extra>",
                )
            )
    fig = style_fig(fig, height=340)
    fig.update_layout(showlegend=True)
    return fig
