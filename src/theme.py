"""Visual theme for the dashboard.

One place for all design decisions, taken straight from the project UI style
guide (Dark Premium): color tokens, the injected CSS, a Plotly styling helper,
and Ukrainian number formatters. Keeping it here means app.py and the charts
stay readable.
"""
from __future__ import annotations

# --- Color tokens (Dark Premium theme from the style guide) -----------------
COLORS = {
    "bg_base": "#0B0D12",
    "bg_subtle": "#10131A",
    "surface": "#151922",
    "surface_elevated": "rgba(24, 29, 39, 0.78)",
    "surface_glass": "rgba(255, 255, 255, 0.06)",
    "text_primary": "#F5F7FA",
    "text_secondary": "#A8B0BD",
    "text_tertiary": "#6F7785",
    "border_subtle": "rgba(255, 255, 255, 0.08)",
    "border_strong": "rgba(255, 255, 255, 0.14)",
    "accent": "#0A84FF",
    "accent_hover": "#2997FF",
    "accent_soft": "rgba(10, 132, 255, 0.14)",
    "positive": "#30D158",
    "positive_soft": "rgba(48, 209, 88, 0.14)",
    "negative": "#FF453A",
    "negative_soft": "rgba(255, 69, 58, 0.14)",
    "warning": "#FFD60A",
    "warning_soft": "rgba(255, 214, 10, 0.14)",
    "purple": "#BF5AF2",
    "cyan": "#64D2FF",
}

# Distinct, non-semantic palette for multi-region line series (avoids using
# pure red/green as categorical colors, per the style guide).
SERIES_PALETTE = [
    "#0A84FF",  # blue
    "#64D2FF",  # cyan
    "#BF5AF2",  # purple
    "#FFD60A",  # amber
    "#5E5CE6",  # indigo
    "#FF9F0A",  # orange
    "#40C8C0",  # teal
    "#C7A2FF",  # light violet
    "#7FB2FF",  # light blue
    "#AC8E68",  # taupe
]

NBSP = "\u00A0"
MINUS = "\u2212"  # real minus sign, per the style guide


# --- Number formatting (Ukrainian: space thousands, comma decimal) ----------
def _group(num_str: str) -> str:
    return num_str.replace(",", NBSP)


def fmt_int(x: float) -> str:
    return _group(f"{round(x):,}")


def fmt_hours(x: float) -> str:
    return _group(f"{x:,.1f}").replace(".", ",")


def fmt_money(x: float) -> str:
    """Compact money for KPI cards, e.g. 85,9 млн ₴."""
    sign = MINUS if x < 0 else ""
    x = abs(x)
    if x >= 1_000_000_000:
        return f"{sign}{x / 1e9:,.1f}".replace(".", ",") + f"{NBSP}млрд{NBSP}₴"
    if x >= 1_000_000:
        return f"{sign}{x / 1e6:,.1f}".replace(".", ",") + f"{NBSP}млн{NBSP}₴"
    return _group(f"{sign}{x:,.0f}") + f"{NBSP}₴"


def fmt_money_full(x: float) -> str:
    """Full money for the table, e.g. 85 924 604 ₴."""
    sign = MINUS if x < 0 else ""
    return _group(f"{sign}{abs(x):,.0f}") + f"{NBSP}₴"


def fmt_pct(ratio: float) -> str:
    if ratio != ratio:  # NaN
        return "—"
    return f"{ratio * 100:,.1f}".replace(".", ",") + "%"


def fmt_index(x: float) -> str:
    if x != x:  # NaN
        return "—"
    return _group(f"{x:,.1f}").replace(".", ",")


def fmt_delta_pct(frac: float) -> str:
    """Signed percentage change, e.g. +12,4% or −8,1%."""
    sign = "+" if frac > 0 else (MINUS if frac < 0 else "")
    return f"{sign}{abs(frac) * 100:,.1f}".replace(".", ",") + "%"


# --- Plotly styling ---------------------------------------------------------
def style_fig(fig, height: int = 320):
    """Apply the clean dark chart style from the style guide to a figure."""
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=13, color=COLORS["text_secondary"]),
        margin=dict(l=8, r=8, t=8, b=8),
        hoverlabel=dict(
            bgcolor=COLORS["surface"],
            bordercolor=COLORS["border_strong"],
            font=dict(family="Inter, sans-serif", color=COLORS["text_primary"], size=13),
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            font=dict(color=COLORS["text_secondary"], size=12),
        ),
        showlegend=False,
        bargap=0.35,
    )
    fig.update_xaxes(
        showgrid=False, zeroline=False, linecolor=COLORS["border_subtle"],
        tickfont=dict(size=12, color=COLORS["text_tertiary"]),
    )
    fig.update_yaxes(
        showgrid=True, gridcolor="rgba(255,255,255,0.06)", gridwidth=1, zeroline=False,
        tickfont=dict(size=12, color=COLORS["text_tertiary"]),
    )
    return fig


# --- Injected CSS -----------------------------------------------------------
def custom_css() -> str:
    c = COLORS
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {{
  --bg-base: {c['bg_base']};
  --surface: {c['surface']};
  --surface-elevated: {c['surface_elevated']};
  --surface-glass: {c['surface_glass']};
  --text-primary: {c['text_primary']};
  --text-secondary: {c['text_secondary']};
  --text-tertiary: {c['text_tertiary']};
  --border-subtle: {c['border_subtle']};
  --border-strong: {c['border_strong']};
  --accent: {c['accent']};
  --accent-soft: {c['accent_soft']};
  --positive: {c['positive']};
  --positive-soft: {c['positive_soft']};
  --negative: {c['negative']};
  --negative-soft: {c['negative_soft']};
  --warning: {c['warning']};
  --warning-soft: {c['warning_soft']};
  --radius-lg: 18px;
  --radius-xl: 24px;
  --shadow-card: 0 16px 40px rgba(0,0,0,0.18);
}}

/* Inter everywhere + tabular numbers for all figures */
html, body, .stApp, button, input, select, textarea,
[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"] {{
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}}
.stApp, .stApp * {{
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum" 1, "zero" 1;
}}

.stApp {{ background: var(--bg-base); }}

/* Quiet the default Streamlit chrome for a cleaner, presentational look */
[data-testid="stToolbar"], footer, #MainMenu {{ visibility: hidden; }}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1440px; }}

/* Sidebar: frosted glass surface */
section[data-testid="stSidebar"] > div {{
  background: rgba(16, 19, 26, 0.85);
  backdrop-filter: blur(24px);
  border-right: 1px solid var(--border-subtle);
}}
section[data-testid="stSidebar"] .stMarkdown h2 {{
  font-size: 13px; letter-spacing: 0.04em; text-transform: uppercase;
  color: var(--text-tertiary); font-weight: 600; margin-bottom: 4px;
}}

/* Headings / titles */
.page-title {{
  font-size: 32px; line-height: 40px; font-weight: 700;
  color: var(--text-primary); margin: 0;
}}
.page-subtitle {{
  font-size: 15px; line-height: 22px; color: var(--text-secondary);
  margin: 4px 0 2px 0;
}}
.page-caption {{
  font-size: 12px; color: var(--text-tertiary); margin-top: 2px;
}}
.section-title {{
  font-size: 22px; line-height: 30px; font-weight: 600;
  color: var(--text-primary); margin: 26px 0 12px 0;
}}

/* Cards */
.summary-card, .bw-card, .empty-card {{
  background: var(--surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xl);
  padding: 22px 24px;
  box-shadow: var(--shadow-card);
  backdrop-filter: blur(24px);
}}
.summary-card p {{ margin: 0 0 8px 0; color: var(--text-secondary); font-size: 15px; line-height: 23px; }}
.summary-card p:last-child {{ margin-bottom: 0; }}
.summary-card b {{ color: var(--text-primary); font-weight: 600; }}
.summary-note {{ color: var(--text-tertiary) !important; font-size: 13px !important; }}

/* KPI grid */
.kpi-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px; margin: 6px 0 4px 0;
}}
.kpi-card {{
  background: var(--surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: 18px 20px;
  box-shadow: var(--shadow-card);
  backdrop-filter: blur(24px);
}}
.kpi-label {{ font-size: 13px; font-weight: 500; color: var(--text-secondary); }}
.kpi-value {{
  font-size: 34px; line-height: 42px; font-weight: 700;
  color: var(--text-primary); margin: 6px 0 6px 0;
}}
.kpi-foot {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
.kpi-context {{ font-size: 12px; color: var(--text-tertiary); }}

/* Badges */
.badge {{
  display: inline-flex; align-items: center; gap: 5px; height: 24px;
  padding: 0 9px; border-radius: 999px; font-size: 12px; font-weight: 600;
}}
.badge-pos {{ background: var(--positive-soft); color: var(--positive); }}
.badge-neg {{ background: var(--negative-soft); color: var(--negative); }}
.badge-warn {{ background: var(--warning-soft); color: var(--warning); }}
.badge-neutral {{ background: var(--surface-glass); color: var(--text-secondary); }}

/* Comparison table */
.cmp-wrap {{
  background: var(--surface-elevated); border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xl); box-shadow: var(--shadow-card);
  backdrop-filter: blur(24px); overflow: hidden; margin-top: 4px;
}}
table.cmp {{ width: 100%; border-collapse: collapse; font-size: 13.5px; }}
table.cmp thead th {{
  text-align: right; font-size: 11px; font-weight: 600; letter-spacing: 0.04em;
  text-transform: uppercase; color: var(--text-tertiary);
  padding: 14px 16px; border-bottom: 1px solid var(--border-subtle);
  white-space: nowrap; background: rgba(255,255,255,0.02);
}}
table.cmp thead th.left {{ text-align: left; }}
table.cmp tbody td {{
  text-align: right; padding: 13px 16px; color: var(--text-primary);
  border-bottom: 1px solid var(--border-subtle); white-space: nowrap;
}}
table.cmp tbody td.left {{ text-align: left; color: var(--text-secondary); font-weight: 500; }}
table.cmp tbody tr:last-child td {{ border-bottom: none; }}
table.cmp tbody tr:hover td {{ background: var(--surface-glass); }}
td.good {{ color: var(--positive); }}
td.mid {{ color: var(--warning); }}
td.bad {{ color: var(--negative); }}

/* Best vs worst block */
.bw-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 18px; }}
.bw-item .bw-k {{ font-size: 12px; color: var(--text-tertiary); }}
.bw-item .bw-region {{ font-size: 18px; font-weight: 600; color: var(--text-primary); margin: 4px 0 2px 0; }}
.bw-item .bw-v {{ font-size: 13px; color: var(--text-secondary); }}

/* Empty state */
.empty-card {{ text-align: center; padding: 48px 24px; }}
.empty-card .e-title {{ font-size: 18px; font-weight: 600; color: var(--text-primary); margin: 10px 0 6px 0; }}
.empty-card .e-text {{ font-size: 14px; color: var(--text-secondary); }}

/* Chart card wrapper (bordered container) */
[data-testid="stVerticalBlockBorderWrapper"] {{
  background: var(--surface-elevated);
  border: 1px solid var(--border-subtle) !important;
  border-radius: var(--radius-xl) !important;
  box-shadow: var(--shadow-card);
  backdrop-filter: blur(24px);
  padding: 6px 10px 10px 10px;
}}
.chart-title {{ font-size: 15px; font-weight: 600; color: var(--text-primary); margin: 8px 4px 0 8px; }}

/* Accessibility + restraint */
:focus-visible {{ outline: 3px solid rgba(10,132,255,0.42); outline-offset: 2px; }}
@media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; animation: none !important; }} }}
</style>
"""
