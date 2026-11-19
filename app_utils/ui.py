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

# Fix categories: categorical slots 1-3 (validated all-pairs, light + dark). Fixed mapping,
# never cycled. Aqua is below 3:1 on light, so it always appears with labels / tooltips / tables.
FIX_COLOURS = {"tower": "#2a78d6", "satellite": "#eb6834", "takeup_gap": "#1baf7a"}
FIX_LABELS = {"tower": "Tower", "satellite": "Satellite", "takeup_gap": "Take-up gap (fixed network likely nearby)",
              "none (take-up gap only)": "Take-up gap only"}
FIX_COLOURS["none (take-up gap only)"] = FIX_COLOURS["takeup_gap"]

OSM_CREDIT = "© OpenStreetMap contributors"
BASEMAP_CREDIT = "Basemap © OpenStreetMap contributors © CARTO"


def hex_rgb(h: str, alpha: int = 255) -> list[int]:
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)] + [alpha]


def page(title: str, intro: str | None = None) -> None:
    st.title(title)
    if intro:
        st.markdown(f"<p style='color:{INK_2};margin-top:-0.6rem'>{intro}</p>", unsafe_allow_html=True)


def what(text: str) -> None:
    """Short 'what this shows' line under a chart."""
    st.markdown(f"<p style='color:{INK_2};font-size:0.88rem;margin-top:-0.4rem'><b>What this shows:</b> {text}</p>",
                unsafe_allow_html=True)


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
    fig.update_layout(
        height=height, template="none", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif', color=INK_2, size=13),
        margin=dict(l=10, r=20, t=30, b=10), showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None),
        hoverlabel=dict(bgcolor="white", font_color=INK, bordercolor=MUTED_LIGHT),
        **layout,
    )
    axis = dict(gridcolor=GRID, linecolor=MUTED_LIGHT, zerolinecolor=MUTED_LIGHT, tickfont=dict(color=MUTED),
                title_font=dict(color=INK_2))
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    return fig


def fmt_pct(v, d: int = 1) -> str:
    return "–" if v is None or v != v else f"{v:.{d}f}%"


def fmt_rm(v) -> str:
    if v is None or v != v:
        return "–"
    return f"RM{v / 1e9:,.2f}bn" if abs(v) >= 1e9 else f"RM{v / 1e6:,.1f}m"
