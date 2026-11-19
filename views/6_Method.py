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
            + "; ".join(f"{r.district} {int(r.rank_sarawak_moe_min)}–{int(r.rank_sarawak_moe_max)}" for r in moe.itertuples()) + ".")

# --- 3. School proxy validation
st.header("3. School screening layer: validation")
st.dataframe(val.rename(columns={"state": "State", "schools_moe": "MOE schools", "hansard_no_fibre": "Hansard",
                                 "est_2km": "Screen 2 km", "diff_2km": "Diff 2 km", "pct_diff_2km": "% diff 2 km",
                                 "est_1km": "Screen 1 km", "diff_1km": "Diff 1 km", "pct_diff_1km": "% diff 1 km"}),
             hide_index=True, width="stretch", column_config={"State": st.column_config.TextColumn(width="medium")})
ui.what("Schools with no Ookla fixed tile within 1 or 2 km, compared with the schools Parliament says lack fibre.",
        data=f"Hansard, 11 Nov 2026 · MOE school list, June 2022 · Ookla {gi.ookla_quarter.iloc[0]}")
tot = val[val.state.str.startswith("Total")].iloc[0]
st.markdown(f"Flagging schools with no Ookla fixed tile within 2 km gives {int(tot.est_2km):,} against Parliament's "
            f"{int(tot.hansard_no_fibre):,} ({tot.pct_diff_2km:+.1f}%). The 1 km version's total ({tot.pct_diff_1km:+.1f}%) "
            "matches only because large state errors cancel. Thresholds were not tuned. **The layer is a low-confidence "
            "screen and does not drive any cost.**")

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
     "tower 5-year cost ÷ satellite 5-year cost per terminal"),
]
st.dataframe(pd.DataFrame(rows, columns=["Item", "Amount (estimate)", "Basis / source"]), hide_index=True, width="stretch",
             column_config={"Item": st.column_config.TextColumn(width="medium"),
                            "Basis / source": st.column_config.TextColumn(width="large")})
ui.what("Unit costs used by the costing (all estimates).", data="config/costs.yaml (sources below; compiled Nov 2026)")
srcs = sorted(set(t["sources"] + f["sources"] + s["sources"]))
st.markdown("Sources: " + " · ".join(f"[{i + 1}]({u})" for i, u in enumerate(srcs)))
cases = {"Main (Residential)": "cost_main_rm", "Lite plan": "cost_lite_rm",
         "Upper bound: cost sensitivity, +1 fibre PoP per take-up-gap settlement (not a recommendation)": "cost_upper_bound_rm"}
sar = co.state == "Sarawak"
st.dataframe(pd.DataFrame([{"Case": k, "Malaysia": ui.fmt_rm(co[c].sum()), "Sarawak": ui.fmt_rm(co.loc[sar, c].sum())}
                           for k, c in cases.items()]), hide_index=True, width="stretch",
             column_config={"Case": st.column_config.TextColumn(width="large")})
ui.what("Estimated five-year cost to provide service under each case.",
        data=f"MOE school list, June 2022 · Census 2020 · DOSM ICTHS {int(gi.access_year.max())} · Ookla {gi.ookla_quarter.iloc[0]} · config/costs.yaml")
take = cl.category_main.eq("takeup_gap")
hh = co.loc[sar, "household_size"]
res_site = t["residents_per_site"]
st.markdown(
    f"**Settlements.** One per rural MOE school ({len(cl):,}). {int(take.sum()):,} ({100 * take.mean():.0f}%) have an Ookla fixed "
    "tile within 2 km and are treated as a **take-up gap** (fixed network likely nearby; a proxy), not costed. "
    f"{ui.TAKEUP_TXT} The rest are screened for a tower if their households reach the break-even, otherwise satellite.  \n"
    f"**JENDELA comparison.** JENDELA 2 plans about {res_site} residents per tower site, roughly "
    f"{res_site / hh.max():.0f}–{res_site / hh.min():.0f} households at Sarawak household sizes — well below the "
    f"break-even of {tower5 / sat5['residential']:.0f}–{tower5 / sat5['residential_lite']:.0f}. Real towers serve more than "
    f"households (roads, safety, mobile users), so our rule is a cost screen, not a verdict. "
    f"Full method: [docs/costing_method.md]({REPO}/blob/main/docs/costing_method.md).")
ui.caveat()

# --- 5. Limitations
st.header("5. Limitations")
st.markdown(f"""
- **Coverage vs access.** The official {facts['value_pct']}% is network coverage of populated areas; DOSM measures households online. They are different things and are shown side by side, not as a contradiction.
- **Survey precision.** DOSM does not publish district sample sizes or margins of error. Our **inferred sample size** comes from the published percentages ({nsmall} districts flagged), and our **approximate margin of error (simple random-sampling formula)** (±{gi.internet_moe95_pp.min():.0f}–{gi.internet_moe95_pp.max():.0f} pp) probably understates the true error. Neither is a DOSM figure. Districts not flagged are not necessarily precise.
- **Ookla is crowd-sourced.** Tests are run by users who choose to test. Fixed results only come from homes that already have fixed broadband, and fixed wireless or satellite home links can count as "fixed".
- **Proxies.** "Fixed tests per 1,000 residents" and "fixed network likely nearby" (a fixed tile within 2 km) are proxies, not coverage maps. There is no public fibre-route data.
- **School screen failed validation.** It is shown only as a low-confidence layer and never drives costs.
- **Boundaries.** Sarawak uses OpenStreetMap boundaries (unofficial) because DOSM's 2022 file predates new districts; Siburan and Membakut have no boundary anywhere. Polygons from the two sources do not line up exactly at the edges.
- **Dates differ.** Household access 2025, Ookla {gi.ookla_quarter.iloc[0]}, income 2024, population 2026, Census 2020 households, MOE school list June 2022.
- **Costs are estimates** from public statements and news (simple averages of budgets ÷ sites), not engineering quotes. Fibre PoP running cost, government satellite prices and users' mobile plan costs are unsourced or excluded.
- **Settlement model.** Each rural school stands for one settlement and households are assumed equal across a district's rural schools; real settlements vary widely in size.
- **Cost screen, not cost-benefit.** Towers and satellite are different services (a tower also serves mobile users and roads). Estimated beneficiaries per RM1m count rural people without home internet only; wider benefits are not valued.
- **No other technologies.** The screen compares tower and satellite only; fibre PoPs appear only as an upper-bound cost sensitivity, not as a recommendation.
- **Licences.** Ookla data is CC BY-NC-SA 4.0 (non-commercial); OSM-derived boundaries are ODbL.
""")
st.markdown(f"Data notes for every file: [data/README.md]({REPO}/blob/main/data/README.md)")

ui.footer([
    f"Official coverage: [{facts['source_name']}]({facts['source_url']})",
    "DOSM ICTHS 2024–2025; OpenDOSM (income, population, amenities); DOSM Census 2020; MOE school list (Jun 2022)",
    f"Speedtest® by Ookla® Global Fixed and Mobile Network Performance Maps, {gi.ookla_quarter.iloc[0]} (CC BY-NC-SA 4.0)",
    "Hansard, Dewan Rakyat, 11 Nov 2026; costs: config/costs.yaml",
], osm=True)
