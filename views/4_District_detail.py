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

ui.page("District detail", "Everything we know about one district, with its uncertainty.")

c1, c2 = st.columns(2)
states = sorted(dt.state.unique())
state = c1.selectbox("State", states, index=states.index("Sarawak"))
opts = dt[dt.state == state].sort_values("rank_national")
district = c2.selectbox("District (sorted by need, highest first)", opts.district.tolist(), index=0)
r = dt[(dt.state == state) & (dt.district == district)].iloc[0]
small = bool(r.small_sample_flag)

if small:
    st.warning(f"**Low confidence.** {district}'s DOSM estimate appears to rest on a small sample: {ui.INFERRED_N} "
               f"about {int(r.implied_sample_n)} households, {ui.MOE_TXT} ±{r.internet_moe95_pp:.1f} percentage points. "
               f"{ui.NOT_DOSM} Treat its ranks as ranges, not exact positions.", icon="⚠️")

# --- 1. Household access 2024 / 2025
st.subheader("Households with internet")
a1, a2, a3 = st.columns([1, 1, 2], gap="medium")


def moe_cap(col, moe):
    if pd.notna(moe):
        col.caption(f"Approx. margin of error ±{moe:.1f} pp (simple random-sampling formula; our estimate)")


a1.metric("DOSM 2024", ui.fmt_pct(r.internet_2024))
moe_cap(a1, r.internet_moe95_pp_2024)
a2.metric("DOSM 2025", ui.fmt_pct(r.internet_2025),
          delta=f"{r.internet_change_pp:+.1f} pp" if pd.notna(r.internet_change_pp) else None)
moe_cap(a2, r.internet_moe95_pp_2025)
if pd.notna(r.change_beyond_noise):
    a2.caption("Change is larger than the approximate margin of error." if bool(r.change_beyond_noise)
               else "Change is within the approximate margin of error: not a measurable trend.")
with a3:
    fig = go.Figure()
    for yr, col in ((2024, ui.MUTED), (2025, ui.ACCENT)):
        v, moe = r[f"internet_{yr}"], r[f"internet_moe95_pp_{yr}"]
        fig.add_trace(go.Scatter(x=[v], y=[str(yr)], mode="markers", marker=dict(size=12, color=col),
                                 error_x=dict(type="data", array=[moe if pd.notna(moe) else 0], color=col, thickness=2, width=6),
                                 hovertemplate=f"{yr}: %{{x:.1f}}%" + (f" ± {moe:.1f} pp" if pd.notna(moe) else "") + "<extra></extra>",
                                 showlegend=False))
    ui.style(fig, height=160, legend=False, margin=dict(l=10, r=20, t=10, b=10))
    fig.update_xaxes(ticksuffix="%", title=None)
    fig.update_yaxes(type="category", categoryorder="array", categoryarray=["2025", "2024"])
    st.plotly_chart(fig, width="stretch")
ui.what("Share of households with internet access (DOSM ICTHS Table 3.1). Error bars show our approximate 95% margin "
        "of error (simple random-sampling formula, inferred sample size) where the estimate rests on a small sample; "
        "no bar means the sample was large enough that no size can be inferred. DOSM does not publish these margins.",
        data="DOSM ICTHS 2024 and 2025, Table 3.1")

# --- 2. Speeds
st.subheader(f"Measured speeds (Ookla, {quarter})")
s1, s2, s3 = st.columns(3)
s1.metric("Mobile download", f"{r.mb_dl_mbps:.0f} Mbps", help=f"Test-weighted mean of {int(r.mb_tests):,} tests")
s2.metric("Mobile upload", f"{r.mb_ul_mbps:.0f} Mbps")
s3.metric("Mobile latency (median)", f"{r.mb_latency_median_ms:.0f} ms")
s4, s5, s6 = st.columns(3)
s4.metric("Fixed download", f"{r.fx_dl_mbps:.0f} Mbps", help=f"Test-weighted mean of {int(r.fx_tests):,} tests")
s5.metric("Fixed upload", f"{r.fx_ul_mbps:.0f} Mbps")
s6.metric("Fixed tests per 1,000 residents", f"{r.fixed_reach:.1f}", help="A proxy for how many homes use fixed broadband")
notes = []
if bool(r.fx_low_sample):
    notes.append(f"only {int(r.fx_tests)} fixed tests (low sample)")
if bool(r.mb_low_sample):
    notes.append(f"only {int(r.mb_tests)} mobile tests (low sample)")
ui.what("Speeds from user-run Speedtest results in the district. Fixed speeds come only from homes that already "
        "have fixed broadband, so a fast fixed speed does not mean wide coverage." + (" Note: " + "; ".join(notes) + "." if notes else ""),
        data=f"Ookla {quarter}; population 2026")

# --- 3. Context
st.subheader("Context")
k1, k2, k3 = st.columns(3)
k4, k5 = st.columns([1, 2])
k1.metric(f"Median household income ({int(r.income_year)})", f"RM{r.income_median:,.0f}")
k2.metric(f"Households with electricity ({int(r.amenities_year)})", ui.fmt_pct(r.electricity))
k3.metric(f"Population ({int(r.population_year)})", f"{r.population_k * 1000:,.0f}")
k4.metric("Pupils in MOE schools (June 2022)", f"{r.students:,.0f}" if pd.notna(r.students) else "–")
k5.metric("People without home internet (estimate)", f"{r.people_without_home_internet:,.0f}",
          help="Population × share of households without internet; assumes individuals follow the household rate.")
ui.what("Background indicators for the district.", data=f"HIES {int(r.income_year)} · OpenDOSM amenities {int(r.amenities_year)} · "
        f"population {int(r.population_year)} · MOE school list, June 2022 · DOSM ICTHS {access_year}")

# --- 4. Need
st.subheader("Need: Connectivity Gap Index")
n1, n2 = st.columns([1, 2])
with n1:
    st.metric("Gap Index (0 best – 1 worst)", f"{r.cgi:.2f}")
    st.markdown(f"**National need rank:** {int(r.rank_national)} of {len(dt)}  \n"
                f"Range under 1,000 random weightings: {int(r.rank_national_dirichlet_p05)}–{int(r.rank_national_dirichlet_p95)}  \n"
                f"With equal weights: {int(r.rank_national_equal)}"
                + (f"  \nWithin the approximate margin of error: {int(r.rank_national_moe_min)}–{int(r.rank_national_moe_max)}" if pd.notna(r.rank_national_moe_min) else ""))
    if state == "Sarawak":
        st.markdown(f"**Sarawak need rank:** {int(r.rank_sarawak)} "
                    f"(range {int(r.rank_sarawak_p05)}–{int(r.rank_sarawak_p95)})"
                    + (f"; within the approximate margin of error {int(r.rank_sarawak_moe_min)}–{int(r.rank_sarawak_moe_max)}" if pd.notna(r.rank_sarawak_moe_min) else ""))
with n2:
    lab = {"access_gap": "Household access gap", "mobile_speed": "Slow mobile", "fixed_reach": "Low fixed reach (proxy)",
           "low_income": "Low income"}
    ks = list(lab)
    fig = go.Figure(go.Bar(y=[lab[k] for k in ks], x=[r[f"{k}_norm"] for k in ks], orientation="h",
                           marker_color=ui.ACCENT, marker_line_width=0,
                           text=[f"{r[f'{k}_norm']:.2f} × weight {w[k]['weight']}" for k in ks], textposition="outside",
                           textfont=dict(color=ui.INK_2), hovertemplate="%{y}: %{x:.2f}<extra></extra>"))
    ui.style(fig, height=230, legend=False)
    fig.update_xaxes(range=[0, 1.35], title="Normalised score (1 = worst district nationally)")
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, width="stretch")
    ui.what("The four indicators behind the Gap Index, each scaled 0–1 across all districts (1 = worst), with the "
            "weight each carries.", data=f"DOSM ICTHS {access_year} · Ookla {quarter} · HIES {int(r.income_year)} · population {int(r.population_year)}")

# --- 5. Fixes and cost
st.subheader("Rural settlements, recommended fixes and cost (estimates)")
if pd.isna(r.rural_settlements):
    st.info(f"{district} has no rural MOE school, so no settlements are costed.")
else:
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Rural settlements (one per rural school)", f"{int(r.rural_settlements)}")
    f2.metric("Take-up gap (fixed network likely nearby)", f"{int(r.n_takeup_gap)} ({100 * r.share_settlements_takeup_gap:.0f}%)",
              help=f"{r.takeup_gap_people_without_internet:,.0f} rural people without home internet. A proxy: an Ookla fixed "
                   "tile lies within 2 km. Not costed as infrastructure.")
    f3.metric("Towers", f"{int(r.n_tower)}")
    f4.metric("Satellite settlements", f"{int(r.n_satellite)}")
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("5-year cost, main (Residential)", ui.fmt_rm(r.cost_main_rm))
    g2.metric("5-year cost, Lite plan", ui.fmt_rm(r.cost_lite_rm))
    g3.metric("Upper bound (cost sensitivity)", ui.fmt_rm(r.cost_upper_bound_rm),
              help="Adds one fibre PoP per take-up-gap settlement, capex only. A cost sensitivity, not a recommendation.")
    g4.metric("Main fix", ui.FIX_LABELS.get(r.main_fix, r.main_fix))
    if pd.notna(r.people_per_rm_m_main):
        st.markdown(f"**Estimated beneficiaries per RM1m:** {r.people_per_rm_m_main:,.0f} rural people without home "
                    f"internet reached per RM1m (national rank {int(r.value_rank_national)}"
                    + (f", Sarawak {int(r.value_rank_sarawak)}" if pd.notna(r.value_rank_sarawak) else "")
                    + f"); {r.students_per_rm_m_main:,.0f} pupils per RM1m. Whole-district figure: "
                    f"{r.people_per_rm_m_district_main:,.0f} people per RM1m (includes people the plan does not reach).")
    ui.what("Each rural school stands for one settlement. Settlements with an Ookla fixed tile within 2 km are treated as "
            "a take-up gap (proxy) and not costed; the rest are screened for a tower if they have enough households to "
            "beat satellite over five years, otherwise satellite. All costs are estimates. " + ui.TAKEUP_TXT,
            data=f"MOE school list, June 2022 · Census 2020 · DOSM ICTHS {access_year} · Ookla {quarter} · config/costs.yaml")
    ui.caveat()

ui.footer([
    "DOSM ICTHS 2024 and 2025, Table 3.1; inferred sample sizes and approximate margins of error (simple random-sampling "
    "formula) are our estimates from the published percentages",
    f"Speedtest® by Ookla® Global Fixed and Mobile Network Performance Maps, {quarter} (CC BY-NC-SA 4.0)",
    "OpenDOSM: household income (HIES), amenities, population; DOSM Census 2020; MOE school list (Jun 2022)",
    "Costs: config/costs.yaml (public statements and news; estimates)",
])
