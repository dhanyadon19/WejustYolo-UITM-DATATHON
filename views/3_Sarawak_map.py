"""Sarawak map: 3D terrain with rural settlements by settlement type, or 3D district blocks (height = Need score).

?district=<name> opens the map focused on that Sarawak district (used by District profile's "Show on map")."""
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
VIEWS = ["3D terrain", "Need score blocks"]
# District fills are draped on the terrain (rendered into a texture laid over the mesh). Keep every draped fill a
# very faint accent blue, never white or pale: if a GPU/driver blends that texture's alpha wrongly, a light fill turns
# into an opaque pale-grey/lavender patch in the district's shape, while a faint blue fill stays a faint blue.
# Some GPUs draw ANY non-zero alpha on a draped fill as fully opaque (a solid blue or pale patch hiding the terrain),
# while alpha 0 stays invisible. So in the terrain view no district fill is ever visible: the selected or clicked
# district gets a thick accent outline only, and hover has no tint (deck.gl's hover highlight recolours the fill too,
# and an outline cannot follow the mouse from Python); the tooltip names the district under the pointer.
PICK_FILL = ui.hex_rgb(ui.ACCENT, 0)      # invisible fill that keeps districts hoverable and clickable
OUTLINE_PX = 4                            # selected / clicked district outline
# Terrain fallbacks. deck.gl draws a terrain tile whose imagery has not loaded (slow or blocked by the imagery server)
# in the layer's base colour, white by default, which reads as a pale-grey faceted patch: use a dark forest tone.
TERRAIN_BASE = [34, 44, 36]
TERRAIN_TILE_MAX_ZOOM = 12   # view stops at 11; fewer, coarser tiles = fewer bursts to the imagery server
TERRAIN_MAX_REQUESTS = 4     # parallel tile requests (deck.gl default 6); the imagery server throttles bursts
MAP_BG = "#16243a"           # dark map background: never an empty white box before or without a deck.gl frame
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

_si = data.csv("dosm_hh_internet_state")
_sy = int(_si["year"].max())
_sr = _si[(_si.year == _sy) & (_si.state == "Sarawak") & (_si.indicator == "internet") & (_si.strata == "rural")]["pct"]
_off = (100 - float(_sr.iloc[0])) / 100 if len(_sr) else float("nan")
st.title(f"Rural Sarawak: {ui.about_one_in(_off)} homes offline" if ui.isnum(_off) else "Sarawak map")
st.markdown(f"<div style='color:{ui.INK_2};margin-top:-0.6rem;display:flex;gap:10px;flex-wrap:wrap;align-items:center'>"
            f"<span>Sarawak: where the gap is deepest, and why it is hard to reach"
            + (f" ({100 * _off:.1f}% of rural households without internet, DOSM {_sy})" if ui.isnum(_off) else "")
            + "</span></div>", unsafe_allow_html=True)
st.markdown(f"<p style='color:{ui.INK_2}'>Rural settlements on Sarawak's terrain, coloured by settlement type (candidate "
            "technologies, screening); or the districts as blocks whose height is the Need score.</p>",
            unsafe_allow_html=True)

# 3D terrain streams many map tiles; phones default to the lighter Gap Index view (switchable).
ua = (st.context.headers.get("User-Agent") or "") if st.context.headers else ""
mobile = any(k in ua for k in ("Mobi", "Android", "iPhone"))
c1, c2 = st.columns([1, 2], vertical_alignment="bottom")
view = c1.radio("Map", VIEWS, index=1 if mobile else 0, horizontal=True, key="sarawak_view",
                help="3D terrain loads elevation and satellite tiles and needs a good connection. The Need score view "
                     "is lighter." + (" Phones start on the Need score view." if mobile else ""))
terrain = view == VIEWS[0]
if not terrain:
    mode = c2.radio("Colour districts by",
                    ["Largest group of rural people without home internet", "Share of settlements needing take-up support"],
                    horizontal=True, key="sarawak_colour_mode")
    # (a "main infrastructure fix" mode was dropped: after the costing fix every Sarawak district's main fix is the
    # same, so it carried no information)
    key = "largest_group" if mode.startswith("Largest") else "takeup_share"
if focus:
    c2.markdown(f"Showing **{focus}**.")
    c2.page_link("views/3_Sarawak_map.py", label="Show all of Sarawak", icon=":material/zoom_out_map:",
                 query_params={})


def swatch(colour: str, label: str, dot: bool = False) -> str:
    shape = "border-radius:50%;border:1.5px solid #fff;" if dot else "border-radius:3px;"
    return (f"<span style='white-space:nowrap'><span style='display:inline-block;width:13px;height:13px;"
            f"background:{colour};{shape}vertical-align:-2px;margin-right:5px'></span>{label}</span>")


if terrain:
    present = set(data.settlement_points(STATE).settlement_type.dropna())
    type_labels = data.yaml_config("settlement_types")["types"]
    legend = "<b>Rural settlement (school location)</b>, by settlement type: &nbsp; " + " &nbsp;&nbsp; ".join(
        swatch(ui.TYPE_COLOURS[t], f"{t}. {type_labels[t]['label'] if t in type_labels else 'Not classified (missing data)'}",
               dot=True) for t in ui.TYPE_ORDER if t in present)
    legend += (" &nbsp;&nbsp; <span style='white-space:nowrap'><span style='display:inline-block;width:16px;"
               "border-top:2px solid #fff;outline:1px solid #888;vertical-align:3px;margin-right:5px'></span>"
               f"District boundary</span> &nbsp;&nbsp; <span style='white-space:nowrap'>Heights exaggerated ×{tx:g}</span>")
else:
    if key == "largest_group":
        used = [c for c in ["A", "E", "new"] if (d.largest_group == c).any()]
        legend = ("<b>Where most rural people without home internet live</b>, by settlement type: &nbsp; "
                  + " &nbsp;&nbsp; ".join(swatch(ui.GROUP_COLOURS[c], ui.GROUP_LABELS[c]) for c in used))
        if d.largest_group.isna().any():
            legend += " &nbsp; " + swatch(ui.MUTED_LIGHT, "No rural school")
    else:
        nb = len(ui.TAKEUP_RAMP)
        legend = ("<b>Rural settlements needing take-up support</b> (fixed network likely nearby, proxy): &nbsp; "
                  + " &nbsp; ".join(swatch(c, f"{100 * i // nb}–{100 * (i + 1) // nb}%")
                                    for i, c in enumerate(ui.TAKEUP_RAMP)))
        if d.share_settlements_takeup_gap.isna().any():
            legend += " &nbsp; " + swatch(ui.MUTED_LIGHT, "No rural school")
    legend += (" &nbsp;&nbsp; <span style='white-space:nowrap'><span style='display:inline-block;width:14px;"
               "height:14px;border:3px solid #0b0b0b;vertical-align:-3px;margin-right:5px'></span>Small-sample district "
               "(low confidence)</span> &nbsp;&nbsp; <span style='white-space:nowrap'>Height = Need score</span>")
st.markdown(f"<div style='font-size:0.88rem;color:{ui.INK_2};margin:4px 0 6px 0'>{legend}</div>", unsafe_allow_html=True)

# Streamlit downloads its map code (deck.gl, ~3 MB) the first time a map appears in a browser session, e.g. after
# "Show on map" from District detail, which has no map. Until it arrives the map element does not exist and the space
# was an empty white box. The map therefore sits in a keyed container that is always there, at the map's height, with
# a background and a loading message; the map covers it once drawn. It is created before the
# layers are built so the box appears at once.
bg, ink = (MAP_BG, "#c9d3e0") if terrain else ("#eceae4", ui.INK_2)
st.markdown(f"""<style>
.st-key-sarawak_map_box {{ background:{bg}; border-radius:8px; min-height:{MAP_HEIGHT}px; position:relative; }}
.st-key-sarawak_map_box .map-loading {{ position:absolute; top:0; left:0; right:0; height:{MAP_HEIGHT}px;
  display:flex; align-items:center; justify-content:center; color:{ink}; font-size:0.95rem; }}
[data-testid='stDeckGlJsonChart'] {{ background:{bg}; border-radius:8px; }}
</style>""", unsafe_allow_html=True)
# Streamlit draws a container only once it has content: the loading message goes in first (absolutely positioned,
# so it takes no space) and the map is drawn over it later
map_box = st.container(key="sarawak_map_box", gap=None)
map_box.markdown(f"<div class='map-loading'>Loading the {'3D ' if terrain else ''}map…</div>", unsafe_allow_html=True)


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
              + (f" (±{r.internet_moe95_pp:.0f} points, low confidence)" if small_r and ui.isnum(r.internet_moe95_pp) else ""))
    p = {"cgi": round(float(r.cgi), 3) if ui.isnum(r.cgi) else 0.0, "small": small_r,
         "focus": r.district == focus}
    if terrain:
        # tooltip fields are plain text (deck.gl escapes them); the markup lives in the tooltip template
        p.update({"t0": f"{r.district} (district)", "t1": f"Need score {p['cgi']} · Sarawak need rank {need}",
                  "t2": f"Households online (DOSM {access_year}) {access}",
                  "t3": "Small sample: low confidence" if small_r else ""})
        # districts share the tooltip template with the settlements: every field it names must exist (empty here),
        # or deck.gl prints the raw placeholder; empty fields sit in <div>s, which collapse
        p.update({f"t{i}": "" for i in range(4, 8)})
    else:
        if key == "largest_group":
            cat = r[key] if isinstance(r[key], str) else None
            colour = ui.GROUP_COLOURS.get(cat, ui.MUTED_LIGHT)
            label = (ui.GROUP_LABELS[cat] + ": the largest share of rural people without home internet (estimate)"
                     if cat in ui.GROUP_LABELS else "no rural school")
        else:
            b = ui.ramp_bin(r.share_settlements_takeup_gap)
            colour = ui.MUTED_LIGHT if b is None else ui.TAKEUP_RAMP[b]
            label = ("no rural school" if b is None else
                     f"{100 * r.share_settlements_takeup_gap:.0f}% of rural settlements need take-up support")
        p.update({
            "colour": ui.hex_rgb(colour, 230),
            "fix_label": label, "need_rank": need, "access": access,
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
# Streamlit restyles a map with a selection: the selected object is filled at full opacity (a solid patch) and every
# other object is dimmed. So a selection never stays: clicking a district focuses it like ?district= (outline only),
# and any click gives the chart a new key, which drops the selection and its styling.
st.session_state.setdefault("sarawak_map_nonce", 0)
map_key = f"sarawak_map_{view}_{focus}_{st.session_state['sarawak_map_nonce']}"


def _on_map_click() -> None:
    try:
        objs = st.session_state[map_key]["selection"]["objects"]
        st.query_params["district"] = objs["districts"][0]["properties"]["district"]
    except (KeyError, IndexError, TypeError):
        pass  # a settlement or empty space: nothing to focus
    st.session_state["sarawak_map_nonce"] += 1

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
    pts["colour"] = [ui.hex_rgb(ui.TYPE_COLOURS.get(t, ui.MUTED_LIGHT), 245) for t in pts.settlement_type]
    # the settlement is anchored on a rural MOE school: name it (MOE name, short form)
    pts["t0"] = ["Rural settlement near " + ui.school_short(n) + ", " + d + " district" if isinstance(n, str)
                 else "Rural settlement in " + d + " district" for n, d in zip(pts.school_name, pts.district)]
    pts["t1"] = [f"Type {t}. {lab}" if isinstance(lab, str) else ui.DASH for t, lab in zip(pts.settlement_type, pts.type_label)]
    pts["t2"] = ["Candidate technologies (screening): " + (c if isinstance(c, str) else ui.DASH)
                 for c in pts.candidate_technologies]
    mq = {"good": "good", "weak": "weak", "few_tests": "too few tests to judge", "no_tests": "no tests within 2 km"}
    pts["t3"] = ["Mobile signal (Ookla): " + mq.get(q, ui.DASH)
                 + (f" ({int(n):,} tests within 2 km, mean {mbps:,.0f} Mbps)" if q in ("good", "weak", "few_tests") else "")
                 for q, n, mbps in zip(pts.mobile_quality, pts.mobile_tests_2km, pts.mobile_dl_mbps_2km)]
    pts["t4"] = [f"Terrain: {t} (mean slope {sl:.0f}°)" if isinstance(t, str) else "Terrain: missing"
                 for t, sl in zip(pts.terrain, pts.slope_mean_deg)]
    pts["t5"] = [f"Road: {r.replace('_', ' ')} ({'under 0.1' if km < 0.1 else f'{km:,.1f}'} km to nearest mapped road)"
                 if isinstance(r, str)
                 else "Road: missing" for r, km in zip(pts.road, pts.road_km)]
    pts["t6"] = ["Estimated people without home internet (district average): " + ui.fmt_num(v)
                 for v in pts.unconnected_people]
    # satellite cost = terminals for unconnected households + one Business terminal for the school (costs.yaml);
    # where the school's link is most of the cost, say so
    sat_cfg = data.yaml_config("costs")["satellite"]
    school_link = sat_cfg["kit_rm"] + 60 * sat_cfg["monthly_rm"]["business_from"]
    pts["t7"] = ["Five-year cost (estimate): "
                 + (("none (no households here lack home internet)" if round(v) == 0
                     else f"{ui.fmt_rm(v)}, {ui.cost_basis_short(b_)}") if bool(ok) and ui.isnum(v) else ui.NOT_COSTED)
                 + (f"; includes the school's satellite link ({ui.fmt_rm(school_link)})"
                    if t == "D" and ui.isnum(v) and v > 0 and school_link / v > 0.5 else "")
                 for t, ok, v, b_ in zip(pts.settlement_type, pts.type_costed, pts.type_cost_5yr_rm, pts.type_cost_basis)]
    pts = pts[["lon", "lat", "colour"] + [f"t{i}" for i in range(8)]]
    layers = [
        # dark backdrop under the terrain so far-away tiles that have not loaded yet do not show as white gaps
        pdk.Layer("PolygonLayer", [{"p": [[95, -15], [135, -15], [135, 25], [95, 25]]}], id="backdrop",
                  get_polygon="p", get_fill_color=[22, 36, 58], stroked=False, pickable=False),
        pdk.Layer("TerrainLayer", id="terrain", elevation_data=S(el["url"]), texture=S(im["url"]),
                  elevation_decoder={"rScaler": dec["r"] * k, "gScaler": dec["g"] * k, "bScaler": dec["b"] * k,
                                     "offset": dec["offset"] * k},
                  max_zoom=min(el["max_zoom"], im["max_zoom"], TERRAIN_TILE_MAX_ZOOM), max_requests=TERRAIN_MAX_REQUESTS,
                  color=TERRAIN_BASE, mesh_max_error=4, operation=S("terrain+draw"),
                  pickable=False),
        # district boundaries draped on the terrain. The fill is invisible (alpha 0) but keeps districts hoverable and
        # clickable; no hover highlight (it would tint the fill, see PICK_FILL)
        pdk.Layer("GeoJsonLayer", g, id="districts", filled=True, stroked=True, get_fill_color=PICK_FILL,
                  get_line_color=[255, 255, 255, 200], line_width_min_pixels=1.2, pickable=True, auto_highlight=False,
                  extensions=terrain_ext, terrain_draw_mode=S("drape")),
        # selected district (?district=, the picker or a click): thick accent outline only, no fill
        pdk.Layer("GeoJsonLayer", focused, id="focus", filled=False, stroked=True,
                  get_line_color=ui.hex_rgb(ui.ACCENT, 255), line_width_min_pixels=OUTLINE_PX, pickable=False,
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
    tooltip = {"html": "<div><b>{t0}</b></div><div><b>{t1}</b></div>"
                       + "".join(f"<div>{{t{i}}}</div>" for i in range(2, 8)), "style": {"backgroundColor": "white", "color": ui.INK, "fontSize": "12px"}}
    # dark, label-free basemap under the terrain: if the terrain is slow or fails, the box is dark, not Streamlit's
    # default light basemap (which looked like an empty white map)
    deck = pdk.Deck(layers=layers, initial_view_state=VIEW, map_style=pdk.map_styles.CARTO_DARK_NO_LABELS,
                    tooltip=tooltip)
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
    tooltip = {"html": "<b>{district}</b><br/>Need score {cgi} · need rank {need_rank}<br/>"
                       f"Households online (DOSM {access_year}) {{access}}<br/>Small sample: {{small_sample}}<br/>"
                       f"Mobile download (Ookla {quarter}) {{mobile}} · fixed tests per 1,000 residents {{fixed_reach}}<br/>"
                       "Median household income {income}<br/>Take-up-gap settlements {takeup}<br/>Colour: {fix_label}",
               "style": {"backgroundColor": "white", "color": ui.INK, "fontSize": "12px"}}
    deck = pdk.Deck(layers=layers, initial_view_state=VIEW, map_style=pdk.map_styles.CARTO_LIGHT, tooltip=tooltip)

with map_box:
    st.pydeck_chart(deck, height=MAP_HEIGHT, key=map_key, on_select=_on_map_click, selection_mode="single-object")
if terrain:  # the imagery licence asks for the credit on the map interface itself
    st.markdown(f"<div style='font-size:0.72rem;color:{ui.MUTED};margin-top:-0.6rem'>{tiles['imagery']['attribution']}"
                f" · {tiles['elevation']['attribution']} · Boundaries {ui.OSM_CREDIT} (ODbL) · {ui.BASEMAP_CREDIT}<br/>"
                "Map empty or partly grey? Terrain and imagery come from public tile servers and can be slow; wait a few "
                "seconds, reload the page, or switch to Need score blocks.</div>", unsafe_allow_html=True)

# --- the focused district (?district=, a click on the map, or picked here) can be opened in District detail
by_need = d.sort_values("rank_sarawak").district.tolist()
default = focus
p1, p2 = st.columns([2, 1], vertical_alignment="bottom")
pick_key = f"sarawak_pick_{default}"


def _focus_picked() -> None:
    """Picking a district moves the map to it, as ?district= does (callbacks run before the rerun)."""
    st.query_params["district"] = st.session_state[pick_key]


choice = p1.selectbox("Click a district on the map, or pick one here to zoom to it (sorted by need, highest first)",
                      by_need, index=by_need.index(default) if default in by_need else 0, key=pick_key,
                      on_change=_focus_picked)
if p2.button(f"Open {choice} in District profile", icon=":material/arrow_forward:", width="stretch"):
    ui.go_to_district(STATE, choice)

weights_txt = ", ".join("{} {}".format(k_.replace("_", " "), v["weight"]) for k_, v in w.items())
if terrain:
    ui.what([f"Sarawak's terrain: satellite image on elevation, heights exaggerated ×{tx:g}.",
             "Each dot is a rural settlement (school location): a rural MOE school standing for the village around it.",
             "Colour = settlement type, from simple rules on fixed network nearby, demand, mobile signal, terrain and "
             "road distance (all proxies; see Method & limitations).",
             "Hover a dot for its type, candidate technologies (screening), mobile signal, terrain, road distance, "
             "estimated people without home internet and five-year cost where costed.",
             "Hills and forest help explain why many inland settlements are far from any network and costly to reach.",
             ui.TAKEUP_TXT],
            data=f"MOE school list, June 2022 · Census {cyear if cyear else ui.DASH} · DOSM ICTHS {access_year} · "
                 f"Ookla {quarter} · OpenStreetMap {data.osm_snapshot()} · config/costs.yaml · "
                 f"{tiles['imagery']['name']} · Terrain Tiles")
else:
    ui.what([f"Each Sarawak district in 3D: height = Need score (Connectivity Gap Index; 0 = best, 1 = worst nationally; "
             f"weights {weights_txt}).",
             ("Colour = the settlement-type group holding most of the district's estimated rural people without home "
              "internet: network nearby (A: take-up support), good mobile signal nearby (E: home broadband over the "
              "mobile network), or new infrastructure (B, C, D). Proxy-based estimates."
              if key == "largest_group" else
              "Colour = share of rural settlements with a fixed network likely nearby (Ookla fixed tile within 2 km "
              "of the school, a proxy), where take-up support may come first; darker = larger share."),
             ui.TAKEUP_TXT,
             f"Thick outlines = small {ui.INFERRED_N} (our estimate, not a DOSM figure)."],
            data=f"DOSM ICTHS {access_year} · Ookla {quarter} · HIES 2024 · Census 2020 · MOE school list, June 2022")
ui.caveat()

if len(no_boundary):
    st.markdown("**Districts with no boundary** (not on the map): " + "; ".join(
        f"{r.district}: {ui.fmt_pct(r.internet_2025)} of households online (DOSM {access_year})"
        + (f" (±{r.internet_moe95_pp_2025:.0f} points)" if ui.isnum(r.internet_moe95_pp_2025) else "")
        for r in no_boundary.itertuples())
        + ". No official or open boundary exists yet; its area is drawn inside its neighbour.")

with st.expander("Table view"):
    tv = d.sort_values("rank_sarawak").copy()
    tv["need"] = [ui.rank_short(r, a, b) for r, a, b in zip(tv.rank_sarawak, tv.rank_sarawak_p05, tv.rank_sarawak_p95)]
    # margin of error only where the sample is small (elsewhere DOSM's figure has no inferred margin)
    tv["moe_small"] = tv.internet_moe95_pp.where(tv.small_sample_flag.fillna(False).astype(bool))
    # settlement types (proxy-based), not the tower-vs-satellite cost screen: that lives in District profile
    # (Reference cost tab) and on Where to invest
    tv = tv.merge(data.district_type_mix(), on=["state", "district"], how="left")
    tv["top_type_txt"] = [f"{t}. {lab} ({100 * sh:.0f}%)" if isinstance(t, str) else ui.DASH
                          for t, lab, sh in zip(tv.top_type, tv.top_type_label, tv.top_share)]
    tv["servable_pct"] = 100 * tv.servable_share
    # fixed tests per 1,000 people and income are in the district tooltip and on District detail
    ui.table(tv, [
        ("district", "District", None),
        ("cgi", "Need score", ".3f", ui.NEED_TECH),
        ("need", "Need rank", lambda v: v, "Sarawak need rank (5th–95th percentile range over random index weightings)"),
        ("internet_pct", "Online (%)", ".1f", f"Households with internet access, DOSM ICTHS {access_year} (%)"),
        ("moe_small", "± MOE (pp)", ".1f", "Approximate margin of error (simple random-sampling formula), our estimate; "
                                           "shown only for small-sample districts"),
        ("mb_dl_mbps", "Mobile (Mbps)", ".1f", f"Mobile download speed, Ookla {quarter}, test-weighted mean (Mbps)"),
        ("top_type_txt", "Most common type", None, "Most common settlement type among the district's rural "
                                                  "settlements (one per rural MOE school), with its share (for type A "
                                                  "this is the take-up share); proxy-based estimate"),
        ("servable_pct", "A + E (%)", ".0f", "Share of rural settlements servable through existing networks "
                                                         "(types A + E: take-up support or home broadband over the "
                                                         "mobile network), proxy-based estimate"),
    ], download="beyond_coverage_sarawak_districts.csv", notes=[
        "Beyond Coverage: Sarawak districts on the map, sorted by need (Need score = Connectivity Gap Index).",
        "Need rank range: 5th-95th percentile over 1,000 random index weightings. MOE (pp): our approximate margin of "
        "error (simple random-sampling formula), shown only for small-sample districts; not a DOSM figure.",
        "Most common settlement type and A + E (%) (servable through existing networks) are ESTIMATES from proxies "
        "(take-up = an Ookla fixed tile within 2 km; types from config/settlement_types.yaml).",
        f"Data: DOSM ICTHS {access_year}; Ookla {quarter}; HIES 2024; Census 2020; MOE school list June 2022; "
        "config/costs.yaml.",
    ])
    ui.what("All Sarawak districts on the map, sorted by need. Need rank range: 5th–95th percentile over random "
            "index weightings. Margin of error: our approximate estimate, shown only for small-sample districts.",
            data=f"DOSM ICTHS {access_year} · Ookla {quarter} · HIES 2024 · costing (Census 2020, MOE list June 2022)")

ui.next_step("views/4_District_detail.py", "District profile",
             "open one district: what to do first, its settlements, households, Need score and reference cost.")
ui.footer([
    f"DOSM ICTHS {access_year}, Table 3.1 (household access by district); {ui.INFERRED_N} and {ui.MOE_TXT} are our "
    "estimates (see Method)",
    f"Speedtest® by Ookla® Global Fixed and Mobile Network Performance Maps, {quarter} (CC BY-NC-SA 4.0)",
    "DOSM HIES 2024 (income), Population 2026, Census 2020; MOE school list (June 2022); costs: config/costs.yaml",
    f"{tiles['imagery']['attribution']}",
    f"{tiles['elevation']['attribution']}",
], osm=True, basemap=True)
