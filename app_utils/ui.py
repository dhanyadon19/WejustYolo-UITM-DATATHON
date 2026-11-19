"""Shared look and feel: one accent colour, muted greys, validated categorical slots for the
three fix categories, chart styling, captions and source footers."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

# --- palette (reference palette, light mode; validated with the dataviz validator) ---
ACCENT = "#2a78d6"          # the one accent colour
INK = "#0b0b0b"
INK_2 = "#52514e"            # secondary text
MUTED = "#898781"            # axis labels, de-emphasised marks
MUTED_LIGHT = "#c3c2b7"      # context marks, baseline
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"

# Fix categories: deep blue / orange / lighter green, chosen for strong lightness contrast and
# validated all-pairs (dataviz validator: lightness, chroma, CVD >= 10, normal-vision >= 25).
# Fixed mapping, never cycled. The green is below 3:1 on light, so it always appears with labels,
# tooltips or tables.
FIX_COLOURS = {"tower": "#1c5cab", "satellite": "#eb6834", "takeup_gap": "#58b98c"}
FIX_LABELS = {"tower": "Tower", "satellite": "Satellite", "takeup_gap": "Take-up gap (fixed network likely nearby)",
              "none (take-up gap only)": "Take-up gap only"}
FIX_COLOURS["none (take-up gap only)"] = FIX_COLOURS["takeup_gap"]

# --- shared wording (reviewed) ---
BENEFIT = "estimated beneficiaries per RM1m"
BENEFIT_RANK = "estimated-beneficiaries-per-RM1m rank"
INFERRED_N = "inferred sample size"
MOE_TXT = "approximate margin of error (simple random-sampling formula)"
NOT_DOSM = "These are our estimates from DOSM's published percentages, not figures DOSM publishes."
TAKEUP_TXT = ("Our proxy suggests many rural settlements already have a fixed network nearby, so take-up support may "
              "matter as much as new infrastructure.")
COST_SCREEN = ("Cost screen, not a full cost-benefit comparison: households are assumed equal across a district's "
               "rural schools, and towers and satellite are different services (a tower also serves mobile users and "
               "roads; satellite serves single homes).")


def caveat(text: str = COST_SCREEN) -> None:
    st.markdown(f"<div style='border-left:3px solid {MUTED_LIGHT};padding:2px 10px;color:{INK_2};font-size:0.85rem'>"
                f"{text}</div>", unsafe_allow_html=True)

OSM_CREDIT = "© OpenStreetMap contributors"
BASEMAP_CREDIT = "Basemap © OpenStreetMap contributors © CARTO"


def hex_rgb(h: str, alpha: int = 255) -> list[int]:
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)] + [alpha]


def page(title: str, intro: str | None = None) -> None:
    st.title(title)
    if intro:
        st.markdown(f"<p style='color:{INK_2};margin-top:-0.6rem'>{intro}</p>", unsafe_allow_html=True)


def what(text: str, data: str | None = None) -> None:
    """Short 'what this shows' line under a chart or table, with the data source and year."""
    chip = (f"<span style='background:#f3f2ee;border-radius:4px;padding:1px 6px;margin-right:6px;"
            f"color:{INK_2};display:inline;line-height:1.7'>Data: {data}</span>") if data else ""
    st.markdown(f"<p style='color:{INK_2};font-size:0.88rem;margin-top:-0.4rem'>{chip}<b>What this shows:</b> {text}</p>",
                unsafe_allow_html=True)


def next_step(page: str, label: str, why: str) -> None:
    """'Next' card at the end of a page that walks the user journey:
    Overview → Schools → Sarawak map → District detail → Priorities → Method."""
    st.markdown(f"<div style='margin-top:1.6rem;color:{INK_2};font-size:0.9rem'><b>Next:</b> {why}</div>",
                unsafe_allow_html=True)
    st.page_link(page, label=label, icon=":material/arrow_forward:")


def go_to_district(state: str, district: str) -> None:
    """Open District detail with this district preselected."""
    st.session_state["detail_state"] = state
    st.session_state["detail_district"] = district
    st.switch_page("views/4_District_detail.py")


def footer(sources: list[str], osm: bool = False, basemap: bool = False) -> None:
    st.divider()
    lines = [f"- {s}" for s in sources]
    if osm:
        lines.append(f"- District boundaries in Sarawak: {OSM_CREDIT} (ODbL); elsewhere DOSM (2022)")
    if basemap:
        lines.append(f"- {BASEMAP_CREDIT}")
    st.markdown(f"<div style='color:{MUTED};font-size:0.8rem'><b>Sources</b></div>", unsafe_allow_html=True)
    st.markdown("\n".join(lines), help=None)


def style(fig: go.Figure, height: int = 420, legend: bool = True, **layout) -> go.Figure:
    base = dict(
        height=height, template="none", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif', color=INK_2, size=13),
        margin=dict(l=10, r=20, t=30, b=10), showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None),
        hoverlabel=dict(bgcolor="white", font_color=INK, bordercolor=MUTED_LIGHT),
    )
    base.update(layout)  # caller overrides win
    fig.update_layout(**base)
    axis = dict(gridcolor=GRID, linecolor=MUTED_LIGHT, zerolinecolor=MUTED_LIGHT, tickfont=dict(color=MUTED),
                title_font=dict(color=INK_2))
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    return fig


# --- safe formatting helpers (NaN / None -> "–") ---
DASH = "–"


def isnum(v) -> bool:
    """True for a real, finite number (not None / NaN / pd.NA)."""
    try:
        return v is not None and v == v and float(v) not in (float("inf"), float("-inf"))
    except (TypeError, ValueError):
        return False


def fmt_num(v, fmt: str = ",.0f", prefix: str = "", suffix: str = "") -> str:
    return f"{prefix}{v:{fmt}}{suffix}" if isnum(v) else DASH


def fmt_int(v) -> str:
    return f"{int(v):,}" if isnum(v) else DASH


def fmt_pct(v, d: int = 1) -> str:
    return f"{v:.{d}f}%" if isnum(v) else DASH


def fmt_rm(v) -> str:
    """RM amounts: RMx.xxbn at or above RM1bn, otherwise RMx.xm."""
    if not isnum(v):
        return DASH
    return f"RM{v / 1e9:,.2f}bn" if abs(v) >= 1e9 else f"RM{v / 1e6:,.1f}m"


def range_text(lo, hi) -> str:
    return f"{int(round(lo))}–{int(round(hi))}" if isnum(lo) and isnum(hi) else DASH


def rank_range(rank, lo, hi) -> str:
    """'12 (range 9–14)'; just the rank if the range is missing; '–' if no rank."""
    if not isnum(rank):
        return DASH
    return f"{int(rank)} (range {range_text(lo, hi)})" if isnum(lo) and isnum(hi) else f"{int(rank)}"


def safe_div(num, den):
    return num / den if isnum(num) and isnum(den) and den != 0 else float("nan")


def moe_text(moe) -> str:
    """Caption for an access figure; empty when there is no inferred margin."""
    return f"Approx. margin of error ±{moe:.1f} pp (simple random-sampling formula; our estimate)" if isnum(moe) else ""


def moe_badge(col, moe) -> None:
    """Margin-of-error caption under a metric, only when one exists."""
    t = moe_text(moe)
    if t:
        col.caption(t)


def small_sample_banner(name: str, n, moe) -> None:
    """Low-confidence warning for small-sample districts (degrades gracefully if n or MOE is missing)."""
    parts = []
    if isnum(n):
        parts.append(f"{INFERRED_N} about {int(n)} households")
    if isnum(moe):
        parts.append(f"{MOE_TXT} ±{moe:.1f} percentage points")
    detail = (": " + ", ".join(parts) + ".") if parts else "."
    st.warning(f"**Low confidence.** {name}'s DOSM estimate appears to rest on a small sample{detail} "
               f"{NOT_DOSM} Treat its ranks as ranges, not exact positions.", icon="⚠️")


def fallback(text: str) -> None:
    """Short message shown instead of a chart or figure that cannot be computed."""
    st.info(text, icon="ℹ️")
