"""Air Alert Downtime Index - Streamlit dashboard.

Run locally with:  streamlit run app.py
"""
from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path

import pandas as pd
import streamlit as st

from src.load_data import load_raw_data
from src.metrics import best_worst_comparison, compute_metrics
from src.preprocess import preprocess_alerts
from src.theme import (
    custom_css,
    fmt_delta_pct,
    fmt_hours,
    fmt_index,
    fmt_int,
    fmt_money,
    fmt_money_full,
    fmt_pct,
)
from src.visualization import (
    bar_availability,
    bar_cost,
    bar_working_hours,
    line_monthly,
)
from src.working_time import clip_intervals_to_range

KYIV = "Europe/Kyiv"
DATA_PATH = Path(__file__).parent / "data" / "raw" / "official_data_uk.csv"

DAY_ORDER = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
DAY_TO_INT = {name: i for i, name in enumerate(DAY_ORDER)}

PREFERRED_REGIONS = [
    "м. Київ",
    "Харківська область",
    "Дніпропетровська область",
    "Львівська область",
    "Сумська область",
]

st.set_page_config(
    page_title="Індекс простою від тривог",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(custom_css(), unsafe_allow_html=True)


# --- Data (loaded and preprocessed once, then cached) -----------------------
@st.cache_data(show_spinner="Готуємо дані про тривоги...")
def load_data(path_str: str):
    raw = load_raw_data(path_str)
    res = preprocess_alerts(raw)
    diag = {
        "n_raw": res.n_raw,
        "n_anomalies_removed": res.n_anomalies_removed,
        "n_intervals": res.n_intervals,
    }
    return res.intervals, diag


# --- Small HTML render helpers ----------------------------------------------
def _avail_class(av: float) -> str:
    if av != av:
        return ""
    if av >= 0.9:
        return "good"
    if av >= 0.7:
        return "mid"
    return "bad"


def delta_badge(frac, higher_is_worse: bool = True) -> str:
    """Colored +/- badge vs the previous period. For downtime/cost an increase
    is bad (red); for availability an increase is good (green)."""
    if frac is None:
        return ""
    if abs(frac) < 0.0005:
        return '<span class="badge badge-neutral">0,0%</span>'
    worse = (frac > 0) == higher_is_worse
    cls = "badge-neg" if worse else "badge-pos"
    return f'<span class="badge {cls}">{fmt_delta_pct(frac)}</span>'


def status_badge(av: float) -> str:
    if av != av:
        return ""
    if av >= 0.9:
        return '<span class="badge badge-pos">висока</span>'
    if av >= 0.7:
        return '<span class="badge badge-warn">середня</span>'
    return '<span class="badge badge-neg">низька</span>'


def kpi_card(label, value, foot_html="") -> str:
    return (
        f'<div class="kpi-card"><div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-foot">{foot_html}</div></div>'
    )


def render_table(metrics: pd.DataFrame) -> None:
    headers = [
        ("Область", True), ("Години тривог", False), ("У робочий час", False),
        ("Норма годин", False), ("Втрачені людино-год", False),
        ("Вартість простою", False), ("Доступність", False), ("Індекс простою", False),
    ]
    thead = "".join(
        f'<th class="{"left" if left else ""}">{h}</th>' for h, left in headers
    )
    rows = ""
    for _, r in metrics.iterrows():
        avcls = _avail_class(r.availability_ratio)
        rows += (
            "<tr>"
            f'<td class="left">{r.oblast}</td>'
            f"<td>{fmt_hours(r.total_alert_hours)}</td>"
            f"<td>{fmt_hours(r.working_time_alert_hours)}</td>"
            f"<td>{fmt_hours(r.nominal_working_hours)}</td>"
            f"<td>{fmt_int(r.lost_labor_hours)}</td>"
            f"<td>{fmt_money_full(r.total_downtime_cost)}</td>"
            f'<td class="{avcls}">{fmt_pct(r.availability_ratio)}</td>'
            f"<td>{fmt_index(r.downtime_index)}</td>"
            "</tr>"
        )
    st.markdown(
        f'<div class="cmp-wrap"><table class="cmp"><thead><tr>{thead}</tr>'
        f"</thead><tbody>{rows}</tbody></table></div>",
        unsafe_allow_html=True,
    )


def render_empty() -> None:
    st.markdown(
        '<div class="empty-card"><div class="e-title">Немає даних для цих параметрів</div>'
        '<div class="e-text">Спробуйте розширити період або додати області у лівій панелі.</div></div>',
        unsafe_allow_html=True,
    )


# --- Load data and derive sidebar bounds ------------------------------------
intervals_all, diag = load_data(str(DATA_PATH))
all_regions = sorted(intervals_all["oblast"].unique())
min_date = intervals_all["started_at"].min().date()
max_date = intervals_all["finished_at"].max().date()

default_regions = [r for r in PREFERRED_REGIONS if r in all_regions]
default_from = max(date(2025, 1, 1), min_date)
default_to = min(date(2025, 12, 31), max_date)


# --- Sidebar inputs ---------------------------------------------------------
with st.sidebar:
    st.markdown("## Параметри")
    date_sel = st.date_input(
        "Період", value=(default_from, default_to),
        min_value=min_date, max_value=max_date, format="DD.MM.YYYY",
    )
    selected_regions = st.multiselect("Області", options=all_regions, default=default_regions)

    st.markdown("## Графік роботи")
    selected_days = st.multiselect(
        "Робочі дні", options=DAY_ORDER, default=["Пн", "Вт", "Ср", "Чт", "Пт"]
    )
    col_a, col_b = st.columns(2)
    work_start = col_a.time_input("Початок", value=time(8, 0))
    work_end = col_b.time_input("Кінець", value=time(18, 0))

    st.markdown("## Виробництво")
    n_workers = st.number_input("Кількість працівників", min_value=1, value=300, step=10)
    hourly_cost = st.number_input("Вартість години праці, грн", min_value=0.0, value=250.0, step=10.0)
    factor_pct = st.slider("Коефіцієнт впливу простою, %", 0, 100, 100)
    machine_cost = st.number_input("Простій обладнання, грн/год", min_value=0.0, value=0.0, step=10.0)

factor = factor_pct / 100.0
working_days = [DAY_TO_INT[d] for d in selected_days]


# --- Title block ------------------------------------------------------------
st.markdown(
    f'<div class="page-title">Індекс простою від повітряних тривог</div>'
    f'<div class="page-subtitle">Історичний операційний простій виробництва по областях України</div>'
    f'<div class="page-caption">Джерело: офіційний датасет тривог, {min_date:%d.%m.%Y} – {max_date:%d.%m.%Y}. '
    f"Прибрано {diag['n_anomalies_removed']} аномальних записів, довших за 24 години.</div>",
    unsafe_allow_html=True,
)

# --- Input validation --------------------------------------------------------
if isinstance(date_sel, (list, tuple)):
    if len(date_sel) != 2:
        st.info("Оберіть кінцеву дату періоду.")
        st.stop()
    d_from, d_to = date_sel
else:
    d_from = d_to = date_sel

if not selected_regions:
    st.markdown('<div class="section-title"></div>', unsafe_allow_html=True)
    st.info("Оберіть хоча б одну область у лівій панелі.")
    st.stop()
if not working_days:
    st.info("Оберіть хоча б один робочий день.")
    st.stop()
if work_start >= work_end:
    st.info("Початок робочого дня має бути раніше за кінець.")
    st.stop()

range_start = pd.Timestamp(datetime.combine(d_from, time(0, 0)), tz=KYIV)
range_end = pd.Timestamp(datetime.combine(d_to, time(23, 59, 59)), tz=KYIV)


# --- Compute metrics ---------------------------------------------------------
iv_regions = intervals_all[intervals_all["oblast"].isin(selected_regions)]
iv_current = clip_intervals_to_range(iv_regions, range_start, range_end)
metrics, monthly = compute_metrics(
    iv_current, range_start, range_end, working_days, work_start, work_end,
    n_workers, hourly_cost, factor, machine_cost,
)

if metrics.empty or metrics["working_time_alert_hours"].sum() == 0:
    render_empty()
    st.stop()

# Previous period (same length, immediately before) for KPI deltas.
duration = range_end - range_start
prev_iv = clip_intervals_to_range(iv_regions, range_start - duration, range_start)
prev_metrics, _ = compute_metrics(
    prev_iv, range_start - duration, range_start, working_days, work_start, work_end,
    n_workers, hourly_cost, factor, machine_cost,
)

total_wt = float(metrics["working_time_alert_hours"].sum())
total_alert = float(metrics["total_alert_hours"].sum())
total_lost = float(metrics["lost_labor_hours"].sum())
total_cost = float(metrics["total_downtime_cost"].sum())
avg_avail = float(metrics["availability_ratio"].mean())

prev_wt = float(prev_metrics["working_time_alert_hours"].sum()) if not prev_metrics.empty else 0.0
prev_cost = float(prev_metrics["total_downtime_cost"].sum()) if not prev_metrics.empty else 0.0
delta_wt = (total_wt - prev_wt) / prev_wt if prev_wt > 0 else None
delta_cost = (total_cost - prev_cost) / prev_cost if prev_cost > 0 else None

bw = best_worst_comparison(metrics, by="downtime_index")


# --- Executive summary -------------------------------------------------------
worst_txt = (
    f"Найбільший простій: <b>{bw.worst_oblast}</b> (індекс {fmt_index(bw.worst_value)}). "
    f"Найменший: <b>{bw.best_oblast}</b> (індекс {fmt_index(bw.best_value)})."
    if bw else ""
)
st.markdown(
    f'<div class="summary-card">'
    f"<p>За період <b>{d_from:%d.%m.%Y} – {d_to:%d.%m.%Y}</b> по <b>{len(selected_regions)}</b> "
    f"обраних областях сумарно зафіксовано <b>{fmt_hours(total_wt)} год</b> тривог у робочий час "
    f"із {fmt_hours(total_alert)} год загальних тривог. Це відповідає приблизно "
    f"<b>{fmt_int(total_lost)}</b> втраченим людино-годинам і оціненій вартості простою "
    f"<b>{fmt_money_full(total_cost)}</b> при коефіцієнті впливу {factor_pct}%.</p>"
    f"<p>{worst_txt}</p>"
    f'<p class="summary-note">Це історична операційна аналітика, не прогноз і не оцінка безпеки. '
    f"Реальний простій залежить від укриттів, процесів і рішень підприємства.</p>"
    f"</div>",
    unsafe_allow_html=True,
)

# --- KPI cards ---------------------------------------------------------------
cards = "".join([
    kpi_card(
        "Простій у робочий час", f"{fmt_hours(total_wt)} год",
        delta_badge(delta_wt, higher_is_worse=True)
        + '<span class="kpi-context">проти попереднього періоду</span>',
    ),
    kpi_card(
        "Втрачені людино-години", fmt_int(total_lost),
        f'<span class="kpi-context">по {len(selected_regions)} обраних областях</span>',
    ),
    kpi_card(
        "Оцінена вартість простою", fmt_money(total_cost),
        delta_badge(delta_cost, higher_is_worse=True)
        + f'<span class="kpi-context">при коефіцієнті {factor_pct}%</span>',
    ),
    kpi_card(
        "Середня доступність", fmt_pct(avg_avail),
        status_badge(avg_avail)
        + '<span class="kpi-context">по обраних областях</span>',
    ),
])
st.markdown(f'<div class="kpi-grid">{cards}</div>', unsafe_allow_html=True)

# --- Comparison table --------------------------------------------------------
st.markdown('<div class="section-title">Порівняльна таблиця по областях</div>', unsafe_allow_html=True)
render_table(metrics)

# --- Charts ------------------------------------------------------------------
st.markdown('<div class="section-title">Порівняння областей</div>', unsafe_allow_html=True)
chart_cfg = {"displayModeBar": False}

row1_a, row1_b = st.columns(2)
with row1_a:
    with st.container(border=True):
        st.markdown('<div class="chart-title">Години тривог у робочий час</div>', unsafe_allow_html=True)
        st.plotly_chart(bar_working_hours(metrics), width="stretch", config=chart_cfg)
with row1_b:
    with st.container(border=True):
        st.markdown('<div class="chart-title">Оцінена вартість простою</div>', unsafe_allow_html=True)
        st.plotly_chart(bar_cost(metrics), width="stretch", config=chart_cfg)

row2_a, row2_b = st.columns(2)
with row2_a:
    with st.container(border=True):
        st.markdown('<div class="chart-title">Доступність виробництва</div>', unsafe_allow_html=True)
        st.plotly_chart(bar_availability(metrics), width="stretch", config=chart_cfg)
with row2_b:
    with st.container(border=True):
        st.markdown('<div class="chart-title">Помісячна динаміка простою</div>', unsafe_allow_html=True)
        st.plotly_chart(line_monthly(monthly), width="stretch", config=chart_cfg)

# --- Best vs worst -----------------------------------------------------------
st.markdown('<div class="section-title">Різниця між регіонами</div>', unsafe_allow_html=True)
if bw and bw.comparable:
    st.markdown(
        '<div class="bw-card"><div class="bw-grid">'
        f'<div class="bw-item"><div class="bw-k">Найменший простій</div>'
        f'<div class="bw-region">{bw.best_oblast}</div>'
        f'<div class="bw-v">індекс {fmt_index(bw.best_value)}</div></div>'
        f'<div class="bw-item"><div class="bw-k">Найбільший простій</div>'
        f'<div class="bw-region">{bw.worst_oblast}</div>'
        f'<div class="bw-v">індекс {fmt_index(bw.worst_value)}</div></div>'
        f'<div class="bw-item"><div class="bw-k">Різниця</div>'
        f'<div class="bw-region">{fmt_index(bw.difference)}</div>'
        f'<div class="bw-v">одиниць індексу простою</div></div>'
        "</div></div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="bw-card"><div class="bw-v">Оберіть щонайменше дві області для порівняння.</div></div>',
        unsafe_allow_html=True,
    )
