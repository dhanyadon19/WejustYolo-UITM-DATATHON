"""District detail: one district's access, speeds, context, need ranks, fixes and cost."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app_utils import data, ui

st.set_page_config(page_title="District detail · Beyond Coverage", layout="wide")

dt = data.district_table()
w = data.yaml_config("weights")["weights"]
quarter = dt["ookla_quarter"].dropna().iloc[0]
access_year = int(dt["access_year"].dropna().iloc[0])
n_indexed = int(dt["indexed"].sum())
host_of = data.unmapped_host()

ui.page("District detail", "Everything we know about one district, with its uncertainty.")

# Preselection: from the Sarawak map / Priorities (session state) or a shared link (?state=...&district=...)
qp = st.query_params
states = sorted(dt.state.unique())
first_load = "sel_state" not in st.session_state
want_state = st.session_state.pop("detail_state", None) or (qp.get("state") if first_load else None)
want_district = st.session_state.pop("detail_district", None) or (qp.get("district") if first_load else None)
if want_state in states:
    st.session_state["sel_state"] = want_state
st.session_state.setdefault("sel_state", "Sarawak")

c1, c2 = st.columns(2)
state = c1.selectbox("State", states, key="sel_state")
opts = dt[dt.state == state].sort_values(["rank_national", "district"], na_position="last").district.tolist()
if want_district in opts:
    st.session_state["sel_district"] = want_district
if st.session_state.get("sel_district") not in opts:
    st.session_state["sel_district"] = opts[0]
district = c2.selectbox("District (sorted by need, highest first)", opts, key="sel_district")
st.query_params.update(state=state, district=district)  # shareable link to this district
r = dt[(dt.state == state) & (dt.district == district)].iloc[0]
host = host_of.get((state, district))

# --- 0. Action plan (summary card; the small-sample and no-boundary warnings live inside it)
fb = data.fix_breakdown()
fixes = {row.category: row for row in fb[(fb.state == state) & (fb.district == district)].itertuples()}
fixes = {k: {"n": v.n, "people": v.people, "cost_main": v.cost_main, "cost_lite": v.cost_lite} for k, v in fixes.items()}
cyear = data.census_year()
ui.action_plan(
    r, fixes, n_national=n_indexed, n_state=int(dt[(dt.state == state) & dt.indexed].shape[0]), host=host,
    sources=f"DOSM ICTHS {access_year} · Ookla {quarter} · Census {cyear if cyear else ui.DASH} · MOE school list, "
            f"June 2022 · OpenStreetMap {data.osm_snapshot()} · Terrain Tiles · config/costs.yaml",
    on_host_click=ui.go_to_district, types=data.district_types(state, district))

# --- download: the action plan, one row per rural settlement (estimates, with their sources in the file)
sett = data.district_settlements(state, district)
if len(sett):
    TAKEUP_FIX = "Take-up support (fixed network likely nearby, proxy)"

    def fix_txt(c):
        return TAKEUP_FIX if c == "takeup_gap" else ui.FIX_LABELS.get(c, c)

    def rm(c, v):  # take-up settlements carry no infrastructure cost: left empty, not 0
        return None if c == "takeup_gap" or not ui.isnum(v) else round(float(v))

    plan = pd.DataFrame({
        "state": sett.state, "district": sett.district, "school_code": sett.school_code,
        "settlement_school_name": sett.school_name, "school_name_short": [ui.school_short(n) for n in sett.school_name],
        "longitude": sett.lon, "latitude": sett.lat,
        "fixed_network_nearby_proxy": ["yes" if bool(v) else "no" for v in sett.fixed_nearby],
        "fix_main": [fix_txt(c) for c in sett.category_main],
        "est_households": sett.households.round(1),
        "est_households_without_home_internet": sett.unconnected_households.round(1),
        "est_people_without_home_internet": sett.unconnected_people.round(0).astype("Int64"),
        "est_5yr_cost_main_rm": pd.array([rm(c, v) for c, v in zip(sett.category_main, sett.cost_main)], dtype="Int64"),
        "fix_lite": [fix_txt(c) for c in sett.category_lite],
        "est_5yr_cost_lite_rm": pd.array([rm(c, v) for c, v in zip(sett.category_lite, sett.cost_lite)], dtype="Int64"),
    })
    at = data.settlements()
    at = at[(at.state == state) & (at.district == district)].set_index("school_code").reindex(sett.school_code)
    plan = plan.assign(
        settlement_type=at.settlement_type.values, settlement_type_label=at.type_label.values,
        candidate_technologies_screening=at.candidate_technologies.values,
        mobile_quality_proxy=at.mobile_quality.values, mobile_tests_2km=at.mobile_tests_2km.values,
        terrain_slope_class=at.terrain.values,
        mobile_dl_mbps_2km=at.mobile_dl_mbps_2km.round(1).values,
        terrain_proxy=at.terrain.values, slope_mean_deg=at.slope_mean_deg.round(1).values,
        road_proxy=at.road.values, road_km=at.road_km.round(2).values,
        type_cost_basis=at.type_cost_basis.values,
        est_5yr_type_cost_rm=pd.array([round(float(v)) if ui.isnum(v) else None for v in at.type_cost_5yr_rm], dtype="Int64"))
    ui.download_csv(plan, f"beyond_coverage_{ui.slug(district)}_action_plan.csv", "Download action plan (CSV)", [
        f"Beyond Coverage: action plan for {district}, {state}. One row per rural settlement (one per rural MOE school).",
        "ESTIMATES ONLY: a cost screen, not a funding recommendation or a full cost-benefit comparison.",
        f"Households: Census {cyear if cyear else ui.DASH} rural households split equally across the district's rural "
        f"schools; without home internet = households x DOSM ICTHS {access_year} access gap; people = x household size.",
        f"fixed_network_nearby_proxy: an Ookla {quarter} fixed tile within 2 km (a proxy). These settlements need take-up "
        "support, not infrastructure, so their cost is left empty.",
        "Costs: five-year, RM, from config/costs.yaml (retail prices and public statements). Main = Residential satellite "
        "plan, Lite = Residential Lite plan; satellite cost includes one Business terminal for the school.",
        "settlement_type: rule-based screening (config/settlement_types.yaml); candidate technologies are a screening "
        "list, not a recommendation. mobile_quality: all Ookla mobile tiles within 2 km combined, judged only with at least 20 tests, vs the JENDELA 35 Mbps target; "
        "terrain: mean slope within 500 m (Terrain Tiles); road: straight-line km to the nearest motorable OSM road. "
        "All proxies. est_5yr_type_cost_rm is empty where there is no public cost source.",
        f"Data: MOE school list June 2022; Census {cyear if cyear else ui.DASH}; DOSM ICTHS {access_year}; Ookla {quarter}; "
        f"OpenStreetMap {data.osm_snapshot()} (ODbL); Terrain Tiles (AWS Open Data).",
    ], key="dl_action_plan")

# --- 1. Household access 2024 / 2025
st.subheader("Households with internet")
if not (ui.isnum(r.internet_2024) or ui.isnum(r.internet_2025)):
    ui.fallback("No DOSM household access figure for this district.")
else:
    a1, a2, a3 = st.columns([1, 1, 2], gap="medium")
    a1.metric("DOSM 2024", ui.fmt_pct(r.internet_2024))
    ui.moe_badge(a1, r.internet_moe95_pp_2024)
    a2.metric("DOSM 2025", ui.fmt_pct(r.internet_2025),
              delta=f"{r.internet_change_pp:+.1f} pp" if ui.isnum(r.internet_change_pp) else None)
    ui.moe_badge(a2, r.internet_moe95_pp_2025)
    if pd.notna(r.change_beyond_noise):
        a2.caption("Change is larger than the approximate margin of error." if bool(r.change_beyond_noise)
                   else "Change is within the approximate margin of error: not a measurable trend.")
    with a3:
        fig = go.Figure()
        for yr, col in ((2024, ui.MUTED), (2025, ui.ACCENT)):
            v, moe = r[f"internet_{yr}"], r[f"internet_moe95_pp_{yr}"]
            if not ui.isnum(v):
                continue
            fig.add_trace(go.Scatter(x=[v], y=[str(yr)], mode="markers", marker=dict(size=12, color=col),
                                     error_x=dict(type="data", array=[moe if ui.isnum(moe) else 0], color=col, thickness=2, width=6),
                                     hovertemplate=f"{yr}: %{{x:.1f}}%" + (f" ± {moe:.1f} pp" if ui.isnum(moe) else "") + "<extra></extra>",
                                     showlegend=False))
        ui.style(fig, height=160, legend=False, margin=dict(l=10, r=20, t=10, b=10))
        fig.update_xaxes(ticksuffix="%", title=None)
        fig.update_yaxes(type="category", categoryorder="array", categoryarray=["2025", "2024"])
        st.plotly_chart(fig, width="stretch")
ui.what(["Share of households with internet access (DOSM ICTHS Table 3.1).",
         "Error bars = our approximate 95% margin of error (simple random-sampling formula, inferred sample size), "
         "shown only where the sample is small.",
         "DOSM does not publish these margins: they are our estimates."],
        data="DOSM ICTHS 2024 and 2025, Table 3.1")

# --- 2. Speeds
st.subheader(f"Measured speeds (Ookla, {quarter})")
if not ui.isnum(r.mb_dl_mbps) and not ui.isnum(r.fx_dl_mbps):
    ui.fallback("No Ookla speeds: no map boundary" + (f" (its tests are counted under {host})." if host else ".")
                if not r.has_boundary else "No Ookla tests were assigned to this district.")
else:
    s1, s2, s3 = st.columns(3)
    s1.metric("Mobile download", ui.fmt_num(r.mb_dl_mbps, ".0f", suffix=" Mbps"),
              help=f"Test-weighted mean of {ui.fmt_int(r.mb_tests)} tests")
    s2.metric("Mobile upload", ui.fmt_num(r.mb_ul_mbps, ".0f", suffix=" Mbps"))
    s3.metric("Mobile latency (median)", ui.fmt_num(r.mb_latency_median_ms, ".0f", suffix=" ms"))
    s4, s5, s6 = st.columns(3)
    s4.metric("Fixed download", ui.fmt_num(r.fx_dl_mbps, ".0f", suffix=" Mbps"),
              help=f"Test-weighted mean of {ui.fmt_int(r.fx_tests)} tests")
    s5.metric("Fixed upload", ui.fmt_num(r.fx_ul_mbps, ".0f", suffix=" Mbps"))
    s6.metric("Fixed tests per 1,000 residents", ui.fmt_num(r.fixed_reach, ".1f"),
              help="A proxy for how many homes use fixed broadband")
    notes = []
    if r.fx_low_sample is True or r.fx_low_sample == 1:
        notes.append(f"only {ui.fmt_int(r.fx_tests)} fixed tests (low sample)")
    if r.mb_low_sample is True or r.mb_low_sample == 1:
        notes.append(f"only {ui.fmt_int(r.mb_tests)} mobile tests (low sample)")
    ui.what("Speeds from user-run Speedtest results in the district. Fixed speeds come only from homes that already "
            "have fixed broadband, so a fast fixed speed does not mean wide coverage." + (" Note: " + "; ".join(notes) + "." if notes else ""),
            data=f"Ookla {quarter}; population 2026")

# --- 3. Context
st.subheader("Context")


def yr(v) -> str:
    return f" ({int(v)})" if ui.isnum(v) else ""


k1, k2, k3 = st.columns(3)
k4, k5 = st.columns([1, 2])
k1.metric(f"Median household income{yr(r.income_year)}", ui.fmt_num(r.income_median, ",.0f", prefix="RM"))
k2.metric(f"Households with electricity{yr(r.amenities_year)}", ui.fmt_pct(r.electricity))
k3.metric(f"Population{yr(r.population_year)}", ui.fmt_num(r.population_k * 1000 if ui.isnum(r.population_k) else None, ",.0f"))
k4.metric("Pupils in MOE schools (June 2022)", ui.fmt_num(r.students, ",.0f"))
k5.metric("People without home internet (estimate)", ui.fmt_num(r.people_without_home_internet, ",.0f"),
          help="Population × share of households without internet; assumes individuals follow the household rate.")
if not r.indexed:
    ui.fallback("Income, population, pupils and people without home internet are only compiled for districts with a "
                "map boundary.")
ctx_sources = [f"HIES {int(r.income_year)}" if ui.isnum(r.income_year) else "",
               f"OpenDOSM amenities {int(r.amenities_year)}" if ui.isnum(r.amenities_year) else "",
               f"population {int(r.population_year)}" if ui.isnum(r.population_year) else "",
               "MOE school list, June 2022", f"DOSM ICTHS {access_year}"]
ui.what("Background indicators for the district.", data=" · ".join(s for s in ctx_sources if s))

# --- 4. Need
st.subheader("Need: Connectivity Gap Index")
if not r.indexed:
    ui.fallback("Not in the Gap Index: without a map boundary there are no Ookla indicators for this district.")
else:
    n1, n2 = st.columns([1, 2])
    with n1:
        st.metric("Gap Index (0 best – 1 worst)", ui.fmt_num(r.cgi, ".2f"))
        st.markdown(f"**National need rank:** {ui.fmt_int(r.rank_national)} of {n_indexed}  \n"
                    f"Range under 1,000 random weightings: {ui.range_text(r.rank_national_dirichlet_p05, r.rank_national_dirichlet_p95)}  \n"
                    f"With equal weights: {ui.fmt_int(r.rank_national_equal)}"
                    + (f"  \nWithin the approximate margin of error: {ui.range_text(r.rank_national_moe_min, r.rank_national_moe_max)}"
                       if ui.isnum(r.rank_national_moe_min) else ""))
        if state == "Sarawak":
            st.markdown(f"**Sarawak need rank:** {ui.rank_range(r.rank_sarawak, r.rank_sarawak_p05, r.rank_sarawak_p95)}"
                        + (f"; within the approximate margin of error {ui.range_text(r.rank_sarawak_moe_min, r.rank_sarawak_moe_max)}"
                           if ui.isnum(r.rank_sarawak_moe_min) else ""))
    with n2:
        lab = {"access_gap": "Household access gap", "mobile_speed": "Slow mobile", "fixed_reach": "Low fixed reach (proxy)",
               "low_income": "Low income"}
        ks = [k for k in lab if ui.isnum(r[f"{k}_norm"])]
        fig = go.Figure(go.Bar(y=[lab[k] for k in ks], x=[r[f"{k}_norm"] for k in ks], orientation="h",
                               marker_color=ui.ACCENT, marker_line_width=0,
                               text=[f"{r[f'{k}_norm']:.2f} × weight {w[k]['weight']}" for k in ks], textposition="outside",
                               textfont=dict(color=ui.INK_2), hovertemplate="%{y}: %{x:.2f}<extra></extra>"))
        ui.style(fig, height=230, legend=False)
        fig.update_xaxes(range=[0, 1.35], title="Normalised score (1 = worst district nationally)")
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, width="stretch")
        ui.what("The four indicators behind the Gap Index, each scaled 0–1 across all districts (1 = worst), with the "
                "weight each carries.",
                data=f"DOSM ICTHS {access_year} · Ookla {quarter} · HIES {ui.fmt_int(r.income_year).replace(',', '')} · "
                     f"population {ui.fmt_int(r.population_year).replace(',', '')}")

# --- 5. Fixes and cost
st.subheader("Rural settlements: cost screen (estimates)")
if not r.has_boundary:
    ui.fallback("No settlements costed: no map boundary" + (f" (its rural schools are counted under {host})." if host else "."))
elif not ui.isnum(r.rural_settlements):
    st.info(f"{district} has no rural MOE school, so no settlements are costed.")
else:
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Rural settlements", ui.fmt_int(r.rural_settlements), help="One settlement per rural MOE school.")
    f2.metric("Take-up gap (proxy)",
              f"{ui.fmt_int(r.n_takeup_gap)} ({ui.fmt_num(100 * r.share_settlements_takeup_gap if ui.isnum(r.share_settlements_takeup_gap) else None, '.0f')}%)",
              help=f"Settlements where our proxy suggests a fixed network is likely nearby (an Ookla fixed tile within "
                   f"2 km); an estimated {ui.fmt_num(r.takeup_gap_people_without_internet, ',.0f')} rural people without "
                   "home internet. Not costed as infrastructure.")
    f3.metric("Towers", ui.fmt_int(r.n_tower))
    f4.metric("Satellite settlements", ui.fmt_int(r.n_satellite))
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("5-year cost, main (Residential)", ui.fmt_rm(r.cost_main_rm))
    g2.metric("5-year cost, Lite plan", ui.fmt_rm(r.cost_lite_rm))
    g3.metric("Upper bound (cost sensitivity)", ui.fmt_rm(r.cost_upper_bound_rm),
              help="Adds one fibre PoP per take-up-gap settlement, capex only. A cost sensitivity, not a recommendation.")
    g4.metric("Main fix", ui.FIX_LABELS.get(r.main_fix, r.main_fix) if isinstance(r.main_fix, str) else ui.DASH)
    if ui.isnum(r.people_per_rm_m_main):
        st.markdown(f"**Estimated beneficiaries per RM1m:** {r.people_per_rm_m_main:,.0f} rural people without home "
                    f"internet reached per RM1m (national rank {ui.fmt_int(r.value_rank_national)}"
                    + (f", Sarawak {int(r.value_rank_sarawak)}" if ui.isnum(r.value_rank_sarawak) else "")
                    + f"); {ui.fmt_num(r.students_per_rm_m_main, ',.0f')} pupils per RM1m. Whole-district figure: "
                    f"{ui.fmt_num(r.people_per_rm_m_district_main, ',.0f')} people per RM1m (includes people the plan does not reach).")
    elif not ui.isnum(r.cost_main_rm) or r.cost_main_rm == 0:
        ui.fallback("No infrastructure cost: all settlements are in the take-up group, so there is no estimated-"
                    "beneficiaries-per-RM1m figure. " + ui.TAKEUP_TXT)
    ui.what(["Each rural school stands for one settlement.",
             "Ookla fixed tile within 2 km = take-up gap (proxy), not costed.",
             "The rest get a tower if enough households without home internet make it cheaper than satellite over "
             "five years; otherwise satellite.",
             "All costs are estimates. " + ui.TAKEUP_TXT],
            data=f"MOE school list, June 2022 · Census 2020 · DOSM ICTHS {access_year} · Ookla {quarter} · config/costs.yaml")
    ui.caveat()

# --- 6. Every settlement, sortable (MOE school names; attributes are proxies, people are estimates)
at_d = data.settlements()
at_d = at_d[(at_d.state == state) & (at_d.district == district)].reset_index(drop=True)
if len(at_d):
    st.subheader(f"Settlements in {district} ({len(at_d):,})")
    MQ = {"good": "Good", "weak": "Weak", "few_tests": "Too few tests", "no_tests": "No tests"}
    tb = pd.DataFrame({
        "School": [ui.school_short(n) for n in at_d.school_name],
        "Type": at_d.settlement_type.values,
        "Offline (est.)": at_d.unconnected_people.round(0).astype("Int64").values,
        "Mobile signal (2 km)": [MQ.get(q, q) + (f": {int(n):,} test{'' if n == 1 else 's'}, {v:,.0f} Mbps"
                                                 if n > 0 and ui.isnum(v) else "")
                                 for q, n, v in zip(at_d.mobile_quality, at_d.mobile_tests_2km, at_d.mobile_dl_mbps_2km)],
        "Terrain": at_d.terrain.str.capitalize().values,
        "Road (km)": at_d.road_km.round(2).values,
        "Candidate technologies (screening)": at_d.candidate_technologies.values,
    }).sort_values(["Type", "Offline (est.)"], ascending=[True, False],
                   key=lambda c: c.map({k: i for i, k in enumerate(ui.TYPE_ORDER)}) if c.name == "Type" else c)
    tb["Type"] = [f"{t}. {lab}" for t, lab in zip(tb["Type"], at_d.loc[tb.index, "type_label"])]
    st.dataframe(tb, hide_index=True, width="stretch", height=min(36 * (len(tb) + 1) + 4, 460), column_config={
        "School": st.column_config.TextColumn(pinned=True, help="Each rural MOE school stands for "
                                                                  "its village (MOE school list, June 2022)."),
        "Type": st.column_config.TextColumn(help="Settlement type (config/settlement_types.yaml): screening rules, "
                                                 "not a survey."),
        "Offline (est.)": st.column_config.NumberColumn(format="localized", help="People offline (estimate): rural people "
                                                               "without home internet in this settlement."),
        "Mobile signal (2 km)": st.column_config.TextColumn(help="All Ookla mobile tiles within 2 km combined: tests "
                                                                 "and test-weighted mean download. Judged good or weak "
                                                                 "only with at least 20 tests (proxy)."),
        "Terrain": st.column_config.TextColumn(help="Mean slope within 500 m (Terrain Tiles): flat, hilly or steep."),
        "Road (km)": st.column_config.NumberColumn(format="%.2f", help="Straight-line distance to the nearest "
                                                   "motorable OpenStreetMap road."),
        "Candidate technologies (screening)": st.column_config.TextColumn(width="medium"),
    })
    ui.download_csv(tb.assign(**{"Mobile tests (2 km)": at_d.loc[tb.index, "mobile_tests_2km"].values,
                                 "Mobile Mbps (2 km)": at_d.loc[tb.index, "mobile_dl_mbps_2km"].round(1).values,
                                 "MOE school name": at_d.loc[tb.index, "school_name"].values,
                                 "School code": at_d.loc[tb.index, "school_code"].values}),
                    f"beyond_coverage_{ui.slug(district)}_settlements.csv", "Download this table (CSV)", [
        f"Beyond Coverage: rural settlements in {district}, {state}; one per rural MOE school (MOE list, June 2022).",
        "ESTIMATES and PROXIES: people offline = Census households x DOSM access gap; mobile = Ookla "
        f"{quarter} tiles within 2 km (judged only with >= 20 tests); terrain = Terrain Tiles slope; road = "
        f"straight-line km to OpenStreetMap {data.osm_snapshot()} road. Candidate technologies are a screening list, "
        "not a recommendation."], key="dl_settlements")
    ui.what(["One row per rural settlement, named after the MOE school it is anchored on; click a column header to sort.",
             "Types follow ordered screening rules (see Method & limitations, section 5); every attribute is a proxy "
             "and people offline is an estimate.",
             "Mobile signal combines all Ookla tiles within 2 km and is judged only with at least 20 tests."],
            data=f"MOE school list, June 2022 · DOSM ICTHS {access_year} · Ookla {quarter} · "
                 f"OpenStreetMap {data.osm_snapshot()} · Terrain Tiles")

ui.next_step("views/5_Priorities.py", "Priorities",
             f"see where {district} sits against other districts on need and estimated beneficiaries per RM1m.")
ui.footer([
    "DOSM ICTHS 2024 and 2025, Table 3.1; inferred sample sizes and approximate margins of error (simple random-sampling "
    "formula) are our estimates from the published percentages",
    f"Speedtest® by Ookla® Global Fixed and Mobile Network Performance Maps, {quarter} (CC BY-NC-SA 4.0)",
    "OpenDOSM: household income (HIES), amenities, population; DOSM Census 2020; MOE school list (Jun 2022)",
    "Costs: config/costs.yaml (public statements and news; estimates)",
])
