"""Sarawak map: 3D districts, height = Connectivity Gap Index, colour = fix."""
import copy

import pandas as pd
import pydeck as pdk
import streamlit as st

from app_utils import data, ui

STATE = "Sarawak"
geo = data.district_geojson(STATE)
dt = data.district_table()
grp = data.settlement_groups()
t3 = data.csv("dosm_hh_ict_district_2025")
w = data.yaml_config("weights")["weights"]

d = dt[dt.state == STATE].merge(grp, on=["state", "district"], how="left")

ui.page("Sarawak: where the gap is deepest",
        "Taller districts have a larger Connectivity Gap Index. Colour shows what kind of fix the rural gap mostly needs.")

mode = st.radio("Colour districts by",
                ["Largest group of rural people without home internet", "Main infrastructure fix (tower or satellite)"],
                horizontal=True)
key = "largest_group" if mode.startswith("Largest") else "main_fix"


def ranges(r, base, p05, p95):
    return f"{int(r[base])} (range {int(r[p05])}–{int(r[p95])})" if pd.notna(r[base]) else "–"


props = {}
for _, r in d.iterrows():
    cat = r[key] if isinstance(r[key], str) else None
    props[r.district] = {
        "cgi": round(float(r.cgi), 3),
        "colour": ui.hex_rgb(ui.FIX_COLOURS.get(cat, ui.MUTED_LIGHT), 215),
        "fix_label": ui.FIX_LABELS.get(cat, "–"),
        "need_rank": ranges(r, "rank_sarawak", "rank_sarawak_p05", "rank_sarawak_p95"),
        "access": f"{r.internet_pct:.1f}%" + (f" ± {r.internet_moe95_pp:.1f} pp" if r.small_sample_flag else ""),
        "small_sample": "Yes: low confidence" if r.small_sample_flag else "No",
        "mobile": f"{r.mb_dl_mbps:.0f} Mbps" if pd.notna(r.mb_dl_mbps) else "–",
        "fixed_reach": f"{r.fixed_reach:.1f}",
        "income": f"RM{r.income_median:,.0f}",
        "takeup": f"{100 * r.share_settlements_takeup_gap:.0f}%" if pd.notna(r.share_settlements_takeup_gap) else "–",
        "small": bool(r.small_sample_flag),
    }

g = copy.deepcopy(geo)
for f in g["features"]:
    f["properties"].update(props.get(f["properties"]["district"], {"cgi": 0, "colour": ui.hex_rgb(ui.MUTED_LIGHT, 120),
                                                                   "fix_label": "no data", "small": False}))
small = {"type": "FeatureCollection", "features": [f for f in g["features"] if f["properties"].get("small")]}

layers = [
    pdk.Layer("GeoJsonLayer", g, extruded=True, wireframe=True, get_elevation="properties.cgi * 60000",
              get_fill_color="properties.colour", get_line_color=[255, 255, 255, 160], pickable=True, auto_highlight=True),
    pdk.Layer("GeoJsonLayer", small, filled=False, stroked=True, get_line_color=ui.hex_rgb(ui.INK, 255),
              line_width_min_pixels=3, pickable=False),
]
tooltip = {"html": "<b>{district}</b><br/>Gap Index {cgi} · need rank {need_rank}<br/>"
                   "Households online {access}<br/>Small sample: {small_sample}<br/>"
                   "Mobile download {mobile} · fixed tests per 1,000 residents {fixed_reach}<br/>"
                   "Median household income {income}<br/>Take-up-gap settlements {takeup}<br/>Colour: {fix_label}",
           "style": {"backgroundColor": "white", "color": ui.INK, "fontSize": "12px"}}
view = pdk.ViewState(latitude=2.6, longitude=113.3, zoom=5.9, pitch=50, bearing=-12)
st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view, map_style=pdk.map_styles.CARTO_LIGHT, tooltip=tooltip),
                height=600)

cats = (["takeup_gap", "tower", "satellite"] if key == "largest_group" else ["tower", "satellite"])
legend = " &nbsp; ".join(f"<span style='display:inline-block;width:12px;height:12px;background:{ui.FIX_COLOURS[c]};"
                         f"border-radius:2px;margin-right:4px'></span>{ui.FIX_LABELS[c]}" for c in cats)
legend += (" &nbsp; <span style='display:inline-block;width:12px;height:12px;border:3px solid #0b0b0b;"
           "margin-right:4px'></span>Small-sample district (low confidence)")
st.markdown(f"<div style='font-size:0.85rem;color:{ui.INK_2}'>{legend}</div>", unsafe_allow_html=True)
weights_txt = ", ".join("{} {}".format(k.replace("_", " "), v["weight"]) for k, v in w.items())
ui.what("Each Sarawak district drawn in 3D: height is the Connectivity Gap Index (0 = best, 1 = worst nationally; "
        f"weights {weights_txt}). "
        + ("Colour shows which group holds most of the district's rural people without home internet: settlements "
           "with a fixed network likely nearby (take-up gap, a proxy), or those needing a tower or satellite."
           if key == "largest_group" else
           "Colour shows the main infrastructure fix for settlements without a fixed network nearby.")
        + " Thick outlines mark districts whose survey estimate rests on a small sample.")

nob = t3[(t3.state == STATE) & (t3.level == "district") & ~t3.district.isin([f["properties"]["district"] for f in geo["features"]])]
if len(nob):
    st.markdown("**Districts with no boundary** (not on the map): " + "; ".join(
        f"{r.district}: {r.internet_pct:.1f}% of households online (DOSM 2025)"
        + (f" ± {r.internet_moe95_pp:.1f} pp" if r.small_sample_flag else "") for r in nob.itertuples())
        + ". No official or open boundary exists yet; its area is drawn inside its neighbour.")

with st.expander("Table view"):
    tv = d.sort_values("rank_sarawak")[["district", "cgi", "rank_sarawak", "rank_sarawak_p05", "rank_sarawak_p95",
                                        "internet_pct", "small_sample_flag", "internet_moe95_pp", "mb_dl_mbps",
                                        "fixed_reach", "income_median", "share_settlements_takeup_gap", "main_fix"]].copy()
    tv["share_settlements_takeup_gap"] = (100 * tv["share_settlements_takeup_gap"]).round(0)
    st.dataframe(tv.rename(columns={
        "district": "District", "cgi": "Gap Index", "rank_sarawak": "Need rank", "rank_sarawak_p05": "Rank p05",
        "rank_sarawak_p95": "Rank p95", "internet_pct": "Households online %", "small_sample_flag": "Small sample",
        "internet_moe95_pp": "MOE (pp)", "mb_dl_mbps": "Mobile Mbps", "fixed_reach": "Fixed tests /1k",
        "income_median": "Median income RM", "share_settlements_takeup_gap": "Take-up settlements %", "main_fix": "Main fix"}),
        hide_index=True, width="stretch")

ui.footer([
    "DOSM ICTHS 2025, Table 3.1 (household access by district); small-sample margins estimated (see Method)",
    f"Speedtest® by Ookla® Global Fixed and Mobile Network Performance Maps, {d.ookla_quarter.iloc[0]} (CC BY-NC-SA 4.0)",
    "DOSM HIES 2024 (income), Population 2026, Census 2020; MOE school list (Jun 2022); costs: config/costs.yaml",
], osm=True, basemap=True)
