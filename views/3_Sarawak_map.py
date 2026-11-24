"""Sarawak map: 3D terrain with rural settlements by fix, or 3D district blocks (height = Gap Index).

?district=<name> opens the map focused on that Sarawak district (used by District detail's "Show on map")."""
import math

import pydeck as pdk
import streamlit as st

from app_utils import data, ui

st.set_page_config(page_title="Sarawak map · Beyond Coverage", layout="wide")

STATE = "Sarawak"
# Gap Index view: the tallest district (Gap Index near 1) rises about a quarter of the map's visible height
# at the initial view. Tuned with screenshots at 1366 px; change here only.
MAX_BLOCK_M = 40000
# Terrain view: heights exaggerated so interior hills read while the coast and plantations stay flat. A district
# view (?district=) is rendered fresh and closer, so it uses a lower value. Tuned with screenshots at 1366 px
# (whole state, Kanowit, Belaga, Kuching at max zoom): x8 looked spiky/crumpled, x4 made Kuching's hills peaky
# up close, x3 made the whole-state relief too faint. Change here only.
TERRAIN_X = 4
TERRAIN_X_DISTRICT = 3
TERRAIN_MAX_ZOOM = 11  # closer than this the 30 m elevation and imagery look crumpled and blurry
SARAWAK_VIEW = dict(latitude=2.55, longitude=112.85, zoom=6.05)            # Gap Index view
SARAWAK_TERRAIN_VIEW = dict(latitude=2.3, longitude=112.75, zoom=6.3)     # tilted terrain view
TERRAIN_PITCH = 50
MAP_HEIGHT = 560
VIEWS = ["3D terrain", "Gap Index blocks"]
HOVER_TINT = ui.hex_rgb(ui.ACCENT, 55)    # hover / clicked district: subtle accent-blue tint
FOCUS_TINT = ui.hex_rgb(ui.ACCENT, 45)    # district opened with ?district=: lighter tint under a thick outline
S = pdk.types.String  # literal string for deck.gl props (pydeck otherwise treats strings as expressions)

geo = data.district_geojson(STATE)
dt = data.district_table()
grp = data.settlement_groups()
w = data.yaml_config("weights")["weights"]
tiles = data.yaml_config("map_tiles")

# only districts that are indexed and have a polygon go on the map; the rest are listed below it
d = dt[(dt.state == STATE) & dt.indexed & dt.has_boundary].merge(grp, on=["state", "district"], how="left")
no_boundary = dt[(dt.state == STATE) & ~dt.has_boundary]
quarter = d.ookla_quarter.iloc[0]
access_year = int(d.access_year.iloc[0])
cyear = data.census_year()

# --- focus district from ?district=... (Sarawak districts with a boundary only)
qp_d = st.query_params.get("district")
focus = qp_d if qp_d in set(d.district) else None
tx = TERRAIN_X_DISTRICT if focus else TERRAIN_X  # exaggeration for this render

ui.page("Sarawak: where the gap is deepest, and why it is hard to reach",
        "Rural settlements on Sarawak's terrain, coloured by the fix our cost screen suggests; or the districts as "
        "blocks whose height is the Connectivity Gap Index.")

# 3D terrain streams many map tiles; phones default to the lighter Gap Index view (switchable).
ua = (st.context.headers.get("User-Agent") or "") if st.context.headers else ""
mobile = any(k in ua for k in ("Mobi", "Android", "iPhone"))
c1, c2 = st.columns([1, 2], vertical_alignment="bottom")
view = c1.radio("Map", VIEWS, index=1 if mobile else 0, horizontal=True, key="sarawak_view",
                help="3D terrain loads elevation and satellite tiles and needs a good connection. The Gap Index view "
                     "is lighter." + (" Phones start on the Gap Index view." if mobile else ""))
terrain = view == VIEWS[0]
if not terrain:
    mode = c2.radio("Colour districts by",
                    ["Largest group of rural people without home internet", "Main infrastructure fix (tower or satellite)"],
                    horizontal=True, key="sarawak_colour_mode")
    key = "largest_group" if mode.startswith("Largest") else "main_fix"
if focus:
    c2.markdown(f"Showing **{focus}**.")
    c2.page_link("views/3_Sarawak_map.py", label="Show all of Sarawak", icon=":material/zoom_out_map:",
                 query_params={})


def swatch(colour: str, label: str, dot: bool = False) -> str:
    shape = "border-radius:50%;border:1.5px solid #fff;" if dot else "border-radius:3px;"
    return (f"<span style='white-space:nowrap'><span style='display:inline-block;width:13px;height:13px;"
            f"background:{colour};{shape}vertical-align:-2px;margin-right:5px'></span>{label}</span>")


if terrain:
    legend = " &nbsp;&nbsp; ".join(swatch(ui.FIX_COLOURS[c], ui.FIX_LABELS[c], dot=True)
                                   for c in ["takeup_gap", "satellite", "tower"])
    legend += (" &nbsp;&nbsp; <span style='white-space:nowrap'><span style='display:inline-block;width:16px;"
               "border-top:2px solid #fff;outline:1px solid #888;vertical-align:3px;margin-right:5px'></span>"
               f"District boundary</span> &nbsp;&nbsp; <span style='white-space:nowrap'>Heights exaggerated ×{tx:g}</span>")
else:
    cats = ["tower", "satellite", "takeup_gap"] if key == "largest_group" else ["tower", "satellite"]
    legend = " &nbsp;&nbsp; ".join(swatch(ui.FIX_COLOURS[c], ui.FIX_LABELS[c]) for c in cats)
    legend += (" &nbsp;&nbsp; <span style='white-space:nowrap'><span style='display:inline-block;width:14px;"
               "height:14px;border:3px solid #0b0b0b;vertical-align:-3px;margin-right:5px'></span>Small-sample district "
               "(low confidence)</span> &nbsp;&nbsp; <span style='white-space:nowrap'>Height = Gap Index</span>")
st.markdown(f"<div style='font-size:0.88rem;color:{ui.INK_2};margin:4px 0 6px 0'>{legend}</div>", unsafe_allow_html=True)


def is_small(r) -> bool:
    return bool(r.small_sample_flag) if ui.isnum(r.small_sample_flag) else False


def round_coords(c, nd: int = 4):
    """Round nested coordinate lists (4 decimals ~ 10 m) to shrink what is sent to the browser."""
    return [round_coords(x, nd) for x in c] if isinstance(c[0], list) else [round(v, nd) for v in c]


def flat_points(c):
    return [p for x in c for p in flat_points(x)] if isinstance(c[0][0], list) else c


props = {}
for _, r in d.iterrows():
    small_r = is_small(r)
    need = ui.rank_range(r.rank_sarawak, r.rank_sarawak_p05, r.rank_sarawak_p95)
    access = (ui.fmt_pct(r.internet_pct)
              + (f" (approx. ± {r.internet_moe95_pp:.1f} pp)" if small_r and ui.isnum(r.internet_moe95_pp) else ""))
    p = {"cgi": round(float(r.cgi), 3) if ui.isnum(r.cgi) else 0.0, "small": small_r,
         "focus": r.district == focus}
    if terrain:
        # tooltip fields are plain text (deck.gl escapes them); the markup lives in the tooltip template
        p.update({"t0": f"{r.district} (district)", "t1": f"Gap Index {p['cgi']} · Sarawak need rank {need}",
                  "t2": f"Households online (DOSM {access_year}) {access}",
                  "t3": "Small sample: low confidence" if small_r else ""})
    else:
        cat = r[key] if isinstance(r[key], str) else None
        p.update({
            "colour": ui.hex_rgb(ui.FIX_COLOURS.get(cat, ui.MUTED_LIGHT), 230),
            "fix_label": ui.FIX_LABELS.get(cat, ui.DASH), "need_rank": need, "access": access,
            "small_sample": ((f"yes, inferred sample size ~{int(r.implied_sample_n)}: low confidence"
                              if ui.isnum(r.implied_sample_n) else "yes: low confidence") if small_r else "no"),
            "mobile": ui.fmt_num(r.mb_dl_mbps, ".0f", suffix=" Mbps"),
            "fixed_reach": ui.fmt_num(r.fixed_reach, ".1f"),
            "income": ui.fmt_num(r.income_median, ",.0f", prefix="RM"),
            "takeup": ui.fmt_num(100 * r.share_settlements_takeup_gap if ui.isnum(r.share_settlements_takeup_gap)
                                 else None, ".0f", suffix="%"),
        })
    props[r.district] = p

# send only the properties the map and tooltip use
features, focus_pts = [], []
for f in geo["features"]:
    name = f["properties"]["district"]
    if name not in props:
        continue
    coords = round_coords(f["geometry"]["coordinates"])
    features.append({"type": "Feature", "properties": {"district": name, **props[name]},
                     "geometry": {"type": f["geometry"]["type"], "coordinates": coords}})
    if name == focus:
        focus_pts = flat_points(coords)
g = {"type": "FeatureCollection", "features": features}
small = {"type": "FeatureCollection", "features": [f for f in features if f["properties"]["small"]]}
focused = {"type": "FeatureCollection", "features": [f for f in features if f["properties"]["focus"]]}

# --- camera: tilted over Sarawak, or over the focus district
if focus_pts:
    lons, lats = [p[0] for p in focus_pts], [p[1] for p in focus_pts]
    span = max(max(lons) - min(lons), (max(lats) - min(lats)) * 1.6)  # map is wider than tall
    zoom = max(6.0, min(10.5, math.log2(360 / max(span, 1e-3)) - 0.6))
    cam = dict(latitude=(min(lats) + max(lats)) / 2, longitude=(min(lons) + max(lons)) / 2, zoom=zoom)
else:
    cam = dict(SARAWAK_TERRAIN_VIEW if terrain else SARAWAK_VIEW)
    if mobile:  # portrait screens: zoom out one step so the whole state fits across
        cam["zoom"] -= 1
VIEW = pdk.ViewState(**cam, pitch=TERRAIN_PITCH if terrain else 40, bearing=0,
                     **({"max_zoom": TERRAIN_MAX_ZOOM} if terrain else {}))

if terrain:
    el, im = tiles["elevation"], tiles["imagery"]
    k = tx
    dec = el["decoder"]
    terrain_ext = [{"@@type": "TerrainExtension"}]
    pts = data.settlement_points(STATE).copy()
    pts["colour"] = [ui.hex_rgb(ui.FIX_COLOURS.get(c, ui.MUTED_LIGHT), 245) for c in pts.category_main]
    pts["t0"] = "Rural settlement, " + pts["district"]
    pts["t1"] = ["Fix: " + ui.FIX_LABELS.get(c, ui.DASH) for c in pts.category_main]
    pts["t2"] = ["Estimated people without home internet: " + ui.fmt_num(v) for v in pts.unconnected_people]
    pts["t3"] = ["Estimated 5-year cost (main case): "
                 + ("not costed (take-up support)" if c == "takeup_gap" else ui.fmt_rm(v))
                 for c, v in zip(pts.category_main, pts.cost_main)]
    pts = pts[["lon", "lat", "colour", "t0", "t1", "t2", "t3"]]
    layers = [
        # dark backdrop under the terrain so far-away tiles that have not loaded yet do not show as white gaps
        pdk.Layer("PolygonLayer", [{"p": [[95, -15], [135, -15], [135, 25], [95, 25]]}], id="backdrop",
                  get_polygon="p", get_fill_color=[22, 36, 58], stroked=False, pickable=False),
        pdk.Layer("TerrainLayer", id="terrain", elevation_data=S(el["url"]), texture=S(im["url"]),
                  elevation_decoder={"rScaler": dec["r"] * k, "gScaler": dec["g"] * k, "bScaler": dec["b"] * k,
                                     "offset": dec["offset"] * k},
                  max_zoom=min(el["max_zoom"], im["max_zoom"]), mesh_max_error=4, operation=S("terrain+draw"),
                  pickable=False),
        # district boundaries draped on the terrain. The fill is invisible (alpha 1) but keeps districts hoverable and
        # clickable; hover and click use a light accent-blue tint (a pale/white tint reads as snow on the forest)
        pdk.Layer("GeoJsonLayer", g, id="districts", filled=True, stroked=True, get_fill_color=[255, 255, 255, 1],
                  get_line_color=[255, 255, 255, 200], line_width_min_pixels=1.2, pickable=True, auto_highlight=True,
                  highlight_color=HOVER_TINT, extensions=terrain_ext, terrain_draw_mode=S("drape")),
        # selected district (?district=): thicker accent outline and a light accent tint
        pdk.Layer("GeoJsonLayer", focused, id="focus", filled=True, stroked=True, get_fill_color=FOCUS_TINT,
                  get_line_color=ui.hex_rgb(ui.ACCENT, 255), line_width_min_pixels=3.5, pickable=False,
                  extensions=terrain_ext, terrain_draw_mode=S("drape")),
        # settlements sit on the terrain surface (TerrainExtension offset mode); billboard dots face the camera and
        # skip the depth test so a neighbouring slope never hides or cuts them
        pdk.Layer("ScatterplotLayer", pts, id="settlements", get_position=["lon", "lat"], get_fill_color="colour",
                  get_radius=6 if focus else 4, radius_units=S("pixels"), radius_min_pixels=3, stroked=True,
                  get_line_color=[255, 255, 255, 255], line_width_units=S("pixels"), get_line_width=1.5,
                  line_width_min_pixels=1.5, pickable=True, auto_highlight=True,
                  extensions=terrain_ext, terrain_draw_mode=S("offset"), billboard=True,
                  parameters={"depthCompare": "always", "depthWriteEnabled": False}),
    ]
    tooltip = {"html": "<b>{t0}</b><br/>{t1}<br/>{t2}<br/>{t3}", "style": {"backgroundColor": "white", "color": ui.INK, "fontSize": "12px"}}
    deck = pdk.Deck(layers=layers, initial_view_state=VIEW, map_style=None, tooltip=tooltip)
else:
    layers = [
        pdk.Layer("GeoJsonLayer", g, id="districts", extruded=True, wireframe=False,
                  get_elevation=f"properties.cgi * {MAX_BLOCK_M}", get_fill_color="properties.colour", pickable=True,
                  auto_highlight=True, highlight_color=ui.hex_rgb(ui.ACCENT, 160), material={"ambient": 0.55, "diffuse": 0.6, "shininess": 8}),
        # small-sample districts: dark edges drawn on the extruded blocks themselves (visible from above)
        pdk.Layer("GeoJsonLayer", small, extruded=True, filled=False, wireframe=True,
                  get_elevation=f"properties.cgi * {MAX_BLOCK_M}", get_line_color=ui.hex_rgb(ui.INK, 255),
                  line_width_min_pixels=2, pickable=False),
        pdk.Layer("GeoJsonLayer", focused, extruded=True, filled=False, wireframe=True,
                  get_elevation=f"properties.cgi * {MAX_BLOCK_M}", get_line_color=ui.hex_rgb(ui.ACCENT, 255),
                  line_width_min_pixels=4, pickable=False),
    ]
    tooltip = {"html": "<b>{district}</b><br/>Gap Index {cgi} · need rank {need_rank}<br/>"
                       f"Households online (DOSM {access_year}) {{access}}<br/>Small sample: {{small_sample}}<br/>"
                       f"Mobile download (Ookla {quarter}) {{mobile}} · fixed tests per 1,000 residents {{fixed_reach}}<br/>"
                       "Median household income {income}<br/>Take-up-gap settlements {takeup}<br/>Colour: {fix_label}",
               "style": {"backgroundColor": "white", "color": ui.INK, "fontSize": "12px"}}
    deck = pdk.Deck(layers=layers, initial_view_state=VIEW, map_style=pdk.map_styles.CARTO_LIGHT, tooltip=tooltip)

event = st.pydeck_chart(deck, height=MAP_HEIGHT, key=f"sarawak_map_{view}_{focus}", on_select="rerun",
                        selection_mode="single-object")
if terrain:  # the imagery licence asks for the credit on the map interface itself
    st.markdown(f"<div style='font-size:0.72rem;color:{ui.MUTED};margin-top:-0.6rem'>{tiles['imagery']['attribution']}"
                f" · {tiles['elevation']['attribution']} · Boundaries {ui.OSM_CREDIT} (ODbL)</div>",
                unsafe_allow_html=True)

# --- click a district or a settlement (or pick one) to open its detail page
picked = None
try:
    sel = event.selection["objects"]
    objs = sel.get("districts", [])
    if objs:
        picked = objs[0]["properties"]["district"]
except (AttributeError, KeyError, TypeError, IndexError):
    picked = None
by_need = d.sort_values("rank_sarawak").district.tolist()
default = picked or focus
p1, p2 = st.columns([2, 1], vertical_alignment="bottom")
choice = p1.selectbox("Click a district on the map, or pick one here (sorted by need, highest first)", by_need,
                      index=by_need.index(default) if default in by_need else 0, key=f"sarawak_pick_{default}")
if p2.button(f"Open {choice} in District detail", icon=":material/arrow_forward:", width="stretch"):
    ui.go_to_district(STATE, choice)

weights_txt = ", ".join("{} {}".format(k_.replace("_", " "), v["weight"]) for k_, v in w.items())
if terrain:
    ui.what("Sarawak's terrain (satellite image on elevation, heights exaggerated "
            f"×{tx:g}) with every rural settlement (one per rural MOE school) as a dot. Colour is the fix our cost "
            "screen suggests: green where our proxy suggests a fixed network is likely nearby (take-up support), "
            "orange for satellite, blue for a tower. Hills and forest are why many inland settlements are far from "
            "any network and costly to reach. Hover a dot for the estimated people without home internet and cost. "
            + ui.TAKEUP_TXT,
            data=f"MOE school list, June 2022 · Census {cyear if cyear else ui.DASH} · DOSM ICTHS {access_year} · "
                 f"Ookla {quarter} · config/costs.yaml · {tiles['imagery']['name']} · Terrain Tiles")
else:
    ui.what("Each Sarawak district drawn in 3D: height is the Connectivity Gap Index (0 = best, 1 = worst nationally; "
            f"weights {weights_txt}). "
            + ("Colour shows which group holds most of the district's rural people without home internet: settlements "
               "with a fixed network likely nearby (take-up gap, a proxy), or settlements screened for a tower or "
               "satellite. " + ui.TAKEUP_TXT
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
    tv = d.sort_values("rank_sarawak").copy()
    tv["need"] = [ui.rank_short(r, a, b) for r, a, b in zip(tv.rank_sarawak, tv.rank_sarawak_p05, tv.rank_sarawak_p95)]
    # margin of error only where the sample is small (elsewhere DOSM's figure has no inferred margin)
    tv["moe_small"] = tv.internet_moe95_pp.where(tv.small_sample_flag.fillna(False).astype(bool))
    tv["takeup_pct"] = 100 * tv.share_settlements_takeup_gap
    tv["fix"] = tv.main_fix.map(ui.FIX_LABELS)
    # fixed tests per 1,000 people and income are in the district tooltip and on District detail
    ui.table(tv, [
        ("district", "District", None),
        ("cgi", "Gap Index", ".3f", "Connectivity Gap Index, 0 = best, 1 = worst nationally"),
        ("need", "Need rank", lambda v: v, "Sarawak need rank (5th–95th percentile range over random index weightings)"),
        ("internet_pct", "Online (%)", ".1f", f"Households with internet access, DOSM ICTHS {access_year} (%)"),
        ("moe_small", "± MOE (pp)", ".1f", "Approximate margin of error (simple random-sampling formula), our estimate; "
                                           "shown only for small-sample districts"),
        ("mb_dl_mbps", "Mobile (Mbps)", ".1f", f"Mobile download speed, Ookla {quarter}, test-weighted mean (Mbps)"),
        ("takeup_pct", "Take-up (%)", ".0f", "Share of rural settlements where our proxy suggests a fixed network is "
                                             "likely nearby (take-up gap)"),
        ("fix", "Main fix", None, "Fix serving most rural people without home internet among planned settlements"),
    ])
    ui.what("All Sarawak districts on the map, sorted by need. Need rank range: 5th–95th percentile over random "
            "index weightings. Margin of error: our approximate estimate, shown only for small-sample districts.",
            data=f"DOSM ICTHS {access_year} · Ookla {quarter} · HIES 2024 · costing (Census 2020, MOE list June 2022)")

ui.next_step("views/5_Priorities.py", "Priorities",
             "compare every district on need and on estimated beneficiaries per RM1m.")
ui.footer([
    f"DOSM ICTHS {access_year}, Table 3.1 (household access by district); {ui.INFERRED_N} and {ui.MOE_TXT} are our "
    "estimates (see Method)",
    f"Speedtest® by Ookla® Global Fixed and Mobile Network Performance Maps, {quarter} (CC BY-NC-SA 4.0)",
    "DOSM HIES 2024 (income), Population 2026, Census 2020; MOE school list (June 2022); costs: config/costs.yaml",
    f"{tiles['imagery']['attribution']}",
    f"{tiles['elevation']['attribution']}",
], osm=True, basemap=not terrain)
