"""Static explainer graphics for non-expert readers: covered vs connected, how settlements are grouped, where the
rural settlements fall, and terms in plain words. No new data: every number is read from data/processed or config/."""
from __future__ import annotations

import html
import re

import plotly.graph_objects as go
import streamlit as st

from app_utils import data, ui

# --- terms in plain words (shown in an expander and as hover help where the terms appear) ---
TERMS = {
    "Take-up": "People signing up for a service that already reaches them. Take-up support means subsidies, "
               "awareness and help signing up, not new network.",
    "FWA": "Fixed Wireless Access: home broadband carried over the mobile network to a router inside the house, "
           "with no cable to the home.",
    "Small cell": "A small, low-power mobile antenna that covers a village or a few streets, instead of a full tower.",
    "Community Wi-Fi": "One shared internet point (for example at the school or community hall) that people nearby "
                       "join over Wi-Fi.",
    "LEO satellite": "Low-earth-orbit satellite internet: satellites much closer to Earth than older ones, so faster "
                     "with less delay. Each home needs a small dish with a clear view of the sky.",
    "Backhaul": "The link that carries a village site's traffic back to the main network: fibre, a microwave radio "
                "link or satellite.",
    "Fibre PoP": "A point of presence: a place where homes and sites can join the fibre network. We use it only as an "
                 "upper-bound cost, not as a recommendation.",
    "Proxy": "An indirect sign used when the real measure is not public. Example: speed tests run nearby suggest a "
             "network is there; they are not a coverage map.",
}
# text patterns that get hover help (first match per term in a piece of text)
_PATTERNS = [
    ("Take-up", r"\btake-up\b"), ("FWA", r"\bFixed Wireless Access\b|\bFWA\b"), ("Small cell", r"\bsmall cells?\b"),
    ("Community Wi-Fi", r"\bcommunity Wi-Fi\b"), ("LEO satellite", r"\blow-earth-orbit\b|\bLEO\b"),
    ("Backhaul", r"\bbackhaul\b"), ("Fibre PoP", r"\bfibre PoPs?\b"), ("Proxy", r"\bprox(?:y|ies)\b"),
]


def gloss(text: str) -> str:
    """Plain text -> HTML with hover help (dotted underline + title) on the first mention of each term."""
    out = html.escape(str(text), quote=False)
    for term, pat in _PATTERNS:
        tip = html.escape(TERMS[term], quote=True)
        out = re.sub(pat, lambda m: (f"<abbr title=\"{tip}\" style='text-decoration:underline dotted;"
                                     f"cursor:help'>{m.group(0)}</abbr>"), out, count=1, flags=re.I)
    return out


def terms_expander() -> None:
    with st.expander("Terms in plain words"):
        st.markdown("\n".join(f"- **{k}:** {v}" for k, v in TERMS.items()))


# --- simple icons (identity is also always given in words) ---
def _icon(code: str, size: int = 30) -> str:
    c = ui.TYPE_COLOURS.get(code, ui.MUTED)
    paths = {
        # house + cable to a box: network nearby
        "A": "<path d='M4 16 L12 9 L20 16 V26 H4 Z'/><path d='M20 21 H28'/><rect x='26' y='17' width='4' height='8'/>",
        # tower
        "B": "<path d='M16 5 L10 28 M16 5 L22 28 M12 20 H20 M13.5 13 H18.5'/><path d='M9 6 Q6 10 9 14 M23 6 Q26 10 23 14'/>",
        # signal bars
        "E": "<rect x='5' y='20' width='4' height='7'/><rect x='12' y='15' width='4' height='12'/>"
             "<rect x='19' y='10' width='4' height='17'/><rect x='26' y='5' width='4' height='22'/>",
        # satellite dish
        "D": "<path d='M6 10 A12 12 0 0 0 22 26 Z'/><path d='M14 18 L24 8'/><circle cx='25' cy='7' r='2'/>"
             "<path d='M12 26 H22'/>",
        # small antenna with wifi arcs
        "C": "<path d='M16 14 V28 M12 28 H20'/><path d='M11 11 Q16 6 21 11 M8 8 Q16 0 24 8'/>",
    }
    return (f"<svg width='{size}' height='{size}' viewBox='0 0 32 32' fill='none' stroke='{c}' stroke-width='2.2' "
            f"stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>{paths.get(code, '')}</svg>")


# --- 1. covered is not the same as connected ---
def covered_vs_connected(coverage_pct: float, coverage_label: str, rural_offline_pct: float, year: int) -> None:
    acc, ink, ink2, mut = ui.ACCENT, ui.INK, ui.INK_2, ui.MUTED
    houses = [(262, 112), (312, 86), (360, 118), (300, 146), (352, 160)]
    hs = "".join(f"<g transform='translate({x},{y})'><path d='M-13 0 L0 -12 L13 0 V14 H-13 Z' fill='#ffffff' "
                 f"stroke='{mut}' stroke-width='2'/></g>" for x, y in houses[:-1])
    ox, oy = houses[-1]
    off = (f"<g transform='translate({ox},{oy})'><path d='M-13 0 L0 -12 L13 0 V14 H-13 Z' fill='#ffffff' stroke='{ink}' "
           f"stroke-width='2.4' stroke-dasharray='4 3'/><circle cx='15' cy='-12' r='9' fill='{ink}'/>"
           f"<path d='M11 -16 L19 -8 M19 -16 L11 -8' stroke='#ffffff' stroke-width='2.2'/></g>")
    svg = (f"<svg viewBox='0 0 400 200' width='100%' style='max-width:420px' role='img' "
           f"aria-label='A tower whose signal area covers a village; one house in the village is still offline'>"
           f"<circle cx='70' cy='120' r='300' fill='{acc}' fill-opacity='0.07'/>"
           + "".join(f"<path d='M{70 + r * 0.7:.0f} {120 - r * 0.7:.0f} A{r} {r} 0 0 1 {70 + r * 0.7:.0f} {120 + r * 0.7:.0f}' "
                     f"fill='none' stroke='{acc}' stroke-opacity='0.45' stroke-width='2'/>" for r in (40, 75, 110))
           + f"<path d='M70 40 L50 180 M70 40 L90 180 M56 140 H84 M61 105 H79 M65 72 H75' stroke='{ink2}' "
             f"stroke-width='3' fill='none' stroke-linecap='round'/><circle cx='70' cy='38' r='5' fill='{acc}'/>"
           + hs + off
           + f"<text x='{ox}' y='194' font-size='12' fill='{ink2}' text-anchor='middle'>offline home</text></svg>")
    lab = (f"<div style='flex:1 1 260px;min-width:240px'>"
           f"<div style='margin-bottom:12px'><div style='font-size:0.8rem;color:{ink2}'>Network reaches the area</div>"
           f"<div style='font-size:1.45rem;font-weight:650;color:{ink}'>{coverage_pct:.2f}%</div>"
           f"<div style='font-size:0.85rem;color:{ink2}'>of populated areas (mainly outdoor)</div></div>"
           f"<div><div style='font-size:0.8rem;color:{ink2}'>But some homes are still offline</div>"
           f"<div style='font-size:1.45rem;font-weight:650;color:{ink}'>{rural_offline_pct:.1f}%</div>"
           f"<div style='font-size:0.85rem;color:{ink2}'>of rural households have no internet (DOSM {year})</div></div>"
           f"<div style='font-size:0.78rem;color:{mut};margin-top:8px'>{html.escape(coverage_label)} and household "
           "access are two different indicators, not a measured gap.</div></div>")
    st.markdown(f"<div style='border:1px solid {ui.GRID};border-radius:8px;padding:10px 14px;margin:0.2rem 0 0.8rem 0'>"
                f"<div style='font-weight:650;color:{ink};font-size:1.05rem;margin-bottom:4px'>Covered is not the same as "
                f"connected</div><div style='display:flex;flex-wrap:wrap;gap:16px;align-items:center'>"
                f"<div style='flex:1 1 300px;min-width:260px'>{svg}</div>{lab}</div></div>", unsafe_allow_html=True)


# --- 2. how settlements are grouped (thresholds read from config) ---
def _thresholds() -> dict:
    stc = data.yaml_config("settlement_types")
    costs = data.yaml_config("costs")
    t, s = costs["tower"], costs["satellite"]
    tower5 = t["capex_per_site_rm"]["central"] + 5 * t["opex_per_site_per_year_rm"]
    sat5 = s["kit_rm"] + 60 * s["monthly_rm"]["residential"]
    fixed_cols = [c for c in data.csv("costing_clusters").columns if re.fullmatch(r"fixed_tiles_\d+km", c)]
    fixed_km = int(re.search(r"(\d+)km", fixed_cols[0]).group(1)) if fixed_cols else None
    return {"fixed_km": fixed_km, "breakeven": tower5 / sat5, "mq": stc["mobile_quality"],
            "road_km": stc["road"]["very_far_min_km"], "steep": stc["terrain"]["steep_min_deg"], "types": stc["types"]}


PLAIN = {  # candidate technology in plain words (the full screening list stays in the table and Method)
    "A": "Help people sign up to the network already there (take-up support), or connect homes to it",
    "B": "A new mobile tower, with home broadband over it (FWA)",
    "E": "Home broadband over the existing mobile network (FWA)",
    "D": "Satellite internet for each home (LEO satellite), or community Wi-Fi fed by satellite",
    "C": "A small cell or community Wi-Fi, linked back by radio or satellite (backhaul)",
}


def grouping_flow() -> None:
    """Question-by-question flow ending in types A, B, E, D, C (first 'yes' wins)."""
    th = _thresholds()
    mq = th["mq"]
    fk = f"{th['fixed_km']} km" if th["fixed_km"] else "a short distance"
    steps = [
        ("A", f"Is a fixed (cable or fibre) network within {fk}?",
         f"Our proxy: an Ookla fixed-broadband speed test within {fk} of the school."),
        ("B", f"Are there at least {th['breakeven']:.0f} homes without internet?",
         "Enough homes for a tower to cost less than satellite dishes over five years (cost screen)."),
        ("E", "Is the mobile signal good nearby?",
         f"At least {mq['min_tests']} mobile speed tests within {mq['search_km']} km, averaging at least "
         f"{mq['good_min_mbps']} Mbps (the JENDELA target)."),
        ("D", f"Is it more than {th['road_km']} km from a road, or on steep ground?",
         f"Steep = average slope of {th['steep']}° or more around the school."),
        ("C", "Otherwise", "A small village that a road reaches, with weak or untested mobile signal."),
    ]
    rows = []
    for i, (code, q, why) in enumerate(steps):
        lab = th["types"][code]["label"]
        col = ui.TYPE_COLOURS[code]
        yes = "Yes" if code != "C" else ""
        rows.append(
            f"<div style='display:flex;flex-wrap:wrap;align-items:stretch;gap:8px;margin:0 0 4px 0'>"
            f"<div style='flex:1 1 260px;border:1px solid {ui.GRID};border-radius:8px;padding:8px 10px;background:#fff'>"
            f"<div style='font-size:0.72rem;color:{ui.MUTED}'>{'Question ' + str(i + 1) if code != 'C' else 'If every answer is no'}</div>"
            f"<div style='font-weight:600;color:{ui.INK};font-size:0.92rem'>{q}</div>"
            f"<div style='font-size:0.8rem;color:{ui.INK_2}'>{gloss(why)}</div></div>"
            f"<div style='flex:0 0 46px;display:flex;align-items:center;justify-content:center;color:{ui.INK_2};"
            f"font-size:0.8rem;font-weight:600'>{yes} →</div>"
            f"<div style='flex:1 1 260px;border:1px solid {ui.GRID};border-left:6px solid {col};border-radius:8px;"
            f"padding:8px 10px;background:#fff;display:flex;gap:10px;align-items:center'>{_icon(code)}"
            f"<div><div style='font-weight:650;color:{ui.INK};font-size:0.92rem'>{code}. {html.escape(lab)}</div>"
            f"<div style='font-size:0.8rem;color:{ui.INK_2}'>{gloss(PLAIN[code])}</div></div></div></div>"
            + (f"<div style='margin:0 0 4px 18px;color:{ui.MUTED};font-size:0.78rem'>No ↓</div>" if code != "C" else ""))
    st.markdown("<div style='margin:0.2rem 0 0.4rem 0'>" + "".join(rows) + "</div>", unsafe_allow_html=True)
    st.caption("The first “yes” decides the type, so every settlement gets exactly one. Candidate technologies are a "
               "screening list, not a recommendation; a site survey decides. Thresholds: config/settlement_types.yaml "
               "and config/costs.yaml.")


# --- 3. where the rural settlements fall (one stacked bar) ---
BAR_ORDER = ["A", "E", "C", "D", "B"]


def settlements_bar(scope: str) -> None:
    ts = data.type_summary(scope).set_index("settlement_type")
    n = int(ts.settlements.sum())
    sv = data.servable_share(scope)
    where = "Malaysia's" if scope == "All Malaysia" else "Sarawak's"
    st.markdown(f"**Where {where} {n:,} rural settlements fall**")
    fig = go.Figure()
    for k in BAR_ORDER:
        if k not in ts.index:
            continue
        v = int(ts.loc[k, "settlements"])
        fig.add_trace(go.Bar(
            x=[v], y=[""], orientation="h", name=f"{k}. {ts.loc[k, 'type_label']}",
            marker=dict(color=ui.TYPE_COLOURS[k], line=dict(color=ui.SURFACE, width=2)),
            text=[f"{k} {v:,}" if v / max(n, 1) >= 0.06 else ""], textposition="inside", insidetextanchor="middle",
            textfont=dict(color="#ffffff" if k == "B" else ui.INK, size=12),
            hovertemplate=f"{k}. {ts.loc[k, 'type_label']}: %{{x:,}} settlements ({100 * v / max(n, 1):.1f}%)<extra></extra>"))
    ui.style(fig, height=170, margin=dict(l=4, r=4, t=36, b=4))
    fig.update_layout(barmode="stack", legend=dict(orientation="h", y=-0.15, yanchor="top", x=0, font=dict(size=11),
                                                  traceorder="normal"),
                      bargap=0.25, height=165, margin=dict(l=4, r=4, t=26, b=4))
    fig.update_xaxes(visible=False, range=[0, n])
    fig.update_yaxes(visible=False)
    # bracket over A + E: servable through existing networks
    ex = sv["existing"]
    fig.add_shape(type="line", x0=0, x1=ex, y0=0.55, y1=0.55, line=dict(color=ui.INK_2, width=1.5))
    fig.add_annotation(x=ex / 2, y=0.62, text=f"{ui.about_one_in(sv['share'])} servable through existing networks "
                       "(A + E, proxy-based)", showarrow=False, yanchor="bottom", font=dict(size=12, color=ui.INK))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    small = [f"{k} {int(ts.loc[k, 'settlements']):,}" for k in BAR_ORDER
             if k in ts.index and int(ts.loc[k, "settlements"]) / max(n, 1) < 0.06]
    if small:
        st.caption("Too small to label on the bar: " + ", ".join(small) + ". Hover a segment for its share.")
