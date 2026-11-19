"""Priorities: need rank vs estimated-beneficiaries-per-RM1m rank."""
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from app_utils import data, ui

st.set_page_config(page_title="Priorities · Beyond Coverage", layout="wide")

dt = data.district_table()
quarter = dt["ookla_quarter"].dropna().iloc[0]
access_year = int(dt["access_year"].dropna().iloc[0])
DATA = f"DOSM ICTHS {access_year} · Ookla {quarter} · HIES 2024 · Census 2020 · MOE school list, June 2022 · config/costs.yaml"

ui.page("Priorities: need vs estimated beneficiaries per RM1m",
        "Where is the gap deepest, and where would each ringgit reach the most people? Ranks come with ranges because "
        "the inputs are uncertain.")

c1, c2 = st.columns(2)
scope = c1.radio("Compare districts in", ["Sarawak", "All Malaysia"], horizontal=True, key="prio_scope")
plan = c2.radio("Satellite plan", ["Residential (main case)", "Lite (sensitivity)"], horizontal=True, key="prio_plan")
case = "main" if plan.startswith("Residential") else "lite"
fix_col = "main_fix" if case == "main" else "main_fix_lite"

d = dt if scope == "All Malaysia" else dt[dt.state == "Sarawak"]
need_col = "rank_national" if scope == "All Malaysia" else "rank_sarawak"
d = d[d[f"people_per_rm_m_{case}"].notna() & d[need_col].notna()].copy()
if d.empty:
    ui.fallback("No district in this selection has costed settlements, so there is nothing to rank.")
    st.stop()
need, p05, p95 = (("rank_national", "rank_national_dirichlet_p05", "rank_national_dirichlet_p95") if scope == "All Malaysia"
                  else ("rank_sarawak", "rank_sarawak_dirichlet_p05", "rank_sarawak_dirichlet_p95"))
d["need_rank"] = d[need].rank(method="min").astype(int)  # re-ranked among districts that have a cost
for k in ["main", "lite", "upper_bound"]:
    d[f"br_{k}"] = d[f"people_per_rm_m_{k}"].rank(ascending=False, method="min")
d["ben_rank"] = d[f"br_{case}"].astype(int)
d["ben_lo"] = d[["br_main", "br_lite", "br_upper_bound"]].min(axis=1).astype(int)
d["ben_hi"] = d[["br_main", "br_lite", "br_upper_bound"]].max(axis=1).astype(int)
n = len(d)

fig = go.Figure()
size = d["planned_people_without_internet"]
sref = 2.0 * size.max() / (36 ** 2)
for cat in ["tower", "satellite"]:
    s = d[d[fix_col] == cat]
    if s.empty:
        continue
    fig.add_trace(go.Scatter(
        x=s.need_rank, y=s.ben_rank, mode="markers", name=ui.FIX_LABELS[cat],
        marker=dict(size=s.planned_people_without_internet, sizemode="area", sizeref=sref, sizemin=5,
                    color=ui.FIX_COLOURS[cat], opacity=0.85, line=dict(color=ui.SURFACE, width=2)),
        customdata=np.stack([s.district, s.state, s.planned_people_without_internet, s[f"people_per_rm_m_{case}"],
                             s[f"cost_{case}_rm"] / 1e6, s[p05], s[p95], s.ben_lo, s.ben_hi,
                             np.where(s.small_sample_flag, "yes (low confidence)", "no")], axis=-1),
        hovertemplate="<b>%{customdata[0]}</b>, %{customdata[1]}<br>Need rank %{x} (weighting range %{customdata[5]:.0f}–%{customdata[6]:.0f})"
                      "<br>Beneficiaries-per-RM1m rank %{y} (range across cost cases %{customdata[7]}–%{customdata[8]})"
                      "<br>%{customdata[2]:,.0f} rural people reached · %{customdata[3]:,.0f} per RM1m (estimate)"
                      "<br>5-year cost RM%{customdata[4]:,.1f}m (estimate)<br>Small sample: %{customdata[9]}<extra></extra>"))
# label only the top districts on both axes, with alternating offsets so labels don't collide
lab = d.assign(score=d.need_rank + d.ben_rank).nsmallest(5, "score").sort_values("need_rank")
# labels stacked in an evenly spaced column left of the cluster (data units), sorted top to bottom, with leader lines
lab = lab.sort_values("ben_rank")
col_x = lab.need_rank.max() + max(3, n * 0.18)
step = max(2.5, n * 0.07)
for i, r in enumerate(lab.itertuples()):
    fig.add_annotation(x=r.need_rank, y=r.ben_rank, text=r.district, showarrow=True, arrowhead=0, arrowwidth=1,
                       arrowcolor=ui.MUTED, axref="x", ayref="y", ax=col_x, ay=1 + i * step, xanchor="right",
                       font=dict(size=11, color=ui.INK), bgcolor="rgba(252,252,251,0.85)")
mid = (n + 1) / 2
fig.add_hline(y=mid, line_color=ui.GRID, line_width=1)
fig.add_vline(x=mid, line_color=ui.GRID, line_width=1)
ui.style(fig, height=560)
fig.update_xaxes(title="Need rank (1 = largest gap)  → higher need", range=[n + 1.5, 0.4], zeroline=False)
fig.update_yaxes(title="Estimated beneficiaries per RM1m, rank (1 = most)  → more", range=[n + 1.5, 0.4], zeroline=False)
st.plotly_chart(fig, width="stretch")
ui.what(f"Each bubble is a district ({'Sarawak' if scope == 'Sarawak' else 'all Malaysia'}, {n} with costed settlements). Right = higher need (Gap Index); "
        "top = more estimated beneficiaries per RM1m (rural people without home internet reached per RM1m of five-year "
        "infrastructure cost). Bubble size = rural people reached; colour = main fix. Labels mark the five districts "
        "highest on both. Settlements with a fixed network likely nearby are a take-up gap and are not costed here.",
        data=DATA)
ui.caveat()

st.subheader("Ranks with ranges")
tbl = d.sort_values(["need_rank"])[["district", "state", "need_rank", p05, p95, "ben_rank", "ben_lo", "ben_hi",
                                     f"people_per_rm_m_{case}", f"students_per_rm_m_{case}", f"cost_{case}_rm",
                                     "planned_people_without_internet", "share_settlements_takeup_gap", fix_col,
                                     "small_sample_flag"]].copy()
tbl["Need range (weights)"] = [ui.range_text(a, b) for a, b in zip(tbl[p05], tbl[p95])]
tbl["Beneficiaries rank range (cost cases)"] = [ui.range_text(a, b) for a, b in zip(tbl.ben_lo, tbl.ben_hi)]
tbl[f"cost_{case}_rm"] = (tbl[f"cost_{case}_rm"] / 1e6).round(1)
tbl["share_settlements_takeup_gap"] = (100 * tbl.share_settlements_takeup_gap).round(0)
tbl[fix_col] = tbl[fix_col].map(ui.FIX_LABELS)
out = tbl.rename(columns={"district": "District", "state": "State", "need_rank": "Need rank",
                          "ben_rank": "Beneficiaries per RM1m rank",
                          f"people_per_rm_m_{case}": "Est. rural people per RM1m", f"students_per_rm_m_{case}": "Est. pupils per RM1m",
                          f"cost_{case}_rm": "Est. 5-yr cost (RM m)", "planned_people_without_internet": "Rural people reached",
                          "share_settlements_takeup_gap": "Take-up settlements %", fix_col: "Main fix",
                          "small_sample_flag": "Small sample"})
cols = ["District"] + (["State"] if scope == "All Malaysia" else []) + [
    "Need rank", "Need range (weights)", "Beneficiaries per RM1m rank", "Beneficiaries rank range (cost cases)",
    "Est. rural people per RM1m", "Est. pupils per RM1m", "Est. 5-yr cost (RM m)", "Rural people reached",
    "Take-up settlements %", "Main fix", "Small sample"]
st.dataframe(out[cols], hide_index=True, width="stretch",
             column_config={"District": st.column_config.TextColumn(width="medium"),
                            "Est. rural people per RM1m": st.column_config.NumberColumn(format="%.0f"),
                            "Est. pupils per RM1m": st.column_config.NumberColumn(format="%.0f"),
                            "Rural people reached": st.column_config.NumberColumn(format="%.0f")})
excluded = (dt if scope == "All Malaysia" else dt[dt.state == "Sarawak"])
excluded = excluded[excluded[f"people_per_rm_m_{case}"].isna()]
why = {
    "with all settlements in the take-up group (no infrastructure cost)":
        excluded.has_boundary & excluded.rural_settlements.notna(),
    "with no rural school": excluded.has_boundary & excluded.rural_settlements.isna(),
    "with no map boundary": ~excluded.has_boundary,
}
why_txt = "; ".join(f"{int(m.sum())} {k}" + (f" ({', '.join(excluded[m].district)})" if 0 < m.sum() <= 3 else "")
                    for k, m in why.items() if m.sum())
ui.what("Need range: 5th–95th percentile rank over 1,000 random index weightings. Beneficiaries rank range: lowest and "
        "highest rank across the Residential, Lite and upper-bound cost cases (scaling all costs ±30% leaves ranks "
        "unchanged). Small-sample districts carry extra uncertainty from their approximate margin of error."
        + (f" Not shown ({len(excluded)}): {why_txt}." if len(excluded) else ""),
        data=DATA)

ui.footer([
    f"Need: Connectivity Gap Index (DOSM ICTHS {access_year}, Ookla {quarter}, OpenDOSM income and population); see Method",
    "Estimated beneficiaries per RM1m: costing on rural MOE schools (June 2022) and DOSM Census 2020; costs from "
    "config/costs.yaml (estimates)",
])
