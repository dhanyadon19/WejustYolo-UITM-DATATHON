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
        "Malaysia's networks reach almost every populated area. Fewer households are actually online, "
        "and far fewer rural homes have fixed broadband.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Official network coverage", ui.fmt_pct(facts["value_pct"], 2),
          help=f"{facts['definition']} As at {facts['as_of']}. Source: {facts['source_name']}.")
c2.metric(f"Households with internet, {year}", ui.fmt_pct(val("Malaysia", "internet", "total")))
c3.metric(f"Rural households with internet, {year}", ui.fmt_pct(val("Malaysia", "internet", "rural")))
c4.metric(f"Rural fixed broadband, {year}", ui.fmt_pct(val("Malaysia", "fixed_broadband", "rural")))
st.caption(f"Coverage measures where the network reaches; household access measures who is online. "
           f"Coverage: [{facts['source_name']}]({facts['source_url']}). Household figures: DOSM ICTHS {year}, Table 1.2.")

# --- 1. Coverage vs household access by state
st.subheader("Coverage is near-universal; household access is not")
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
fig.add_annotation(x=facts["value_pct"], y=1.0, yref="paper", yanchor="bottom", text=f"Official coverage {facts['value_pct']}%",
                   showarrow=False, xanchor="right", font=dict(color=ui.INK_2, size=12))
lo = float(states["pct"].min())
ui.style(fig, height=520, legend=False, margin=dict(l=10, r=20, t=40, b=10))
fig.update_xaxes(range=[lo - 6, 102.5], title="% of households with internet access", ticksuffix="%")
fig.update_yaxes(categoryorder="array", categoryarray=states["state"].tolist()[::-1])  # lowest access on top
st.plotly_chart(fig, width="stretch")
ui.what(f"Share of households with internet access in {year}, by state (grey dots; Sabah and Sarawak in blue); "
        f"the dotted line marks official network coverage ({facts['value_pct']}% of populated areas), "
        "a different measure from household access, shown for context.",
        data=f"DOSM ICTHS {year} (Table 1.2) · official coverage as at {facts['as_of']}")

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
    f"Official coverage: [{facts['source_name']}]({facts['source_url']}) ({facts['published']})",
    "DOSM, ICT Use and Access by Individuals and Households Survey Report 2024 and 2025, Tables 1.2 and 6.4–6.6",
])
