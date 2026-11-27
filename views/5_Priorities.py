"""Where to invest: the one headline reference cost, need rank vs people reached per RM1m, ranks, budget planner."""
import math

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from app_utils import data, ui

st.set_page_config(page_title="Where to invest · Beyond Coverage", layout="wide")

dt = data.district_table()
quarter = dt["ookla_quarter"].dropna().iloc[0]
access_year = int(dt["access_year"].dropna().iloc[0])
DATA = f"DOSM ICTHS {access_year} · Ookla {quarter} · HIES 2024 · Census 2020 · MOE school list, June 2022 · config/costs.yaml"

ui.page("Where to invest",
        "Need score first (where the gap is deepest), then people reached per RM1m (where each ringgit reaches the most "
        "people). Ranks come with ranges because the inputs are uncertain.")

# --- the ONE headline cost, shown once, with its range; every other case is a sensitivity (all read from data)
co = data.csv("costing_districts")
ref, lite, m30, p30 = (co[c].sum() for c in ("cost_main_rm", "cost_lite_rm", "cost_cost_minus30_rm", "cost_cost_plus30_rm"))
ref_lo, ref_hi = min(lite, m30), max(p30, ref)


def bn(v):
    return f"{v / 1e9:,.2f}"


with st.container(border=True):
    st.markdown(f"<div style='font-size:0.9rem;color:{ui.INK_2}'>Reference cost, all Malaysia, five years "
                f"{ui.conf_badge('indicative')}</div>"
                f"<div style='font-size:2rem;font-weight:600;color:{ui.INK};line-height:1.3'>RM{bn(ref)}bn "
                f"<span style='font-size:1.1rem;font-weight:500;color:{ui.INK_2}'>(RM{bn(ref_lo)}–{bn(ref_hi)}bn)</span></div>"
                f"<div style='font-size:0.88rem;color:{ui.INK_2}'>Reference: if every settlement without a nearby network "
                "were served by towers or satellite only. Not a total across settlement types: take-up support (A) and "
                "small cells or community Wi-Fi (C) are not costed.</div>", unsafe_allow_html=True)
    with st.expander("Range and sensitivity cases"):
        sens = [("Range low: Lite satellite plan (sensitivity)", lite), ("All costs −30% (sensitivity)", m30),
                ("All costs +30% (sensitivity): range high", p30),
                ("Tower test on all households (sensitivity)", co["cost_rule_all_hh_rm"].sum()),
                ("Upper bound: adds a fibre PoP per take-up settlement (sensitivity, not a recommendation)",
                 co["cost_upper_bound_rm"].sum())]
        st.markdown("\n".join(f"- {k}: {ui.fmt_rm(v)}" for k, v in sens))
        st.caption("The range runs from the lowest of the Lite plan and −30% cases to the +30% case. Method & "
                   "limitations, section 4, explains each case.")
    ui.conf_legend()

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
first = d.sort_values("need_rank").iloc[0]
ui.finding(f"{first.district} has the highest need {'in Sarawak' if scope == 'Sarawak' else 'nationally'} "
           f"(rank 1, range {ui.range_text(first[p05], first[p95])})",
           f"Need score vs people reached per RM1m (estimates), {n} districts with costed settlements")

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
        hovertemplate="<b>%{customdata[0]}</b>, %{customdata[1]}<br>Need rank %{x} (range %{customdata[5]:.0f}–%{customdata[6]:.0f})"
                      "<br>People-reached-per-RM1m rank %{y} (range %{customdata[7]}–%{customdata[8]})"
                      "<br>%{customdata[2]:,.0f} rural people reached · %{customdata[3]:,.0f} per RM1m (estimate)"
                      "<br>5-year cost RM%{customdata[4]:,.1f}m (estimate)<br>Small sample: %{customdata[9]}<extra></extra>"))
# label the five districts highest on both axes, right next to their bubble (no leader lines)
lab = d.assign(score=d.need_rank + d.ben_rank).nsmallest(5, "score")
for _, r in lab.iterrows():
    # shift each label left by its own bubble radius (area sizemode: diameter px = sqrt(size / sizeref)) + white border
    radius = max(np.sqrt(r.planned_people_without_internet / sref), 5) / 2 + 2
    fig.add_annotation(x=r.need_rank, y=r.ben_rank, text=r.district, showarrow=False, xanchor="right",
                       xshift=-(radius + 3), font=dict(size=11, color=ui.INK), bgcolor="rgba(252,252,251,0.7)")
mid = (n + 1) / 2
fig.add_hline(y=mid, line_color=ui.GRID, line_width=1)
fig.add_vline(x=mid, line_color=ui.GRID, line_width=1)
# quadrant names (corners of the plot; axes are reversed so rank 1 is top-right)
for qx, qy, xa, ya, txt in ((1, 1, "right", "top", "<b>Act first</b>"),
                            (0, 1, "left", "top", "Cheap, lower need"),
                            (1, 0, "right", "bottom", "<b>High need, costly</b>"),
                            (0, 0, "left", "bottom", "Lower priority")):
    fig.add_annotation(x=qx, y=qy, xref="paper", yref="paper", xanchor=xa, yanchor=ya, text=txt, showarrow=False,
                       font=dict(size=11, color=ui.MUTED), bgcolor="rgba(252,252,251,0.8)")
ui.style(fig, height=560)
pad = max(1.0, 0.035 * n)  # room so the largest rank-1 bubble is not clipped at the plot edge
step = 5 if n <= 60 else 20
ticks = [1] + list(range(step, n + 1, step))  # no rank-0 tick in the padding
fig.update_xaxes(tickvals=ticks)
fig.update_yaxes(tickvals=ticks)
fig.update_xaxes(title="Need score rank (1 = largest gap)  → higher need", range=[n + 1.5, 1 - pad], zeroline=False)
fig.update_yaxes(title="People reached per RM1m, rank (1 = most, estimate)  → more", range=[n + 1.5, 1 - pad], zeroline=False)
ev = st.plotly_chart(fig, width="stretch", on_select="rerun", selection_mode="points", key="prio_chart")
try:
    pts = ev.selection["points"]
    sel = pts[0]["customdata"] if pts and "customdata" in pts[0] else None
except (AttributeError, KeyError, TypeError, IndexError):
    sel = None
if sel is not None:
    if st.button(f"Open {sel[0]} ({sel[1]}) in District profile", icon=":material/arrow_forward:"):
        ui.go_to_district(sel[1], sel[0])
ui.what([f"Each bubble is a district ({'Sarawak' if scope == 'Sarawak' else 'all Malaysia'}, {n} with costed "
         "settlements). Click one to open it.",
         "Right = higher need (Need score, the Connectivity Gap Index). Top = more people reached per RM1m (estimated "
         "beneficiaries: rural people without home internet reached per RM1m of five-year infrastructure cost).",
         "Top-right = high need and many people reached per RM1m. Bottom-right = high need but costly per person: "
         "check the Lite plan and the district's take-up share.",
         "Size = rural people reached; colour = reference cost-screen result (tower or satellite); labels = the five districts highest on both.",
         "Settlements with a fixed network likely nearby (take-up gap) are not costed here."],
        data=DATA)
ui.caveat()

# The beneficiaries-per-RM1m values sit close together, so this rank is secondary to need.
cl = data.csv("costing_clusters")
tower_keys = set(map(tuple, cl.loc[cl[f"category_{case}"] == "tower", ["state", "district"]].values))
has_tower = d[[(s, x) in tower_keys for s, x in zip(d["state"], d["district"])]]
sat_only = d[~d.index.isin(has_tower.index)][f"people_per_rm_m_{case}"]
top = sat_only.nlargest(min(15, len(sat_only)))
where = f"{'Sarawak' if scope == 'Sarawak' else 'all Malaysia'}, {'Residential' if case == 'main' else 'Lite'} plan"
pts = []
if len(top):
    close = top.max() <= 1.5 * top.min()  # 'close' = top value within 1.5x of the 15th
    pts.append(f"Satellite-only districts: people reached per RM1m {'are close together' if close else 'vary'} "
               f"(top {len(top)}: {top.min():,.0f} to {top.max():,.0f} per RM1m, {where}).")
if len(has_tower):
    nm = sorted(has_tower["district"])
    names = nm[0] if len(nm) == 1 else ", ".join(nm[:-1]) + " and " + nm[-1]
    pts.append(f"{names} score{'s' if len(has_tower) == 1 else ''} higher: "
               f"{'it has' if len(has_tower) == 1 else 'they have'} a settlement large enough for a tower, which reaches "
               "many people for one fixed cost.")
pts.append("With satellite, cost grows with every household, so small rank differences mean little: use this rank to "
           "spot districts that cost much more per person, not to order districts.")
st.markdown("**The Need score is the main ranking.**\n" + "".join(f"\n- {t}" for t in pts))

tbl = d.sort_values(["need_rank"]).copy()
top3 = tbl.head(3)
ui.finding("Highest need: " + ", ".join(f"{x['district']} (rank {int(x['need_rank'])}, range "
                                         f"{ui.range_text(x[p05], x[p95])})" for _, x in top3.iterrows()),
           "Ranks with ranges")
tbl["need"] = [ui.rank_short(r, a, b) for r, a, b in zip(tbl.need_rank, tbl[p05], tbl[p95])]
tbl["ben"] = [ui.rank_short(r, a, b) for r, a, b in zip(tbl.ben_rank, tbl.ben_lo, tbl.ben_hi)]
tbl["cost_m"] = tbl[f"cost_{case}_rm"] / 1e6
tbl["takeup_pct"] = 100 * tbl.share_settlements_takeup_gap
tbl["fix"] = tbl[fix_col].map(ui.FIX_LABELS)
tbl["small"] = ["Yes" if ui.isnum(v) and bool(v) else "No" for v in tbl.small_sample_flag]
# pupils per RM1m stays on District detail; the table keeps the columns needed to compare districts
ui.table(tbl, [("district", "District", None)] + ([("state", "State", None)] if scope == "All Malaysia" else []) + [
    ("need", "Need rank", lambda v: v, "Need rank (5th–95th percentile range over random index weightings)"),
    ("ben", "Per RM1m rank", lambda v: v, "People-reached-per-RM1m rank (estimated beneficiaries per RM1m; range "
                                          "across the Residential, Lite and upper-bound cost cases)"),
    (f"people_per_rm_m_{case}", "Per RM1m", ",.0f", "People reached per RM1m (estimated beneficiaries): rural people "
                                                    "without home internet in planned settlements per RM1m of five-year cost"),
    ("cost_m", "Ref. cost (RM m)", ",.1f", "Reference cost: estimated five-year tower or satellite cost, RM million"),
    ("planned_people_without_internet", "People reached", ",.0f", "Estimated rural people without home internet in "
                                                                  "planned (tower or satellite) settlements"),
    ("takeup_pct", "Take-up (%)", ".0f", "Share of rural settlements where our proxy suggests a fixed network is "
                                         "likely nearby (take-up gap)"),
    ("fix", "Ref. cost-screen result", None, "Reference cost-screen result: tower or satellite, whichever serves most "
                                             "rural people without home internet among planned settlements (towers and "
                                             "satellite only; not the settlement-type grouping)"),
    ("small", "Small sample", None, "Yes = DOSM estimate rests on a small inferred sample: low confidence"),
], download=f"beyond_coverage_priorities_{ui.slug(scope)}_{'residential' if case == 'main' else 'lite'}.csv", notes=[
    f"Beyond Coverage: need and estimated beneficiaries per RM1m, {where}.",
    "Need score (Connectivity Gap Index) is the main ranking. Need rank range: 5th-95th percentile over 1,000 random index weightings; "
    "per-RM1m rank range: lowest-highest across the Residential, Lite and upper-bound cost cases.",
    "ESTIMATES ONLY: costs, people reached and per-RM1m figures come from a cost screen, not a full cost-benefit "
    "comparison. Settlements with a fixed network likely nearby (proxy) are a take-up gap and are not costed.",
    f"Data: {DATA}.",
])
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
ui.what("Need rank range: 5th–95th percentile rank over 1,000 random index weightings. Beneficiaries rank range: lowest and "
        "highest rank across the Residential, Lite and upper-bound cost cases (scaling all costs ±30% leaves ranks "
        "unchanged). Small-sample districts carry extra uncertainty from their approximate margin of error."
        + (f" Not shown ({len(excluded)}): {why_txt}." if len(excluded) else ""),
        data=DATA)

# --- budget planner: fund districts in need order (not by beneficiaries per RM1m, which are close together)
bp_head = st.empty()  # finding title, filled once the budget is known
st.markdown("**Screening tool: estimates only, not a funding recommendation.**")
q = data.funding_queue(scope, case)
cl_scope = cl if scope == "All Malaysia" else cl[cl.state == "Sarawak"]
tk = cl_scope[cl_scope[f"category_{case}"] == "takeup_gap"]
if q.empty:
    ui.fallback("No planned (tower or satellite) settlements in this selection, so there is nothing to fund.")
else:
    total_m = q["cost"].sum() / 1e6
    step = 0.1
    top = math.ceil(total_m / step) * step  # slider end: the full planned cost, rounded up to the step
    budget_m = st.slider(f"Five-year budget, RM million ({where})", 0.0, top, value=round(top / 2 / step) * step,
                         step=step, format="RM%.1fm", key=f"budget_{scope}_{case}",
                         help="Up to the estimated five-year cost of every planned tower and satellite settlement in "
                              "this selection.")
    st.caption("Slider maximum: the reference cost of every planned tower and satellite settlement in this selection. "
               "Types A (take-up) and C (small cell or community Wi-Fi) are not costed.")
    budget = budget_m * 1e6
    # fund in order and stop at the first settlement the rest of the budget cannot cover, so need order is kept
    funded = q[q["cum_cost"] <= budget + 0.5]
    nxt = q.iloc[len(funded)] if len(funded) < len(q) else None
    per_d = q.groupby(["state", "district"], sort=False).agg(need_rank=("need_rank", "first"), n=("cost", "size"),
                                                           people=("people", "sum"), cost=("cost", "sum"))
    got = funded.groupby(["state", "district"], sort=False).agg(n_f=("cost", "size"), people_f=("people", "sum"),
                                                                cost_f=("cost", "sum"))
    per_d = per_d.join(got, how="left").fillna({"n_f": 0, "people_f": 0, "cost_f": 0})
    full = per_d[per_d.n_f == per_d.n]
    part = per_d[(per_d.n_f > 0) & (per_d.n_f < per_d.n)]
    used, reached = funded["cost"].sum(), funded["people"].sum()
    with bp_head.container():
        ui.finding(f"A {ui.fmt_rm(budget)} budget funds {len(full):,} district{'' if len(full) == 1 else 's'} fully and reaches "
                   f"an estimated {reached:,.0f} people" if len(funded) else f"A {ui.fmt_rm(budget)} budget funds no settlement yet",
                   "Budget planner: districts funded in order of need")
    m1, m2, m3 = st.columns(3)
    m1.metric("Budget used", ui.fmt_rm(used), help=f"Of {ui.fmt_rm(budget)} chosen; the rest cannot fund the next "
                                                  "settlement in line.")
    m2.metric("Districts funded", f"{len(full):,} fully · {len(part):,} partly",
              help=f"Of {len(per_d):,} districts with planned settlements.")
    m3.metric("Settlements funded", f"{len(funded):,} of {len(q):,}")
    m4, m5, m6 = st.columns(3)
    m4.metric("People reached (estimate)", ui.fmt_num(reached),
              help="Estimated rural people without home internet in the funded settlements.")
    m5.metric("People left unfunded (estimate)", ui.fmt_num(q["people"].sum() - reached),
              help="Estimated rural people without home internet in planned settlements this budget does not reach.")
    m6.metric("Take-up group, not in this budget", ui.fmt_num(tk["unconnected_people"].sum()) + " people",
              help=f"{len(tk):,} settlements where our proxy suggests a fixed network is likely nearby: they need "
                   "take-up support, not new infrastructure, so they are not costed or funded here.")
    if nxt is not None and len(funded):
        st.markdown(f"Next in line: a {ui.FIX_LABELS[nxt.category].lower()} settlement in **{nxt.district}** "
                    f"(need rank {int(nxt.need_rank)}), estimated {ui.fmt_rm(nxt.cost)}; "
                    f"{ui.fmt_rm(nxt.cum_cost - budget)} more budget would fund it.")
    fd = per_d[per_d.n_f > 0].reset_index()
    if len(fd):
        fd["status"] = ["Fully funded" if a == b else "Partly funded" for a, b in zip(fd.n_f, fd.n)]
        fd["sett"] = [f"{int(a):,} of {int(b):,}" for a, b in zip(fd.n_f, fd.n)]
        fd["cost_m"] = fd.cost_f / 1e6
        with st.expander(f"Funded districts ({len(fd):,})", expanded=len(fd) <= 12):
            ui.table(fd, [("district", "District", None)] + ([("state", "State", None)] if scope == "All Malaysia" else [])
                     + [("need_rank", "Need rank", ".0f", "Need score rank, 1 = highest need" + (" in Sarawak" if scope == "Sarawak" else " nationally")),
                        ("sett", "Settlements", lambda v: v, "Funded of planned (tower or satellite) settlements"),
                        ("people_f", "People reached", ",.0f", "Estimated rural people without home internet in "
                                                               "the funded settlements"),
                        ("cost_m", "Cost (RM m)", ",.1f", "Estimated five-year cost of the funded settlements"),
                        ("status", "Status", None)],
                     height=min(36 * (len(fd) + 1) + 4, 400) if len(fd) > 10 else "auto",
                     download=f"beyond_coverage_budget_{ui.slug(scope)}_{'residential' if case == 'main' else 'lite'}.csv",
                     notes=[f"Beyond Coverage budget planner, {where}, budget RM{budget_m:.1f}m. SCREENING TOOL: "
                            "estimates only, not a funding recommendation.",
                            "Order: districts by need (Need score rank), within a district cheapest cost per person "
                            "first; stops at the first settlement the budget cannot cover. Take-up-gap settlements "
                            "(fixed network likely nearby, proxy) are not in this budget.",
                            f"Data: {DATA}."])
    ui.what(["Funds districts by need (Need score rank, highest first); within a district, the cheapest tower or "
             "satellite settlements per person first.",
             "Stops at the first settlement the remaining budget cannot cover, so a lower-need district is never "
             "funded ahead of a higher-need one.",
             "Not ordered by estimated beneficiaries per RM1m: those values are close together.",
             "Take-up-gap settlements (fixed network likely nearby, our proxy) are not in this budget. " + ui.TAKEUP_TXT],
            data=DATA)
    ui.caveat()

ui.next_step("views/6_Method.py", "Method & limitations",
             "how the index and costs are built, and how sure we are.")
ui.footer([
    f"Need score: Connectivity Gap Index (DOSM ICTHS {access_year}, Ookla {quarter}, OpenDOSM income and population); see Method",
    "People reached per RM1m (estimated beneficiaries per RM1m): costing on rural MOE schools (June 2022) and DOSM Census 2020; costs from "
    "config/costs.yaml (estimates)",
])
