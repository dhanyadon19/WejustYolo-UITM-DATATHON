"""Schools: Hansard figures, MOE school map, optional low-confidence screening layer."""
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

from app_utils import data, ui

st.set_page_config(page_title="Schools · Beyond Coverage", layout="wide")

h = data.csv("hansard_schools")
schools = data.csv("schools_all")
conn = data.csv("schools_connectivity")
val = data.csv("schools_validation")
quarter = conn["ookla_quarter"].iloc[0]
HANSARD = "Hansard, Dewan Rakyat, 11 Nov 2026"
MOE_LIST = "MOE school list, June 2022"

total = h[h.state.str.startswith("Total")].iloc[0]
by_state = h[~h.state.str.startswith("Total")].sort_values("schools_without_fibre")

ui.page("Schools without fibre",
        f"Parliament was told on 11 Nov 2026 that {int(total.schools_without_fibre):,} of {int(total.schools_total):,} "
        f"schools ({int(total.pct_without_fibre)}%) in six states are not yet on fibre.")

# --- Hansard by state
_top = by_state.sort_values("schools_without_fibre").iloc[-1]
ui.finding(f"{_top.state} has the most schools without fibre: {int(_top.schools_without_fibre):,} "
           f"({int(_top.pct_without_fibre)}% of its schools)", "Schools without fibre, by state (Hansard)", conf="solid")
fig = go.Figure(go.Bar(
    x=by_state.schools_without_fibre, y=by_state.state, orientation="h",
    marker_color=[ui.ACCENT if s == "Sarawak" else ui.MUTED_LIGHT for s in by_state.state], marker_line_width=0,
    text=[f"{int(n):,} ({int(p)}%)" for n, p in zip(by_state.schools_without_fibre, by_state.pct_without_fibre)],
    textposition="outside", textfont=dict(color=ui.INK_2), cliponaxis=False,
    customdata=by_state[["pct_without_fibre", "schools_total", "schools_total_min", "schools_total_max"]],
    hovertemplate="%{y}: %{x:,} schools without fibre (%{customdata[0]}% of schools)<br>"
                  "Total schools (derived from rounded %): ~%{customdata[1]:,} "
                  "(range %{customdata[2]:,}–%{customdata[3]:,})<extra></extra>"))
ui.style(fig, height=330, legend=False, margin=dict(l=10, r=60, t=30, b=10))
fig.update_xaxes(title="Schools without fibre", range=[0, by_state.schools_without_fibre.max() * 1.2])
st.plotly_chart(fig, width="stretch")
ui.what(["Schools without fibre in each state, as stated in Parliament (share of the state's schools in brackets).",
         "These schools use wireless broadband or satellite instead.",
         "State totals in the tooltip come from rounded percentages, so they are approximate."], data=HANSARD,
        conf="solid")

# --- Map
_v = val[val.state.str.startswith("Total")].iloc[0]
ui.finding(f"Our screen finds {int(_v.est_2km):,} schools vs Parliament's {int(_v.hansard_no_fibre):,} "
           f"({_v.pct_diff_2km:+.0f}%): use it to screen, never to count",
           "Where the schools are, and how our screening layer compares with Parliament", conf="low")
c1, c2 = st.columns([1, 2])
state = c1.selectbox("State", ["All six Hansard states"] + data.SIX_STATES + ["All Malaysia"], index=0)
screen = c2.toggle("Screening layer (low confidence): no fixed broadband nearby", value=False,
                   help=f"Schools with no Ookla fixed tile within 2 km ({quarter}). A screen, not a count: see the table.")

pts = schools.dropna(subset=["lon", "lat"]).copy()
if state == "All six Hansard states":
    pts = pts[pts.state.isin(data.SIX_STATES)]
elif state != "All Malaysia":
    pts = pts[pts.state == state]
pts["students"] = pts["students"].fillna(0).astype(int)
pts["district"] = pts["district"].fillna("(not placed)")
# send only the columns the layer and tooltip use, coordinates rounded to ~1 m
MAP_COLS = ["lon", "lat", "school_name", "district", "level", "urban_rural", "students"]
layers = [pdk.Layer("ScatterplotLayer", data=pts[MAP_COLS].round({"lon": 5, "lat": 5}),
                    get_position="[lon, lat]", get_fill_color=ui.hex_rgb(ui.MUTED, 150), get_radius=250,
                    radius_min_pixels=1.5, radius_max_pixels=5, pickable=True)]
flag = conn[(conn.likely_no_fibre == True) & conn.lon.notna()]  # noqa: E712
if state not in ("All six Hansard states", "All Malaysia"):
    flag = flag[flag.state == state]
if screen:
    f = flag[["lon", "lat", "school_name", "district", "level", "urban_rural", "students", "nearest_fixed_tile_km",
              "confidence"]].copy()
    f["students"] = f["students"].fillna(0).astype(int)
    f["nearest_fixed_tile_km"] = f["nearest_fixed_tile_km"].round(1)
    f = f.round({"lon": 5, "lat": 5})
    layers.append(pdk.Layer("ScatterplotLayer", data=f, get_position="[lon, lat]",
                            get_fill_color=ui.hex_rgb(ui.ACCENT, 230), get_line_color=[255, 255, 255, 255],
                            stroked=True, line_width_min_pixels=1, get_radius=600, radius_min_pixels=3.5,
                            radius_max_pixels=9, pickable=True))
if pts.empty:
    ui.fallback("No schools with coordinates in this selection.")
    st.stop()
view = pdk.data_utils.compute_view(pts[["lon", "lat"]].values.tolist(), view_proportion=0.95)
tooltip = {"html": "<b>{school_name}</b><br/>{district} · {level} · {urban_rural}<br/>{students} pupils"
                   + ("<br/>Nearest fixed tile: {nearest_fixed_tile_km} km · confidence {confidence}" if screen else ""),
           "style": {"backgroundColor": "white", "color": ui.INK, "fontSize": "12px"}}

left, right = st.columns([1, 1], gap="medium")
with left:
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view, map_style=pdk.map_styles.CARTO_LIGHT,
                             tooltip=tooltip), height=520, key=f"schools_map_{state}")
    msg = (f"Grey: {len(pts):,} MOE schools."
           + (f" Blue: {len(flag):,} schools with no Ookla fixed tile within 2 km: a low-confidence screen, not a count "
              "of schools without fibre." if screen else ""))
    ui.what(msg, data=MOE_LIST + (f" · Ookla {quarter}" if screen else ""), conf="low" if screen else "solid")
with right:
    st.markdown("**Does the screening layer match Parliament?**")
    pct = lambda v: f"{v:+,.0f}%" if ui.isnum(v) else ""  # noqa: E731
    ui.table(val, [
        ("state", "State", None),
        ("hansard_no_fibre", "Hansard", ",.0f", "Schools without fibre, as stated in Parliament"),
        ("est_2km", "Screen", ",.0f", "Schools with no Ookla fixed tile within 2 km (low-confidence screen)"),
        ("pct_diff_2km", "Diff 2 km", pct, "Screen (2 km) vs Hansard, % difference"),
        ("pct_diff_1km", "Diff 1 km", pct, "Screen (1 km) vs Hansard, % difference"),
    ])
    tot = val[val.state.str.startswith("Total")].iloc[0]
    conf = conn[conn.likely_no_fibre == True]["confidence"].value_counts()  # noqa: E712
    ui.what([f"2 km screen: {int(tot.est_2km):,} schools vs Parliament's {int(tot.hansard_no_fibre):,} "
             f"({tot.pct_diff_2km:+.1f}%).",
             f"1 km total looks close ({tot.pct_diff_1km:+.1f}%) only because state errors cancel out.",
             f"Flagged schools by confidence (mobile tests nearby): {int(conf.get('low', 0)):,} low, "
             f"{int(conf.get('medium', 0)):,} medium, {int(conf.get('high', 0)):,} high.",
             "Use it to screen, never to count."],
            data=f"{HANSARD} · {MOE_LIST} · Ookla {quarter}", conf="low")

ui.next_step("views/5_Priorities.py", "Where to invest",
             "compare districts on need and people reached per RM1m, and try the budget planner.")
ui.footer([
    "Hansard, Dewan Rakyat, 11 Nov 2026, oral question 11 (DR-11112026, p.33)",
    "Ministry of Education, Senarai Sekolah Rendah dan Menengah (as at 30 Jun 2022)",
    f"Speedtest® by Ookla® Global Fixed and Mobile Network Performance Maps, {quarter} (CC BY-NC-SA 4.0)",
], basemap=True)
