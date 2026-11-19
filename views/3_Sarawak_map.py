"""Sarawak map: 3D districts, height = Connectivity Gap Index, colour = fix."""
import copy

import pandas as pd
import pydeck as pdk
import streamlit as st

from app_utils import data, ui

st.set_page_config(page_title="Sarawak map · Beyond Coverage", layout="wide")

STATE = "Sarawak"
# Gentle 3D: the tallest district (Gap Index near 1) rises about a quarter of the map's visible height
# at the initial view below. Tuned with screenshots at 1366 px; change here only.
MAX_BLOCK_M = 40000
VIEW = pdk.ViewState(latitude=2.55, longitude=112.85, zoom=6.05, pitch=40, bearing=0)
MAP_HEIGHT = 560

geo = data.district_geojson(STATE)
dt = data.district_table()
grp = data.settlement_groups()
t3 = data.csv("dosm_hh_ict_district_2025")
w = data.yaml_config("weights")["weights"]

d = dt[dt.state == STATE].merge(grp, on=["state", "district"], how="left")
quarter = d.ookla_quarter.iloc[0]
access_year = int(d.access_year.iloc[0])

ui.page("Sarawak: where the gap is deepest",
        "Taller districts have a larger Connectivity Gap Index. Colour shows which group of rural settlements holds "
        "most people without home internet, or the main infrastructure fix.")

mode = st.radio("Colour districts by",
                ["Largest group of rural people without home internet", "Main infrastructure fix (tower or satellite)"],
                horizontal=True, key="sarawak_colour_mode")
key = "largest_group" if mode.startswith("Largest") else "main_fix"
cats = (["tower", "satellite", "takeup_gap"] if key == "largest_group" else ["tower", "satellite"])
legend = " &nbsp;&nbsp; ".join(
    f"<span style='display:inline-block;width:14px;height:14px;background:{ui.FIX_COLOURS[c]};border-radius:3px;"
    f"vertical-align:-2px;margin-right:5px'></span>{ui.FIX_LABELS[c]}" for c in cats)
legend += (" &nbsp;&nbsp; <span style='display:inline-block;width:14px;height:14px;border:3px solid #0b0b0b;"
           "vertical-align:-3px;margin-right:5px'></span>Small-sample district (low confidence)"
           " &nbsp;&nbsp; Height = Gap Index")
st.markdown(f"<div style='font-size:0.88rem;color:{ui.INK_2};margin:4px 0 6px 0'>{legend}</div>", unsafe_allow_html=True)


def rank_txt(r, base, p05, p95):
    return f"{int(r[base])} (range {int(r[p05])}–{int(r[p95])})" if pd.notna(r[base]) else "–"


props = {}
for _, r in d.iterrows():
    cat = r[key] if isinstance(r[key], str) else None
    props[r.district] = {
        "cgi": round(float(r.cgi), 3),
        "colour": ui.hex_rgb(ui.FIX_COLOURS.get(cat, ui.MUTED_LIGHT), 230),
        "fix_label": ui.FIX_LABELS.get(cat, "–"),
        "need_rank": rank_txt(r, "rank_sarawak", "rank_sarawak_p05", "rank_sarawak_p95"),
        "access": f"{r.internet_pct:.1f}%" + (f" (approx. ± {r.internet_moe95_pp:.1f} pp)" if r.small_sample_flag else ""),
        "small_sample": (f"yes, inferred sample size ~{int(r.implied_sample_n)}: low confidence" if r.small_sample_flag else "no"),
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
    pdk.Layer("GeoJsonLayer", g, extruded=True, wireframe=False, get_elevation=f"properties.cgi * {MAX_BLOCK_M}",
              get_fill_color="properties.colour", pickable=True, auto_highlight=True,
              material={"ambient": 0.55, "diffuse": 0.6, "shininess": 8}),
    # small-sample districts: dark edges drawn on the extruded blocks themselves (visible from above)
    pdk.Layer("GeoJsonLayer", small, extruded=True, filled=False, wireframe=True,
              get_elevation=f"properties.cgi * {MAX_BLOCK_M}", get_line_color=ui.hex_rgb(ui.INK, 255),
              line_width_min_pixels=2, pickable=False),
]
tooltip = {"html": "<b>{district}</b><br/>Gap Index {cgi} · need rank {need_rank}<br/>"
                   f"Households online (DOSM {access_year}) {{access}}<br/>Small sample: {{small_sample}}<br/>"
                   f"Mobile download (Ookla {quarter}) {{mobile}} · fixed tests per 1,000 residents {{fixed_reach}}<br/>"
                   "Median household income {income}<br/>Take-up-gap settlements {takeup}<br/>Colour: {fix_label}",
           "style": {"backgroundColor": "white", "color": ui.INK, "fontSize": "12px"}}
st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=VIEW, map_style=pdk.map_styles.CARTO_LIGHT, tooltip=tooltip),
                height=MAP_HEIGHT, key="sarawak_map")

weights_txt = ", ".join("{} {}".format(k.replace("_", " "), v["weight"]) for k, v in w.items())
ui.what("Each Sarawak district drawn in 3D: height is the Connectivity Gap Index (0 = best, 1 = worst nationally; "
        f"weights {weights_txt}). "
        + ("Colour shows which group holds most of the district's rural people without home internet: settlements with "
           "a fixed network likely nearby (take-up gap, a proxy), or settlements screened for a tower or satellite. "
           + ui.TAKEUP_TXT
           if key == "largest_group" else
           "Colour shows the main infrastructure fix for settlements without a fixed network nearby.")
        + f" Thick outlines mark districts with a small {ui.INFERRED_N} (our estimate, not a DOSM figure).",
        data=f"DOSM ICTHS {access_year} · Ookla {quarter} · HIES 2024 · Census 2020 · MOE school list, June 2022")
ui.caveat()

nob = t3[(t3.state == STATE) & (t3.level == "district") & ~t3.district.isin([f["properties"]["district"] for f in geo["features"]])]
if len(nob):
    st.markdown("**Districts with no boundary** (not on the map): " + "; ".join(
        f"{r.district}: {r.internet_pct:.1f}% of households online (DOSM {access_year})"
        + (f", approx. ± {r.internet_moe95_pp:.1f} pp" if r.small_sample_flag else "") for r in nob.itertuples())
        + ". No official or open boundary exists yet; its area is drawn inside its neighbour.")

with st.expander("Table view"):
    tv = d.sort_values("rank_sarawak")[["district", "cgi", "rank_sarawak", "rank_sarawak_p05", "rank_sarawak_p95",
                                        "internet_pct", "small_sample_flag", "internet_moe95_pp", "mb_dl_mbps",
                                        "fixed_reach", "income_median", "share_settlements_takeup_gap", "main_fix"]].copy()
    tv["share_settlements_takeup_gap"] = (100 * tv["share_settlements_takeup_gap"]).round(0)
    tv["main_fix"] = tv["main_fix"].map(ui.FIX_LABELS)
    st.dataframe(tv.rename(columns={
        "district": "District", "cgi": "Gap Index", "rank_sarawak": "Need rank", "rank_sarawak_p05": "Rank p05",
        "rank_sarawak_p95": "Rank p95", "internet_pct": f"Households online % ({access_year})",
        "small_sample_flag": "Small sample", "internet_moe95_pp": "Approx. MOE (pp)", "mb_dl_mbps": f"Mobile Mbps ({quarter})",
        "fixed_reach": "Fixed tests /1k", "income_median": "Median income RM (2024)",
        "share_settlements_takeup_gap": "Take-up settlements %", "main_fix": "Main fix"}),
        hide_index=True, width="stretch", column_config={"District": st.column_config.TextColumn(width="medium")})
    ui.what("All Sarawak districts on the map, sorted by need.",
            data=f"DOSM ICTHS {access_year} · Ookla {quarter} · HIES 2024 · costing (Census 2020, MOE list June 2022)")

ui.footer([
    f"DOSM ICTHS {access_year}, Table 3.1 (household access by district); {ui.INFERRED_N} and {ui.MOE_TXT} are our "
    "estimates (see Method)",
    f"Speedtest® by Ookla® Global Fixed and Mobile Network Performance Maps, {quarter} (CC BY-NC-SA 4.0)",
    "DOSM HIES 2024 (income), Population 2026, Census 2020; MOE school list (June 2022); costs: config/costs.yaml",
], osm=True, basemap=True)
