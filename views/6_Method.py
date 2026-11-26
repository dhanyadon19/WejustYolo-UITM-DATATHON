"""Method & limitations: index, sensitivity, school-proxy validation, cost assumptions, limitations."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app_utils import data, ui

st.set_page_config(page_title="Method & limitations · Beyond Coverage", layout="wide")

w = data.yaml_config("weights")["weights"]
costs = data.yaml_config("costs")
facts = data.yaml_config("facts")["official_coverage_populated_areas"]
gi = data.csv("gap_index_districts")
sens = data.csv("gap_index_sensitivity")
val = data.csv("schools_validation")
co = data.csv("costing_districts")
cl = data.csv("costing_clusters")
REPO = "https://github.com/dhanyadon19/WejustYolo-UITM-DATATHON"

ui.page("Method & limitations", "How the numbers are built, how sure we are, and what they cannot tell you.")

# --- 1. Index
st.header("1. Connectivity Gap Index")
st.latex(r"\mathrm{CGI}_d=\sum_i w_i\,\tilde S_{d,i},\qquad \tilde S_{d,i}=\frac{S_{d,i}-\min_d S_i}{\max_d S_i-\min_d S_i}\ \text{(inverted where lower is worse)}")
labels = {"access_gap": ("100 − household internet access %", f"DOSM ICTHS {int(gi.access_year.max())}, Table 3.1"),
          "mobile_speed": ("Ookla mobile download, test-weighted (inverted)", f"Ookla {gi.ookla_quarter.iloc[0]}"),
          "fixed_reach": ("Ookla fixed tests per 1,000 residents (inverted) — a PROXY", f"Ookla {gi.ookla_quarter.iloc[0]}; population {int(gi.population_year.max())}"),
          "low_income": ("Median household income (inverted)",
                         f"OpenDOSM HIES {int(gi.income_year.max())} ({int(gi.income_year.min())} where {int(gi.income_year.max())} is missing)")}
st.dataframe(pd.DataFrame([{"Indicator": k, "Definition": labels[k][0], "Source": labels[k][1], "Weight": v["weight"],
                            "Why this weight": v["reason"]} for k, v in w.items()]), hide_index=True, width="stretch",
             column_config={"Why this weight": st.column_config.TextColumn(width="large")})
ui.what("The four indicators, their sources and weights (config/weights.yaml).",
        data=f"DOSM ICTHS {int(gi.access_year.max())} · Ookla {gi.ookla_quarter.iloc[0]} · HIES {int(gi.income_year.max())} · population {int(gi.population_year.max())}")
nsmall = int(gi.small_sample_flag.sum())
st.markdown(f"Computed for **{len(gi)} districts and territories**. Each indicator is scaled 0–1 across all of them "
            "(1 = worst). Need rank 1 = highest index. Districts without a boundary have no Ookla data and are not indexed.")

# --- 2. Sensitivity
st.header("2. How stable are the ranks?")
sk = sens[sens.state == "Sarawak"].sort_values("rank_sarawak").head(15)
fig = go.Figure()
for r in sk.itertuples():
    fig.add_trace(go.Scatter(x=[r.rank_sarawak_dirichlet_p05, r.rank_sarawak_dirichlet_p95], y=[r.district] * 2, mode="lines",
                             line=dict(color=ui.MUTED_LIGHT, width=6), hoverinfo="skip", showlegend=False))
fig.add_trace(go.Scatter(x=sk.rank_sarawak, y=sk.district, mode="markers", name="Baseline rank",
                         marker=dict(color=ui.ACCENT, size=10, line=dict(color=ui.SURFACE, width=2)),
                         customdata=sk[["rank_sarawak_dirichlet_p05", "rank_sarawak_dirichlet_p95", "rank_sarawak_equal"]],
                         hovertemplate="%{y}: rank %{x}; random weights %{customdata[0]:.0f}–%{customdata[1]:.0f}; "
                                       "equal weights %{customdata[2]}<extra></extra>"))
fig.add_trace(go.Scatter(x=sk.rank_sarawak_equal, y=sk.district, mode="markers", name="Equal weights",
                         marker=dict(color=ui.INK_2, size=8, symbol="diamond-open", line=dict(width=1.5)),
                         hovertemplate="%{y}: equal-weights rank %{x}<extra></extra>"))
ui.style(fig, height=470)
fig.update_xaxes(title="Rank within Sarawak (1 = largest gap)", range=[0, sk.rank_sarawak_dirichlet_p95.max() + 2])
fig.update_yaxes(autorange="reversed")
st.plotly_chart(fig, width="stretch")
n_runs = int(sens.n_runs.iloc[0])
ui.what(f"Sarawak's 15 highest-need districts: blue dot = rank with the chosen weights, grey bar = 5th–95th percentile "
        f"rank over {n_runs:,} random weightings (Dirichlet), open diamond = rank with equal weights.",
        data=f"Gap Index from DOSM ICTHS {int(gi.access_year.max())} · Ookla {gi.ookla_quarter.iloc[0]} · HIES {int(gi.income_year.max())}")
moe = sens[sens.rank_sarawak_moe_min.notna() & (sens.state == "Sarawak")].sort_values("rank_sarawak").head(10)
st.markdown(f"**Survey uncertainty.** {nsmall} districts have a small {ui.INFERRED_N} (our estimate, not a DOSM figure). "
            f"Setting each one's access to the low and high end of its {ui.MOE_TXT} moves its Sarawak rank as follows: "
            + "; ".join(f"{r.district} {ui.range_text(r.rank_sarawak_moe_min, r.rank_sarawak_moe_max)}" for r in moe.itertuples()) + ".")

# --- 3. School proxy validation
st.header("3. School screening layer: validation")
ui.table(val, [
    ("state", "State", None),
    ("schools_moe", "MOE schools", ",.0f"),
    ("hansard_no_fibre", "Hansard", ",.0f"),
    ("est_2km", "Screen 2 km", ",.0f"),
    ("diff_2km", "Diff 2 km", "+,.0f"),
    ("pct_diff_2km", "% diff 2 km", lambda v: f"{v:+,.1f}%" if ui.isnum(v) else ""),
    ("est_1km", "Screen 1 km", ",.0f"),
    ("diff_1km", "Diff 1 km", "+,.0f"),
    ("pct_diff_1km", "% diff 1 km", lambda v: f"{v:+,.1f}%" if ui.isnum(v) else ""),
])
ui.what("Schools with no Ookla fixed tile within 1 or 2 km, compared with the schools Parliament says lack fibre.",
        data=f"Hansard, 11 Nov 2026 · MOE school list, June 2022 · Ookla {gi.ookla_quarter.iloc[0]}")
tot = val[val.state.str.startswith("Total")].iloc[0]
st.markdown(f"""
- **2 km screen:** {int(tot.est_2km):,} schools flagged vs Parliament's {int(tot.hansard_no_fibre):,} ({tot.pct_diff_2km:+.1f}%).
- **1 km screen:** total {tot.pct_diff_1km:+.1f}%, but only because large state errors cancel out.
- Thresholds were not tuned.
- **A low-confidence screen only: it does not drive any cost.**
""")

# --- 4. Costs
st.header("4. Cost assumptions (estimates)")
t, s, f = costs["tower"], costs["satellite"], costs["fibre_pop"]
tower5 = t["capex_per_site_rm"]["central"] + 5 * t["opex_per_site_per_year_rm"]
sat5 = {p: s["kit_rm"] + 60 * s["monthly_rm"][p] for p in ("residential", "residential_lite")}
school5 = s["kit_rm"] + 60 * s["monthly_rm"]["business_from"]
rows = [
    ("Tower capex per site", f"RM{t['capex_per_site_rm']['central']:,} (high RM{t['capex_per_site_rm']['high']:,})", "; ".join(t["capex_notes"])),
    ("Tower opex per year", f"RM{t['opex_per_site_per_year_rm']:,}", t["opex_source"]),
    ("Tower, 5-year cost", f"RM{tower5:,.0f}", "capex + 5 × opex"),
    ("Satellite kit / month (Residential, Lite)", f"RM{s['kit_rm']:,} / RM{s['monthly_rm']['residential']} , RM{s['monthly_rm']['residential_lite']}", "; ".join(s["notes"])),
    ("Satellite, 5-year per household", f"RM{sat5['residential']:,} (Lite RM{sat5['residential_lite']:,})", "kit + 60 months"),
    ("Satellite, 5-year per school (Business from)", f"RM{school5:,}", "kit + 60 × Business 'from' price (derived)"),
    ("Fibre PoP capex (upper-bound cost sensitivity only; not a recommendation)", f"RM{f['capex_per_site_rm']['central']:,}", "; ".join(f["notes"]) + "; running cost UNSOURCED"),
    ("Break-even households per tower", f"{tower5 / sat5['residential']:.1f} (Lite {tower5 / sat5['residential_lite']:.1f})",
     "tower 5-year cost ÷ satellite 5-year cost per terminal; compared with households without home internet"),
]
st.dataframe(pd.DataFrame(rows, columns=["Item", "Amount (estimate)", "Basis / source"]), hide_index=True, width="stretch",
             column_config={"Item": st.column_config.TextColumn(width="medium"),
                            "Basis / source": st.column_config.TextColumn(width="large")})
ui.what("Unit costs used by the costing (all estimates).", data="config/costs.yaml (sources below; compiled Nov 2026)")
srcs = sorted(set(t["sources"] + f["sources"] + s["sources"]))
st.markdown("Sources: " + " · ".join(f"[{i + 1}]({u})" for i, u in enumerate(srcs)))
cases = {"Main (Residential): " + ui.REF_COST: "cost_main_rm", "Lite plan": "cost_lite_rm",
         "Upper bound (cost sensitivity, not a recommendation)": "cost_upper_bound_rm",
         "Rule sensitivity: tower test on all households": "cost_rule_all_hh_rm"}
sar = co.state == "Sarawak"
st.dataframe(pd.DataFrame([{"Case": k, "Malaysia": ui.fmt_rm(co[c].sum()), "Sarawak": ui.fmt_rm(co.loc[sar, c].sum())}
                           for k, c in cases.items()]), hide_index=True, width="stretch",
             column_config={"Case": st.column_config.TextColumn(width="large")})
ui.what("Estimated five-year cost to provide service under each case. Upper bound: adds one fibre PoP per take-up-gap "
        "settlement (capex only), a cost sensitivity, not a recommendation.",
        data=f"MOE school list, June 2022 · Census 2020 · DOSM ICTHS {int(gi.access_year.max())} · Ookla {gi.ookla_quarter.iloc[0]} · config/costs.yaml")
take = cl.category_main.eq("takeup_gap")
hh = co.loc[sar, "household_size"]
res_site = t["residents_per_site"]
st.markdown(f"""
**How each settlement gets a fix (estimates)**
- **Settlements:** one per rural MOE school ({len(cl):,} in total).
- **Take-up gap:** {int(take.sum()):,} ({100 * take.mean():.0f}%) have an Ookla fixed tile within 2 km (fixed network likely nearby; a proxy). Not costed. {ui.TAKEUP_TXT}
- **Tower or satellite:** the rest get a tower if their households without home internet (the ones the costs pay for) reach the break-even, otherwise satellite.
- **Sensitivity:** a second case applies the tower test to all households instead.

**JENDELA comparison**
- JENDELA 2 plans about {res_site} residents per tower site: roughly {res_site / hh.max():.0f}–{res_site / hh.min():.0f} households at Sarawak household sizes.
- That is well below our break-even of {tower5 / sat5['residential']:.0f}–{tower5 / sat5['residential_lite']:.0f} households.
- Real towers serve more than households (roads, safety, mobile users), so our rule is a cost screen, not a verdict.

Full method: [docs/costing_method.md]({REPO}/blob/main/docs/costing_method.md)
""")
ui.caveat()

# --- 5. Settlement types and technology options
st.header("5. Settlement types and technology options")
stc = data.yaml_config("settlement_types")
mq, tr, rd = stc["mobile_quality"], stc["terrain"], stc["road"]
fwa = costs["fwa"]
st.markdown(f"""
Added after **expert feedback from a telecom industry expert** (Nov 2026): rather than a tower-vs-satellite choice, group settlements
by demand, distance to existing networks, current service quality and terrain, then match a technology mix.

- **One settlement per rural MOE school** ({len(cl):,}). Rules are applied in order; the first match wins, so each settlement has exactly one type.
- **Candidate technologies are a screening list**, not a recommendation. A site survey decides.
""")
ui.table(pd.DataFrame([{"type": f"{k}. {v['label']}", "rule": v["rule"], "tech": v["candidates"]}
                       for k, v in ((k, stc["types"][k]) for k in stc["order"])]),
         [("type", "Type", None), ("rule", "Rule (in this order)", None), ("tech", "Candidate technologies (screening)", None)])
ui.what("Settlement types, their rules and candidate technologies (config/settlement_types.yaml).",
        data="config/settlement_types.yaml")
st.markdown(f"""
**Inputs (all proxies, computed in scripts/build_settlements.py and cached; never fetched by the app)**
- **Demand:** estimated households and people without home internet (Census 2020 households × DOSM ICTHS {int(gi.access_year.max())} access gap).
- **Fixed network nearby:** an Ookla fixed tile within 2 km (existing proxy).
- **Mobile signal:** all Ookla {gi.ookla_quarter.iloc[0]} mobile tiles within {mq['search_km']} km combined (total tests, test-weighted mean download). Judged only with at least {mq['min_tests']} tests: single tiles with 1–3 tests are too noisy. *Good* = mean download ≥ {mq['good_min_mbps']} Mbps, the [JENDELA Phase 1 mobile speed target]({mq['source_url']}) (also a mean, from Ookla); *weak* = below; *too few tests* = 1–{mq['min_tests'] - 1} tests; *no tests* = no tile within {mq['search_km']} km (not proof of no signal).
- **Terrain:** mean slope within {tr['radius_m']} m from [Terrain Tiles]({tr['source_url']}) (zoom {tr['zoom']}, ~38 m, SRTM-based). Flat < {tr['flat_max_deg']}°, hilly {tr['flat_max_deg']}–{tr['steep_min_deg']}°, steep ≥ {tr['steep_min_deg']}°.
- **Road distance:** straight line to the nearest motorable road in [OpenStreetMap]({rd['source_url']}) (Geofabrik extract, {data.osm_snapshot()}, ODbL; tracks and paths excluded). Near ≤ {rd['near_max_km']} km, far {rd['near_max_km']}–{rd['very_far_min_km']} km, very far > {rd['very_far_min_km']} km.
- **Break-even (type B):** households without home internet ≥ the tower vs satellite break-even (section 4).
""")
tsum = data.csv("settlement_types_summary")
piv = tsum.pivot_table(index=["settlement_type", "type_label"], columns="scope", values="settlements", aggfunc="sum").reset_index()
ppl = tsum.pivot_table(index="settlement_type", columns="scope", values="people_without_home_internet", aggfunc="sum")
piv["people_mys"] = piv.settlement_type.map(ppl.get("All Malaysia", {}))
piv["people_sar"] = piv.settlement_type.map(ppl.get("Sarawak", {}))
cst = tsum[tsum.scope == "All Malaysia"].set_index("settlement_type")
piv["cost"] = [ui.fmt_rm(cst.type_cost_5yr_rm.get(k)) if ui.isnum(cst.type_cost_5yr_rm.get(k)) else ui.NOT_COSTED
               for k in piv.settlement_type]
piv["basis"] = piv.settlement_type.map(cst.type_cost_basis)
piv = piv.sort_values("settlement_type", key=lambda x: x.map({k: i for i, k in enumerate(ui.TYPE_ORDER)}))
ui.table(piv, [("settlement_type", "Type", None), ("type_label", "Name", None),
               ("All Malaysia", "Settlements (Malaysia)", ",.0f"), ("people_mys", "People offline (Malaysia)", ",.0f",
                "Estimated rural people without home internet"),
               ("Sarawak", "Settlements (Sarawak)", ",.0f"), ("people_sar", "People offline (Sarawak)", ",.0f"),
               ("cost", "Five-year cost, Malaysia (estimate)", None), ("basis", "Cost basis", None)],
         download="beyond_coverage_settlement_types.csv",
         notes=["Beyond Coverage: settlement types (rule-based screening; config/settlement_types.yaml). ESTIMATES and PROXIES.",
                "Costs only where a cited public unit cost exists (config/costs.yaml); otherwise not costed.",
                f"Data: MOE school list June 2022; Census 2020; DOSM ICTHS {int(gi.access_year.max())}; Ookla {gi.ookla_quarter.iloc[0]}; "
                f"OpenStreetMap {data.osm_snapshot()}; Terrain Tiles."])
ui.what(["Settlements and estimated people without home internet by type.",
         f"Costed only with a cited unit cost: tower (type B), satellite per household plus the school terminal (D), "
         f"and FWA at a retail 5G home plan, RM{fwa['monthly_rm']}/month with the router included "
         f"([source]({fwa['sources'][0]}), accessed {fwa['accessed']}), for E. FWA assumes the nearby mobile site has spare "
         "capacity: no network build cost is included.",
         "Types A and C are not costed: we found no public Malaysian cost for take-up support, small cells, community "
         "Wi-Fi sites or microwave links.",
         "The tower-vs-satellite cost screen (section 4) is unchanged and still drives the rankings and budget planner."],
        data=f"Ookla {gi.ookla_quarter.iloc[0]} · OpenStreetMap {data.osm_snapshot()} · Terrain Tiles · config/costs.yaml")
st.markdown("""
**What this cannot tell you**
- **No tower locations and no fibre routes:** neither is public, so "network nearby" relies on where people ran speed tests.
- **No indoor signal:** Ookla tests and coverage figures say little about signal inside buildings.
- **Terrain is a proxy:** slope near the school, not a line-of-sight or radio model; forest cover is not included.
- **Road distance is straight-line** and depends on how complete OpenStreetMap is in rural Borneo; rivers are not counted.
""")

# --- 6. Limitations
st.header("6. Limitations")
st.markdown(f"""
- **Coverage ≠ access:** the official {facts['value_pct']}% is network coverage of populated areas (mainly outdoor); DOSM measures households online. Two different indicators, not a measured gap.
- **No indoor signal data:** indoor connectivity depends on building materials, signal penetration, distance to the site, terrain and network capacity, which we do not measure.
- **Survey precision:** DOSM publishes no district margins of error; our {ui.INFERRED_N} and margin are estimates ({nsmall} districts flagged).
- **Ookla is crowd-sourced:** fixed tests only come from homes that already have fixed broadband.
- **Proxies, not coverage maps:** no public fibre-route data exists.
- **School screen failed validation:** shown only as a low-confidence layer; never drives costs.
- **Boundaries:** Sarawak uses unofficial OpenStreetMap boundaries; Siburan and Membakut have none.
- **Data years differ:** 2020 to {gi.ookla_quarter.iloc[0]}.
- **Costs are estimates** from public statements and news, not engineering quotes.
- **Simple settlement model:** households assumed equal across a district's rural schools.
- **Cost screen, not cost-benefit:** towers and satellite are different services.
- **3D view is context only:** no line-of-sight or signal model.
- **Satellite in practice:** needs power and clear sky; the monthly fee is a real cost; no mobile coverage.
- **Take-up proxy may be too generous:** the same proxy undercounted schools without fibre by about {abs(tot.pct_diff_2km):.0f}%, so the main cost is likely understated.
- **Settlement types are a screen:** rules and proxies, not a site survey or radio plan (section 5).
- **Fibre PoPs** appear only as an upper-bound cost sensitivity.
- **Licences:** Ookla CC BY-NC-SA 4.0 (non-commercial); OSM boundaries ODbL.
""")
with st.expander("Full detail on each limitation"):
    st.markdown(f"""
- **Coverage vs access.** The official {facts['value_pct']}% is network coverage of populated areas, mainly from an outdoor perspective; DOSM measures whether households are online. They are two different indicators (where the network reaches outdoors vs whether households are online), shown side by side, not a measured gap and not a contradiction.
- **Indoor connectivity is not measured.** Whether a signal works indoors depends on building materials, signal penetration, distance to the site, terrain and network capacity. None of these is in our data.
- **Survey precision.** DOSM does not publish district sample sizes or margins of error. Our **inferred sample size** comes from the published percentages ({nsmall} districts flagged), and our **approximate margin of error (simple random-sampling formula)** (±{gi.internet_moe95_pp.min():.0f}–{gi.internet_moe95_pp.max():.0f} pp) probably understates the true error. Neither is a DOSM figure. Districts not flagged are not necessarily precise.
- **Ookla is crowd-sourced.** Tests are run by users who choose to test. Fixed results only come from homes that already have fixed broadband, and fixed wireless or satellite home links can count as "fixed".
- **Proxies.** "Fixed tests per 1,000 residents" and "fixed network likely nearby" (a fixed tile within 2 km) are proxies, not coverage maps. There is no public fibre-route data.
- **School screen failed validation.** It is shown only as a low-confidence layer and never drives costs.
- **Boundaries.** Sarawak uses OpenStreetMap boundaries (unofficial) because DOSM's 2022 file predates new districts; Siburan and Membakut have no boundary anywhere. Polygons from the two sources do not line up exactly at the edges.
- **Dates differ.** Household access 2025, Ookla {gi.ookla_quarter.iloc[0]}, income 2024, population 2026, Census 2020 households, MOE school list June 2022.
- **Costs are estimates** from public statements and news (simple averages of budgets ÷ sites), not engineering quotes. Fibre PoP running cost, government satellite prices and users' mobile plan costs are unsourced or excluded.
- **Settlement model.** Each rural school stands for one settlement and households are assumed equal across a district's rural schools; real settlements vary widely in size.
- **Cost screen, not cost-benefit.** Towers and satellite are different services (a tower also serves mobile users and roads). Estimated beneficiaries per RM1m count rural people without home internet only; wider benefits are not valued.
- **3D view is context only.** The 3D view shows terrain context only; it does not model line-of-sight or signal blocking (future work: add tower locations and a line-of-sight model).
- **Satellite in practice.** A terminal needs continuous power and a clear view of the sky (tall forest and hills can block it), and heavy rain can slow it. The monthly fee is a real cost to low-income households: the five-year cost includes the fee, but not who pays it once any subsidy ends. It serves a fixed location only: no mobile coverage on roads or farms.
- **Take-up proxy may be too generous.** The same type of proxy (a fixed tile within 2 km) undercounted schools without fibre by about {abs(tot.pct_diff_2km):.0f}% against Hansard ({int(tot.est_2km):,} flagged vs {int(tot.hansard_no_fibre):,} in the six states; state errors vary widely), so the take-up group is likely overstated and the main cost understated; the upper bound covers this case.
- **Technology options.** The cost screen behind the rankings compares tower and satellite only. Settlement types (section 5) add candidate technologies (FWA, small cells, community Wi-Fi, microwave backhaul, fibre connection), but only FWA has a cited cost; the others are not costed. Fibre PoPs appear only as an upper-bound cost sensitivity, not as a recommendation.
- **Licences.** Ookla data is CC BY-NC-SA 4.0 (non-commercial); OSM-derived boundaries are ODbL.
""")
ui.next_step("views/1_Overview.py", "Back to the overview", "start the story again from the national picture.")
st.markdown(f"Data notes for every file: [data/README.md]({REPO}/blob/main/data/README.md)")

ui.footer([
    f"Network coverage of populated areas (mainly outdoor): [{facts['source_name']}]({facts['source_url']})",
    "DOSM ICTHS 2024–2025; OpenDOSM (income, population, amenities); DOSM Census 2020; MOE school list (Jun 2022)",
    f"Speedtest® by Ookla® Global Fixed and Mobile Network Performance Maps, {gi.ookla_quarter.iloc[0]} (CC BY-NC-SA 4.0)",
    "Hansard, Dewan Rakyat, 11 Nov 2026; costs: config/costs.yaml",
], osm=True)
