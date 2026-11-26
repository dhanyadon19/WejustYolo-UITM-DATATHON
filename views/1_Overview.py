"""Overview: official coverage vs household access, urban/rural, rural broadband, trend."""
import plotly.graph_objects as go
import streamlit as st

from app_utils import data, ui

st.set_page_config(page_title="Overview · Beyond Coverage", layout="wide")

facts = data.yaml_config("facts")["official_coverage_populated_areas"]
st_int = data.csv("dosm_hh_internet_state")
trend = data.csv("dosm_hh_internet_trend")
year = int(st_int["year"].max())
cur = st_int[st_int["year"] == year]


def val(state: str, ind: str, strata: str) -> float:
    s = cur[(cur.state == state) & (cur.indicator == ind) & (cur.strata == strata)]["pct"]
    return float(s.iloc[0]) if len(s) else float("nan")


ui.page("Beyond Coverage",
        "Mobile networks reach almost every populated area, mainly outdoors. Fewer households are online, "
        "and far fewer rural homes have fixed broadband.")

# --- Start here: three key findings, every number read from data/ or config/facts.yaml
hz = data.csv("hansard_schools")
h_tot = hz[hz.state.str.startswith("Total")].iloc[0]
h_sar = hz[hz.state == "Sarawak"]
mys_s, sar_s = data.servable_share("All Malaysia"), data.servable_share("Sarawak")
gi_all = data.csv("gap_index_districts")
top_sar = gi_all[(gi_all.state == "Sarawak") & (gi_all.rank_sarawak == 1)]["district"]
top_sar = top_sar.iloc[0] if len(top_sar) else None


def in_ten(share) -> str:
    return f"about {round(10 * share)} in 10" if ui.isnum(share) else ui.DASH


with st.container(border=True):
    st.markdown("#### Start here: three key findings")
    st.markdown("\n".join([
        f"1. **{facts['label']} is {ui.fmt_pct(facts['value_pct'], 2)}**, but only "
        f"{ui.fmt_pct(val('Malaysia', 'internet', 'total'))} of households are online and "
        f"{ui.fmt_pct(val('Malaysia', 'fixed_broadband', 'rural'))} of rural homes have fixed broadband "
        f"(DOSM {year}): two different indicators, not a measured gap.",
        f"2. **{in_ten(mys_s['share']).capitalize()} rural settlements nationally ({in_ten(sar_s['share'])} in "
        f"Sarawak) appear servable through existing networks** (take-up support or home broadband over the mobile "
        f"network, FWA); only ~{mys_s['new']:,} ({sar_s['new']:,} in Sarawak) appear to need new infrastructure. "
        "*Proxy-based estimates.*",
        f"3. **{int(h_tot.schools_without_fibre):,} of {int(h_tot.schools_total):,} schools in six states lack fibre**"
        + (f", {int(h_sar.schools_without_fibre.iloc[0]):,} of them in Sarawak" if len(h_sar) else "")
        + f" (Hansard, Dewan Rakyat, {data.hansard_date()}).",
    ]))
    if top_sar:
        st.markdown(f"<span style='color:{ui.INK_2};font-size:0.9rem'><b>Try:</b> Sarawak map → pick {top_sar} "
                    f"(Sarawak's highest need) → <i>Open {top_sar} in District detail</i>.</span>", unsafe_allow_html=True)
        st.page_link("views/3_Sarawak_map.py", label=f"Open the Sarawak map at {top_sar}", icon=":material/map:",
                     query_params={"district": top_sar})

ui.metric_cards([
    (facts["label"], ui.fmt_pct(facts["value_pct"], 2), f"{facts['definition']} As at {facts['as_of']}."),
    (f"Households with internet, {year}", ui.fmt_pct(val("Malaysia", "internet", "total")), None),
    (f"Rural households with internet, {year}", ui.fmt_pct(val("Malaysia", "internet", "rural")), None),
    (f"Rural households with fixed broadband, {year}", ui.fmt_pct(val("Malaysia", "fixed_broadband", "rural")), None),
])
st.markdown(f"<div style='border-left:3px solid {ui.ACCENT};padding:2px 10px;color:{ui.INK_2};font-size:0.9rem;"
            f"margin:0.2rem 0 0.4rem 0'>{facts['comparison_note']}</div>",
            unsafe_allow_html=True)
st.caption(f"Coverage: [{facts['source_name']}]({facts['source_url']}). Household figures: DOSM ICTHS {year}, Table 1.2.")

# --- 1. Coverage vs household access by state
st.subheader("Where the network reaches vs who is online: two different indicators")
states = cur[(cur.indicator == "internet") & (cur.strata == "total") & (cur.state != "Malaysia")].sort_values("pct")
# Dot plot, not bars: the axis does not start at 0, and bar length would exaggerate the gaps.
hl = states.state.isin(["Sabah", "Sarawak"])
fig = go.Figure()
near = states["pct"] >= facts["value_pct"] - 0.5  # labels left of these dots would sit on the dotted line
for mask, col, size in ((~hl, ui.MUTED, 10), (hl, ui.ACCENT, 13)):
    s_ = states[mask]
    fig.add_trace(go.Scatter(
        x=s_["pct"], y=s_["state"], mode="markers+text", marker=dict(color=col, size=size),
        text=[f"{v:.1f}%" for v in s_["pct"]],
        textposition=["middle right" if nr else "middle left" for nr in near[mask]], textfont=dict(color=ui.INK_2, size=11),
        hovertemplate="%{y}: %{x:.1f}% of households online<extra></extra>", showlegend=False))
fig.add_vline(x=facts["value_pct"], line_color=ui.INK_2, line_dash="dot", line_width=1.5)
fig.add_annotation(x=facts["value_pct"], y=1.0, yref="paper", yanchor="bottom", text=f"Network coverage {facts['value_pct']}% (mainly outdoor)",
                   showarrow=False, xanchor="right", font=dict(color=ui.INK_2, size=12))
lo = float(states["pct"].min())
ui.style(fig, height=520, legend=False, margin=dict(l=10, r=20, t=40, b=10))
fig.update_xaxes(range=[lo - 6, 102.5], title="% of households with internet access", ticksuffix="%")
fig.update_yaxes(categoryorder="array", categoryarray=states["state"].tolist()[::-1])  # lowest access on top
st.plotly_chart(fig, width="stretch")
ui.what(f"Share of households with internet access in {year}, by state (grey dots; Sabah and Sarawak in blue); "
        f"the dotted line marks {facts['label'].lower()} ({facts['value_pct']}%) for context. "
        + facts["comparison_note"],
        data=f"DOSM ICTHS {year} (Table 1.2) · network coverage (mainly outdoor) as at {facts['as_of']}")

# --- 2. Urban vs rural, and 3. rural mobile vs fixed broadband
left, right = st.columns(2)


def dumbbell(df_a, df_b, name_a, name_b, col_a, col_b, title_x, order_by):
    m = df_a.merge(df_b, on="state", suffixes=("_a", "_b")).dropna().sort_values(order_by)
    fig = go.Figure()
    for _, r in m.iterrows():
        fig.add_trace(go.Scatter(x=[r.pct_a, r.pct_b], y=[r.state, r.state], mode="lines",
                                 line=dict(color=ui.GRID, width=2), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=m.pct_a, y=m.state, mode="markers", name=name_a,
                             marker=dict(color=col_a, size=10, line=dict(color=ui.SURFACE, width=2)),
                             hovertemplate="%{y}: %{x:.1f}%<extra>" + name_a + "</extra>"))
    fig.add_trace(go.Scatter(x=m.pct_b, y=m.state, mode="markers", name=name_b,
                             marker=dict(color=col_b, size=10, line=dict(color=ui.SURFACE, width=2)),
                             hovertemplate="%{y}: %{x:.1f}%<extra>" + name_b + "</extra>"))
    ui.style(fig, height=540)
    fig.update_xaxes(title=title_x, ticksuffix="%")
    return fig, m


with left:
    st.subheader("Urban vs rural household access")
    a = cur[(cur.indicator == "internet") & (cur.strata == "urban")][["state", "pct"]]
    b = cur[(cur.indicator == "internet") & (cur.strata == "rural")][["state", "pct"]]
    fig, m = dumbbell(a, b, "Urban", "Rural", ui.MUTED, ui.ACCENT, "% of households with internet", "pct_b")
    st.plotly_chart(fig, width="stretch")
    gap = m.assign(g=m.pct_a - m.pct_b).sort_values("g", ascending=False).iloc[0]
    ui.what(f"Household internet access in urban (grey) and rural (blue) areas, {year}. The widest gap is in "
            f"{gap.state}: {gap.pct_a:.1f}% urban vs {gap.pct_b:.1f}% rural. Kuala Lumpur and Putrajaya have no rural strata.",
            data=f"DOSM ICTHS {year}, Table 1.2")

with right:
    st.subheader("Rural homes: mobile vs fixed broadband")
    a = cur[(cur.indicator == "mobile_broadband") & (cur.strata == "rural")][["state", "pct"]]
    b = cur[(cur.indicator == "fixed_broadband") & (cur.strata == "rural")][["state", "pct"]]
    fig, m = dumbbell(a, b, "Mobile broadband", "Fixed broadband", ui.MUTED, ui.ACCENT, "% of rural households", "pct_b")
    st.plotly_chart(fig, width="stretch")
    ui.what(f"Rural households with mobile broadband (grey) vs fixed (wired) broadband (blue), {year} (DOSM Table 1.2). "
            f"Nationally {val('Malaysia', 'mobile_broadband', 'rural'):.1f}% of rural homes have mobile broadband but only "
            f"{val('Malaysia', 'fixed_broadband', 'rural'):.1f}% have fixed broadband.",
            data=f"DOSM ICTHS {year}, Table 1.2")

# --- Action summary: settlement types and candidate technologies (screening)
st.subheader("What would close the rural gap: settlement types (estimates)")
cl_q = data.csv("costing_clusters")["ookla_quarter"].dropna()
acc_year = data.csv("gap_index_districts")["access_year"].max()
cyear = data.census_year()
scope = st.radio("Area", ["All Malaysia", "Sarawak"], horizontal=True, key="ov_type_scope", label_visibility="collapsed")
ts = data.type_summary(scope)
if len(ts):
    rows = []
    for t in ts.itertuples():
        if t.type_cost_basis == ui.NOT_COSTED or not ui.isnum(t.type_cost_5yr_rm):
            cost = ui.NOT_COSTED if t.settlements else ui.DASH
        else:
            cost = f"{ui.fmt_rm(t.type_cost_5yr_rm)} ({t.type_cost_basis.split(',')[0]})"
        swatch = f"<span style='color:{ui.TYPE_COLOURS.get(t.settlement_type, ui.MUTED)}'>●</span>"
        # candidate technologies sit under the type name, so the table keeps four columns and fits a phone
        tech = f"<br/><span style='font-size:0.85em;color:{ui.INK_2}'>{t.candidate_technologies}</span>"
        rows.append([f"{swatch} **{t.settlement_type}. {t.type_label}**{tech}", f"{int(t.settlements):,}",
                     f"{t.people_without_home_internet:,.0f}", cost])
    # settlements and people add up; costs do not (A and C are not costed), so the total row has no cost
    rows.append(["**All types**", f"**{int(ts.settlements.sum()):,}**", f"**{ts.people_without_home_internet.sum():,.0f}**",
                 f"<span style='color:{ui.INK_2}'>no total: A and C are not costed</span>"])
    # markdown table: wraps on narrow screens instead of scrolling sideways
    head = ["Settlement type and candidate technologies (screening)", "Rural settlements",
            "Rural people without home internet", "Five-year cost (estimate, where costed)"]
    st.markdown("\n".join(["| " + " | ".join(head) + " |", "|---|--:|--:|---|"]
                          + ["| " + " | ".join(r_) + " |" for r_ in rows]), unsafe_allow_html=True)
    screen = ts.screen_cost_main_rm.sum()
    ui.what(["One settlement per rural MOE school, grouped by simple rules on fixed network nearby, demand, "
             "mobile signal, terrain and road distance (proxies; see Method & limitations).",
             "Candidate technologies are a screening list, not a recommendation; a site survey decides.",
             "Costs only where we have a cited public unit cost: tower, satellite per household, FWA retail plan. "
             "Small cells, community Wi-Fi sites and microwave links have no public cost source, so they are not costed.",
             f"For comparison, the tower-vs-satellite cost screen used in the rankings: {ui.fmt_rm(screen)} "
             f"({scope}; {ui.REF_COST}). It is not a total of the types above.",
             ui.TAKEUP_TXT],
            data=f"MOE school list, June 2022 · Census {cyear if cyear else ui.DASH} · DOSM ICTHS {int(acc_year)} · "
                 f"Ookla {cl_q.iloc[0] if len(cl_q) else ui.DASH} · OpenStreetMap {data.osm_snapshot()} · "
                 "Terrain Tiles · config/costs.yaml")
    ui.caveat()
else:
    ui.fallback("No settlement data available.")

# --- 4. Trend
st.subheader(f"Trend, {int(trend.year.min())}–{int(trend.year.max())}")
c1, c2 = st.columns([1, 1])
place = c1.selectbox("Area", ["Malaysia"] + sorted(s for s in trend.state.unique() if s != "Malaysia"),
                     index=0, key="trend_state")
ind_lab = {"internet": "Internet access", "fixed_broadband": "Fixed broadband", "mobile_broadband": "Mobile broadband"}
ind = c2.selectbox("Indicator", list(ind_lab), format_func=ind_lab.get, key="trend_ind")
t = trend[(trend.state == place) & (trend.indicator == ind)].dropna(subset=["pct"])
if t.empty:
    ui.fallback(f"No DOSM trend data for {place} on this indicator.")
    st.stop()
fig = go.Figure()
styles = {"total": (ui.MUTED_LIGHT, "dot", "Total"), "urban": (ui.MUTED, "solid", "Urban"), "rural": (ui.ACCENT, "solid", "Rural")}
for s, (col, dash, lab) in styles.items():
    d = t[t.strata == s].sort_values("year")
    if d.empty:
        continue
    fig.add_trace(go.Scatter(x=d.year, y=d.pct, mode="lines+markers", name=lab,
                             line=dict(color=col, width=2, dash=dash), marker=dict(size=8, color=col),
                             hovertemplate="%{x}: %{y:.1f}%<extra>" + lab + "</extra>"))
    last = d.iloc[-1]
    fig.add_annotation(x=last.year, y=last.pct, text=f" {lab} {last.pct:.1f}%", showarrow=False, xanchor="left",
                       font=dict(color=ui.INK_2, size=12))
ui.style(fig, height=380, hovermode="x unified")
fig.update_xaxes(dtick=1, range=[t.year.min() - 0.2, t.year.max() + 0.8])
fig.update_yaxes(ticksuffix="%", title=f"% of households ({ind_lab[ind].lower()})")
st.plotly_chart(fig, width="stretch")
ui.what(f"{ind_lab[ind]} among households in {place}, by urban/rural strata. Years before the latest edition are "
        "rounded to one decimal by DOSM; each year comes from the newest DOSM edition that reports it.",
        data=f"DOSM ICTHS {int(t.year.min())}–{int(t.year.max())}, Tables 6.4–6.6")

ui.next_step("views/2_Schools.py", "Schools without fibre",
             "the gap is sharpest in schools. See which states Parliament flagged.")
ui.footer([
    f"Network coverage of populated areas (mainly outdoor): [{facts['source_name']}]({facts['source_url']}) ({facts['published']})",
    "DOSM, ICT Use and Access by Individuals and Households Survey Report 2024 and 2025, Tables 1.2 and 6.4–6.6",
])
