"""Sarawak map: 3D districts, height = Connectivity Gap Index, colour = fix."""
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
w = data.yaml_config("weights")["weights"]

# only districts that are indexed and have a polygon go on the map; the rest are listed below it
d = dt[(dt.state == STATE) & dt.indexed & dt.has_boundary].merge(grp, on=["state", "district"], how="left")
no_boundary = dt[(dt.state == STATE) & ~dt.has_boundary]
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


def is_small(r) -> bool:
    return bool(r.small_sample_flag) if ui.isnum(r.small_sample_flag) else False


props = {}
for _, r in d.iterrows():
    cat = r[key] if isinstance(r[key], str) else None
    small_r = is_small(r)
    props[r.district] = {
        "cgi": round(float(r.cgi), 3) if ui.isnum(r.cgi) else 0.0,
        "colour": ui.hex_rgb(ui.FIX_COLOURS.get(cat, ui.MUTED_LIGHT), 230),
        "fix_label": ui.FIX_LABELS.get(cat, ui.DASH),
        "need_rank": ui.rank_range(r.rank_sarawak, r.rank_sarawak_p05, r.rank_sarawak_p95),
        "access": ui.fmt_pct(r.internet_pct)
                  + (f" (approx. ± {r.internet_moe95_pp:.1f} pp)" if small_r and ui.isnum(r.internet_moe95_pp) else ""),
        "small_sample": ((f"yes, inferred sample size ~{int(r.implied_sample_n)}: low confidence"
                          if ui.isnum(r.implied_sample_n) else "yes: low confidence") if small_r else "no"),
        "mobile": ui.fmt_num(r.mb_dl_mbps, ".0f", suffix=" Mbps"),
        "fixed_reach": ui.fmt_num(r.fixed_reach, ".1f"),
        "income": ui.fmt_num(r.income_median, ",.0f", prefix="RM"),
        "takeup": ui.fmt_num(100 * r.share_settlements_takeup_gap if ui.isnum(r.share_settlements_takeup_gap) else None,
                             ".0f", suffix="%"),
        "small": small_r,
    }


def round_coords(c, nd: int = 4):
    """Round nested coordinate lists (4 decimals ~ 10 m) to shrink what is sent to the browser."""
    return [round_coords(x, nd) for x in c] if isinstance(c[0], list) else [round(v, nd) for v in c]


# send only the properties the map and tooltip use
features = []
for f in geo["features"]:
    name = f["properties"]["district"]
    if name not in props:
        continue
    features.append({"type": "Feature", "properties": {"district": name, **props[name]},
                     "geometry": {"type": f["geometry"]["type"], "coordinates": round_coords(f["geometry"]["coordinates"])}})
g = {"type": "FeatureCollection", "features": features}
small = {"type": "FeatureCollection", "features": [f for f in features if f["properties"]["small"]]}
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

if len(no_boundary):
    st.markdown("**Districts with no boundary** (not on the map): " + "; ".join(
        f"{r.district}: {ui.fmt_pct(r.internet_2025)} of households online (DOSM {access_year})"
        + (f", approx. ± {r.internet_moe95_pp_2025:.1f} pp" if ui.isnum(r.internet_moe95_pp_2025) else "")
        for r in no_boundary.itertuples())
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
