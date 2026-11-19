"""Priorities: need rank vs value rank."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app_utils import data, ui

dt = data.district_table()

ui.page("Priorities: need vs value",
        "Where is the gap deepest, and where does each ringgit reach the most people? Ranks come with ranges "
        "because the inputs are uncertain.")

c1, c2 = st.columns(2)
scope = c1.radio("Compare districts in", ["Sarawak", "All Malaysia"], horizontal=True)
plan = c2.radio("Satellite plan", ["Residential (main case)", "Lite (sensitivity)"], horizontal=True)
case = "main" if plan.startswith("Residential") else "lite"
fix_col = "main_fix" if case == "main" else "main_fix_lite"

d = dt if scope == "All Malaysia" else dt[dt.state == "Sarawak"]
d = d[d[f"people_per_rm_m_{case}"].notna()].copy()
need, p05, p95 = (("rank_national", "rank_national_dirichlet_p05", "rank_national_dirichlet_p95") if scope == "All Malaysia"
                  else ("rank_sarawak", "rank_sarawak_dirichlet_p05", "rank_sarawak_dirichlet_p95"))
d["need_rank"] = d[need].rank(method="min").astype(int)  # re-ranked among districts that have a value
for k in ["main", "lite", "upper_bound"]:
    d[f"vr_{k}"] = d[f"people_per_rm_m_{k}"].rank(ascending=False, method="min")
d["value_rank"] = d[f"vr_{case}"].astype(int)
d["value_lo"] = d[["vr_main", "vr_lite", "vr_upper_bound"]].min(axis=1).astype(int)
d["value_hi"] = d[["vr_main", "vr_lite", "vr_upper_bound"]].max(axis=1).astype(int)
n = len(d)

fig = go.Figure()
size = d["planned_people_without_internet"]
sref = 2.0 * size.max() / (38 ** 2)
for cat in ["tower", "satellite"]:
    s = d[d[fix_col] == cat]
    if s.empty:
        continue
    fig.add_trace(go.Scatter(
        x=s.need_rank, y=s.value_rank, mode="markers", name=ui.FIX_LABELS[cat],
        marker=dict(size=s.planned_people_without_internet, sizemode="area", sizeref=sref, sizemin=5,
                    color=ui.FIX_COLOURS[cat], opacity=0.85, line=dict(color=ui.SURFACE, width=2)),
        customdata=np.stack([s.district, s.state, s.planned_people_without_internet, s[f"people_per_rm_m_{case}"],
                             s[f"cost_{case}_rm"] / 1e6, s[p05], s[p95], s.value_lo, s.value_hi,
                             np.where(s.small_sample_flag, "yes (low confidence)", "no")], axis=-1),
        hovertemplate="<b>%{customdata[0]}</b>, %{customdata[1]}<br>Need rank %{x} (weighting range %{customdata[5]:.0f}–%{customdata[6]:.0f})"
                      "<br>Value rank %{y} (range across cases %{customdata[7]}–%{customdata[8]})"
                      "<br>%{customdata[2]:,.0f} rural people reached · %{customdata[3]:,.0f} per RM1m"
                      "<br>5-year cost RM%{customdata[4]:,.1f}m<br>Small sample: %{customdata[9]}<extra></extra>"))
lab = d[(d.need_rank <= max(5, n // 6)) & (d.value_rank <= max(5, n // 6))] if scope == "Sarawak" else d.nsmallest(6, "need_rank")
for r in lab.itertuples():
    fig.add_annotation(x=r.need_rank, y=r.value_rank, text=r.district, showarrow=False, yshift=14,
                       font=dict(size=11, color=ui.INK_2))
mid = (n + 1) / 2
fig.add_hline(y=mid, line_color=ui.GRID, line_width=1)
fig.add_vline(x=mid, line_color=ui.GRID, line_width=1)
fig.add_annotation(x=1, y=1, xref="x", yref="y", text="High need · high value", showarrow=False, xanchor="right",
                   yanchor="top", font=dict(color=ui.MUTED, size=12), xshift=-4, yshift=-4)
ui.style(fig, height=560)
fig.update_xaxes(title="Need rank (1 = largest gap)", autorange="reversed")
fig.update_yaxes(title="Value rank (1 = most rural people reached per RM1m)", autorange="reversed")
st.plotly_chart(fig, width="stretch")
ui.what(f"Each bubble is a district ({scope.lower()}, {n} with costed settlements). Right = higher need (Gap Index), "
        "top = better value (rural people without home internet reached per RM1m of five-year infrastructure cost). "
        "Bubble size = rural people reached; colour = main fix. Settlements with a fixed network likely nearby are a "
        "take-up gap and are not costed here.")

st.subheader("Ranks with ranges")
tbl = d.sort_values(["need_rank"])[["district", "state", "need_rank", p05, p95, "value_rank", "value_lo", "value_hi",
                                     f"people_per_rm_m_{case}", f"students_per_rm_m_{case}", f"cost_{case}_rm",
                                     "planned_people_without_internet", "share_settlements_takeup_gap", fix_col,
                                     "small_sample_flag"]].copy()
tbl["Need range (weights)"] = tbl[p05].round().astype(int).astype(str) + "–" + tbl[p95].round().astype(int).astype(str)
tbl["Value range (cases)"] = tbl.value_lo.astype(str) + "–" + tbl.value_hi.astype(str)
tbl[f"cost_{case}_rm"] = (tbl[f"cost_{case}_rm"] / 1e6).round(1)
tbl["share_settlements_takeup_gap"] = (100 * tbl.share_settlements_takeup_gap).round(0)
tbl[fix_col] = tbl[fix_col].map(ui.FIX_LABELS)
out = tbl.rename(columns={"district": "District", "state": "State", "need_rank": "Need rank", "value_rank": "Value rank",
                          f"people_per_rm_m_{case}": "Rural people per RM1m", f"students_per_rm_m_{case}": "Pupils per RM1m",
                          f"cost_{case}_rm": "5-yr cost (RM m)", "planned_people_without_internet": "Rural people reached",
                          "share_settlements_takeup_gap": "Take-up settlements %", fix_col: "Main fix",
                          "small_sample_flag": "Small sample"})
cols = ["District"] + (["State"] if scope == "All Malaysia" else []) + [
    "Need rank", "Need range (weights)", "Value rank", "Value range (cases)", "Rural people per RM1m", "Pupils per RM1m",
    "5-yr cost (RM m)", "Rural people reached", "Take-up settlements %", "Main fix", "Small sample"]
st.dataframe(out[cols], hide_index=True, width="stretch",
             column_config={"Rural people per RM1m": st.column_config.NumberColumn(format="%.0f"),
                            "Pupils per RM1m": st.column_config.NumberColumn(format="%.0f"),
                            "Rural people reached": st.column_config.NumberColumn(format="%.0f")})
excluded = (dt if scope == "All Malaysia" else dt[dt.state == "Sarawak"])
excluded = excluded[excluded[f"people_per_rm_m_{case}"].isna()]
ui.what("Need range: 5th–95th percentile rank over 1,000 random index weightings. Value range: lowest and highest "
        "value rank across the Residential, Lite and upper-bound cost cases (scaling all costs ±30% leaves ranks "
        "unchanged). Small-sample districts have extra uncertainty from their survey margin of error."
        + (f" Not shown ({len(excluded)}): districts with no costed settlements." if len(excluded) else ""))

ui.footer([
    "Need: Connectivity Gap Index (DOSM ICTHS 2025, Ookla, OpenDOSM income and population); see Method",
    "Value: costing on rural MOE schools (Jun 2022) and DOSM Census 2020; costs from config/costs.yaml (estimates)",
])
