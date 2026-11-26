"""Fast consistency checks on data/processed and config (no Streamlit, no network).

Run: .venv\\Scripts\\python -m pytest tests
Every expected value is read from config/ or the processed files themselves; the reported totals are read
from docs/costing_method.md, so a stale document fails the test."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
CONFIG = ROOT / "config"
KEY = ["state", "district"]
# DOSM Table 3 districts with no polygon anywhere (their area sits inside Kuching and Beaufort): table only,
# so not indexed, not costed and not in districts.geojson (see CLAUDE.md / data/README.md)
NO_BOUNDARY = {("Sarawak", "Siburan"), ("Sabah", "Membakut")}
TAKEUP = "takeup_gap"


def yml(name: str) -> dict:
    return yaml.safe_load((CONFIG / f"{name}.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def gi() -> pd.DataFrame:
    return pd.read_csv(PROC / "gap_index_districts.csv")


@pytest.fixture(scope="module")
def cd() -> pd.DataFrame:
    return pd.read_csv(PROC / "costing_districts.csv")


@pytest.fixture(scope="module")
def cl() -> pd.DataFrame:
    return pd.read_csv(PROC / "costing_clusters.csv")


@pytest.fixture(scope="module")
def geo_keys() -> list[tuple[str, str]]:
    g = json.loads((PROC / "districts.geojson").read_text(encoding="utf-8"))
    return [(f["properties"]["state"], f["properties"]["district"]) for f in g["features"]]


@pytest.fixture(scope="module")
def unit() -> dict:
    """Five-year unit costs and break-evens, computed from costs.yaml as build_costing.py does."""
    c = yml("costs")
    t, s = c["tower"], c["satellite"]
    tower = t["capex_per_site_rm"]["central"] + 5 * t["opex_per_site_per_year_rm"]
    school = s["kit_rm"] + 60 * s["monthly_rm"]["business_from"]
    out = {"tower": tower, "school": school}
    for case, plan in (("main", "residential"), ("lite", "residential_lite")):
        term = s["kit_rm"] + 60 * s["monthly_rm"][plan]
        out[case] = {"terminal": term, "breakeven": tower / term}
    return out


def keys(df: pd.DataFrame) -> list[tuple[str, str]]:
    return list(zip(df["state"], df["district"]))


# --- index weights ---
def test_weights_sum_to_one():
    w = yml("weights")["weights"]
    assert math.isclose(sum(v["weight"] for v in w.values()), 1.0, abs_tol=1e-9)
    assert all(v["weight"] >= 0 for v in w.values())


# --- districts line up across files ---
@pytest.mark.parametrize("name,get", [("gap_index_districts", "gi"), ("costing_districts", "cd"),
                                      ("districts.geojson", "geo_keys")])
def test_no_duplicate_districts(name, get, request):
    k = request.getfixturevalue(get)
    k = keys(k) if isinstance(k, pd.DataFrame) else k
    dup = sorted({x for x in k if k.count(x) > 1})
    assert not dup, f"duplicate districts in {name}: {dup}"


def test_index_and_boundaries_match(gi, geo_keys):
    a, b = set(keys(gi)), set(geo_keys)
    assert a == b, f"only in gap index: {sorted(a - b)}; only in geojson: {sorted(b - a)}"


def test_costing_districts_are_indexed(gi, cd, cl):
    idx = set(keys(gi))
    assert set(keys(cd)) <= idx, f"costed but not indexed: {sorted(set(keys(cd)) - idx)}"
    assert set(keys(cl)) == set(keys(cd)), "clusters and district costing cover different districts"


def test_only_known_districts_lack_a_boundary(gi):
    t3 = pd.read_csv(PROC / "dosm_hh_ict_district_2025.csv")
    t3 = t3[t3["level"] != "state"]
    missing = set(keys(t3)) - set(keys(gi))
    assert missing == NO_BOUNDARY, f"Table 3 districts not indexed: {sorted(missing)}"
    assert not (NO_BOUNDARY & set(keys(gi))), "a no-boundary district has an index row"


# --- costs add up ---
@pytest.mark.parametrize("case", ["main", "lite"])
def test_cluster_costs_sum_to_district_costs(cl, cd, case):
    s = cl.groupby(KEY)[f"cost_{case}"].sum().rename("from_clusters")
    m = cd.set_index(KEY)[[f"cost_{case}_rm"]].join(s, how="outer")
    assert m.notna().all().all()
    assert np.allclose(m["from_clusters"], m[f"cost_{case}_rm"], rtol=1e-9, atol=0.5)


def reported_totals() -> dict:
    """Malaysia and Sarawak totals (RM bn) from the results table in docs/costing_method.md."""
    txt = (ROOT / "docs" / "costing_method.md").read_text(encoding="utf-8")
    out = {}
    for case, label in (("main", r"\*\*Main\*\* \(Residential, central\)"), ("lite", r"\*\*Lite plan\*\*")):
        m = re.search(label + r"\s*\|\s*\*\*RM([\d.]+)bn\*\*\s*\|\s*\*\*RM([\d.]+)bn\*\*", txt)
        assert m, f"results row for {case} not found in docs/costing_method.md"
        out[case] = (float(m.group(1)), float(m.group(2)))
    return out


@pytest.mark.parametrize("case", ["main", "lite"])
def test_totals_match_reported(cl, case):
    mys, sar = reported_totals()[case]
    tot = cl[f"cost_{case}"].sum() / 1e9
    tot_sar = cl.loc[cl["state"] == "Sarawak", f"cost_{case}"].sum() / 1e9
    assert round(tot, 2) == mys, f"Malaysia {case}: data RM{tot:.3f}bn vs docs RM{mys}bn"
    assert round(tot_sar, 2) == sar, f"Sarawak {case}: data RM{tot_sar:.3f}bn vs docs RM{sar}bn"


# --- plausible values ---
def test_no_negative_people_households_or_costs(cl, cd):
    ccols = ["households", "unconnected_households", "unconnected_people", "rural_households", "students"] + \
            [c for c in cl.columns if c.startswith("cost_")]
    dcols = [c for c in cd.columns if c.startswith(("cost_", "n_")) or "people" in c or c.startswith("rural_")
             or c.startswith("students") or c == "planned_students"]
    for df, cols, name in ((cl, ccols, "costing_clusters"), (cd, dcols, "costing_districts")):
        num = df[cols].select_dtypes("number")
        bad = [c for c in num.columns if (num[c] < 0).any()]
        assert not bad, f"negative values in {name}: {bad}"


def test_access_shares_within_0_100(gi, cl):
    acc = pd.read_csv(PROC / "dosm_hh_ict_district_2025.csv")
    for name, s in (("gap_index internet_pct", gi["internet_pct"]), ("gap_index access_gap", gi["access_gap"]),
                    ("clusters access_gap", cl["access_gap"]), ("Table 3.1 internet_pct", acc["internet_pct"])):
        s = s.dropna()
        assert ((s >= 0) & (s <= 100)).all(), f"{name} outside 0-100: {s[(s < 0) | (s > 100)].tolist()[:5]}"
    assert np.allclose(gi["internet_pct"] + gi["access_gap"], 100, atol=1e-6)


# --- the cost rules, recomputed from costs.yaml ---
@pytest.mark.parametrize("case", ["main", "lite"])
def test_satellite_cost_formula(cl, unit, case):
    sat = cl[cl[f"category_{case}"] == "satellite"]
    assert len(sat), "no satellite settlements"
    want = sat["unconnected_households"] * unit[case]["terminal"] + unit["school"]
    assert np.allclose(sat[f"cost_{case}"], want, rtol=1e-9, atol=0.5)


def test_tower_cost_and_takeup_cost(cl, unit):
    for case in ("main", "lite"):
        assert np.allclose(cl.loc[cl[f"category_{case}"] == "tower", f"cost_{case}"], unit["tower"])
        assert (cl.loc[cl[f"category_{case}"] == TAKEUP, f"cost_{case}"] == 0).all()


@pytest.mark.parametrize("case", ["main", "lite"])
def test_tower_decision_uses_unconnected_households(cl, unit, case):
    want = np.where(cl["fixed_nearby"], TAKEUP,
                    np.where(cl["unconnected_households"] >= unit[case]["breakeven"], "tower", "satellite"))
    diff = cl[cl[f"category_{case}"] != want]
    assert diff.empty, f"{len(diff)} settlements break the rule, e.g. {diff[['district', 'school_code']].head(3).values.tolist()}"


def test_rule_sensitivity_uses_all_households(cl, unit):
    want = np.where(cl["fixed_nearby"], TAKEUP,
                    np.where(cl["households"] >= unit["main"]["breakeven"], "tower", "satellite"))
    assert (cl["category_rule_all_hh"] == want).all()


def test_breakeven_matches_config_note(unit):
    """costs.yaml states the rounded break-evens; they must agree with the unit costs."""
    be = yml("costs")["decision_rule"]["breakeven_households_vs_starlink"]
    assert round(unit["main"]["breakeven"]) == be["residential"]
    assert round(unit["lite"]["breakeven"]) == be["residential_lite"]


# --- budget planner funding order (Priorities page) ---
@pytest.mark.parametrize("scope", ["Sarawak", "All Malaysia"])
@pytest.mark.parametrize("case", ["main", "lite"])
def test_funding_queue_order(cl, scope, case):
    import sys

    sys.path.insert(0, str(ROOT))
    from app_utils import data

    q = data.funding_queue(scope, case)
    sub = cl if scope == "All Malaysia" else cl[cl["state"] == "Sarawak"]
    planned = sub[sub[f"category_{case}"] != TAKEUP]
    assert len(q) == len(planned) and (q["category"] != TAKEUP).all()
    assert q["need_rank"].notna().all() and q["need_rank"].is_monotonic_increasing, "not in need order"
    # each district's settlements are contiguous, cheapest per person first
    runs = (q["district"] != q["district"].shift()).cumsum()
    assert runs.nunique() == q.groupby(["state", "district"]).ngroups
    assert all(g["cost_per_person"].is_monotonic_increasing for _, g in q.groupby(["state", "district"]))
    assert math.isclose(q["cost"].sum(), planned[f"cost_{case}"].sum(), rel_tol=1e-12)
    assert np.allclose(q["cum_cost"].iloc[-1], q["cost"].sum())


# --- settlement attributes and types (build_settlements.py; expert feedback, Nov 2026) ---
@pytest.fixture(scope="module")
def st_() -> pd.DataFrame:
    return pd.read_csv(PROC / "settlements.csv")


@pytest.fixture(scope="module")
def stypes() -> dict:
    return yml("settlement_types")


def test_settlements_match_clusters(st_, cl):
    k = ["state", "district", "school_code"]
    assert len(st_) == len(cl) and not st_.duplicated(k).any()
    assert set(map(tuple, st_[k].astype(str).values)) == set(map(tuple, cl[k].astype(str).values))


@pytest.mark.parametrize("value,flag", [("terrain", "terrain_missing"), ("road", "road_missing")])
def test_attribute_missing_is_flagged(st_, value, flag):
    """No silent NaN: a value is empty exactly when its *_missing flag is set."""
    assert (st_[value].isna() == st_[flag]).all()
    num = {"terrain": "slope_mean_deg", "road": "road_km"}[value]
    assert (st_[num].isna() == st_[flag]).all()


def test_mobile_quality_classes(st_, stypes):
    c = stypes["mobile_quality"]
    assert st_["mobile_quality"].notna().all()
    assert set(st_["mobile_quality"]) <= {"good", "weak", "no_tests"}
    near = st_["mobile_tile_km"].notna()
    assert (st_.loc[~near, "mobile_quality"] == "no_tests").all()
    assert (st_.loc[near, "mobile_tile_km"] <= c["search_km"] + 1e-9).all()
    good = st_["mobile_tile_dl_mbps"] >= c["good_min_mbps"]
    assert (st_.loc[near & good, "mobile_quality"] == "good").all()
    assert (st_.loc[near & ~good, "mobile_quality"] == "weak").all()


def test_terrain_and_road_classes_follow_config(st_, stypes):
    t, r = stypes["terrain"], stypes["road"]
    s = st_.dropna(subset=["slope_mean_deg"])
    want = np.select([s.slope_mean_deg < t["flat_max_deg"], s.slope_mean_deg >= t["steep_min_deg"]], ["flat", "steep"], "hilly")
    assert (s["terrain"] == want).all()
    s = st_.dropna(subset=["road_km"])
    want = np.select([s.road_km <= r["near_max_km"], s.road_km > r["very_far_min_km"]], ["near", "very_far"], "far")
    assert (s["road"] == want).all()


def test_every_settlement_has_exactly_one_type(st_, stypes, unit):
    assert st_["settlement_type"].notna().all()
    assert set(st_["settlement_type"]) <= set(stypes["types"]) | {"U"}
    # recompute the ordered rules
    be = unit["main"]["breakeven"]
    nf, below = ~st_.fixed_nearby, st_.unconnected_households < be
    iso = (st_.slope_mean_deg >= stypes["terrain"]["steep_min_deg"]) | (st_.road_km > stypes["road"]["very_far_min_km"])
    want = np.select([st_.fixed_nearby, nf & ~below, nf & below & (st_.mobile_quality == "good"), nf & below & iso,
                      nf & below & (st_.slope_mean_deg.isna() | st_.road_km.isna())], ["A", "B", "E", "D", "U"], "C")
    diff = st_[st_.settlement_type != want]
    assert diff.empty, f"{len(diff)} settlements break the type rules, e.g. {diff.school_code.head(3).tolist()}"


def test_type_costs_reconcile(st_, cl, stypes, unit):
    """Costed types use cited unit costs only; B and D equal the existing tower / satellite screen costs."""
    costed = st_.settlement_type.map({k: v["costed"] for k, v in stypes["types"].items()}).fillna("none")
    assert (st_["type_costed"] == (costed != "none")).all()
    assert st_.loc[~st_.type_costed, "type_cost_5yr_rm"].isna().all()
    assert st_.loc[st_.type_costed, "type_cost_5yr_rm"].notna().all()
    m = st_.merge(cl[["state", "district", "school_code", "cost_main", "category_main"]],
                  on=["state", "district", "school_code"], suffixes=("", "_cl"))
    for k, cat in (("B", "tower"), ("D", "satellite")):
        sub = m[m.settlement_type == k]
        assert (sub.category_main_cl == cat).all()
        assert np.allclose(sub.type_cost_5yr_rm, sub.cost_main_cl, rtol=1e-9, atol=0.5)
    c = yml("costs")["fwa"]
    fwa = m[m.settlement_type == "E"]
    assert np.allclose(fwa.type_cost_5yr_rm, fwa.unconnected_households * (c["cpe_rm"] + 60 * c["monthly_rm"]))
    assert c["five_year_cost_per_household_rm"] == c["cpe_rm"] + 60 * c["monthly_rm"]
    # the existing screen is untouched: every settlement keeps its cost_main
    assert np.allclose(m.cost_main, m.cost_main_cl)


def test_type_summary_matches_settlements(st_):
    sm = pd.read_csv(PROC / "settlement_types_summary.csv")
    for scope, sub in (("All Malaysia", st_), ("Sarawak", st_[st_.state == "Sarawak"])):
        g = sub.groupby("settlement_type").agg(n=("school_code", "size"), p=("unconnected_people", "sum"))
        s = sm[sm.scope == scope].set_index("settlement_type")
        assert s.settlements.sum() == len(sub)
        for k, row in g.iterrows():
            assert s.loc[k, "settlements"] == row.n and math.isclose(s.loc[k, "people_without_home_internet"], row.p, rel_tol=1e-9)
