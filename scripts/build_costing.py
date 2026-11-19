"""Recommend a connectivity fix per settlement cluster, cost it per district, rank by value.

All costs are ESTIMATES from config/costs.yaml (public statements and news, not quotes).
Method: docs/costing_method.md.

Clusters
  One cluster per RURAL school (MOE list Jun 2022, LOKASI = "Luar Bandar"), all states, placed
  in districts.geojson by coordinates. Schools are anchors only; the "likely_no_fibre" flag is
  NOT used (it failed validation).
  households_per_cluster = district rural households / number of rural schools in the district
  district rural households = Census 2020 rural population / Census 2020 average household size
  New districts (Gedong, Lingga, Pantu, Sebuyau) are not in the 2020 Census. Their parent
  (the 2022 DOSM polygon they overlap most) supplies household size and rural share, and the
  parent's 2020 rural households are split between parent and new districts by 2026 population
  share, so no household is counted twice. Flagged (hh_source = "parent ...").
  unconnected_households = households x access_gap / 100 (district rate, ICTHS 2025)

Category per settlement (in order)
  takeup_gap  any Ookla fixed tile within 2 km of the school: "fixed network likely nearby:
              take-up gap" (PROXY). Take-up, not infrastructure, is the likely barrier, so these
              settlements are EXCLUDED from the infrastructure cost (counted and reported only).
  tower       households >= break-even (tower 5-yr cost / satellite 5-yr cost per terminal)
  satellite   otherwise: one terminal per unconnected household + one Business terminal for the school

5-year cost to provide service (users' mobile plans excluded)
  tower       capex + 5 x opex
  satellite   (kit + 60 x monthly) per terminal; school terminal uses the Business plan
  upper bound additionally costs each take-up-gap settlement as one fibre PoP (capex only;
              running cost UNSOURCED)
Cases: main (Residential, central costs), Lite plan, upper bound; also all costs -30% / +30%.

Value (planned = tower/satellite settlements)
  MAIN       people_per_rm_m = rural people without home internet in planned settlements per RM1m
  secondary  people_per_rm_m_district = whole-district people without home internet per RM1m
  students_per_rm_m = pupils of planned settlements' schools per RM1m (reported separately)
  Districts whose settlements are all take-up gap have no infrastructure cost and no value rank.

Usage: python scripts/build_costing.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
RAW, PROC = ROOT / "data" / "raw", ROOT / "data" / "processed"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_schools import assign_districts, latest_quarter, load_schools, tile_metrics  # noqa: E402

COSTS = ROOT / "config" / "costs.yaml"
CENSUS = RAW / "census" / "census_district.csv"
DOSM_2022 = RAW / "boundaries" / "dosm_administrative_2_district.geojson"
OUT_CLUSTERS = PROC / "costing_clusters.csv"
OUT_DISTRICTS = PROC / "costing_districts.csv"
FIBRE_RADIUS_KM = 2
FOCUS = "Sarawak"
TAKEUP = "takeup_gap"  # fixed network likely nearby: take-up gap (PROXY)


def unit_costs(c: dict, plan: str, scale: float = 1.0) -> dict:
    t, s, f = c["tower"], c["satellite"], c["fibre_pop"]
    tower = t["capex_per_site_rm"]["central"] + 5 * t["opex_per_site_per_year_rm"]
    sat = s["kit_rm"] + 60 * s["monthly_rm"][plan]
    school = s["kit_rm"] + 60 * s["monthly_rm"]["business_from"]
    u = {"tower": tower * scale, "satellite_terminal": sat * scale, "satellite_school": school * scale,
         "fibre_pop": f["capex_per_site_rm"]["central"] * scale}
    u["breakeven_households"] = tower / sat  # unchanged by a uniform scale
    return u


def census_households(d: gpd.GeoDataFrame) -> pd.DataFrame:
    """Rural households per current district (2020 Census; new districts split from parent)."""
    amap = {(r.state, r.alias): r.canonical for r in pd.read_csv(PROC / "district_aliases.csv").itertuples()}
    c = pd.read_csv(CENSUS, encoding="utf-8-sig", usecols=range(40))
    c = c[c["year"] == c["year"].max()].copy()
    c["district"] = [amap.get((s, x), x) for s, x in zip(c["state"], c["district"])]
    c["rural_pop"] = c["density_rural"].fillna(0)  # column holds rural POPULATION; blank = 0
    c = c[["state", "district", "population_total", "rural_pop", "household_size_avg"]]
    c["census_year"] = 2020

    pop = pd.read_parquet(RAW / "population_district.parquet")
    pop = pop[(pop["sex"] == "both") & (pop["age"] == "overall") & (pop["ethnicity"] == "overall")]
    pop = pop[pop["date"] == pop["date"].max()]
    pop["district"] = [amap.get((s, x), x) for s, x in zip(pop["state"], pop["district"])]
    pop2026 = dict(zip(zip(pop["state"], pop["district"]), pop["population"]))

    # parents of districts missing from the census: 2022 DOSM polygon with the largest overlap
    have = set(zip(c["state"], c["district"]))
    new = d[[(s, x) not in have for s, x in zip(d["state"], d["district"])]]
    old = gpd.read_file(DOSM_2022)
    old["geometry"] = old.geometry.make_valid()
    old = old.to_crs(3375)
    old["district"] = [amap.get((s, x), x) for s, x in zip(old["state"], old["district"].str.strip())]
    parent = {}
    for r in new.to_crs(3375).itertuples():
        ov = old[old["state"] == r.state].intersection(r.geometry).area
        parent[(r.state, r.district)] = (r.state, old.loc[ov.idxmax(), "district"])

    rows = []
    cen = c.set_index(["state", "district"])
    families: dict[tuple, list] = {}
    for child, par in parent.items():
        families.setdefault(par, []).append(child)
    for key, r in cen.iterrows():
        rural_hh = r["rural_pop"] / r["household_size_avg"]
        if key not in families:
            rows.append({"state": key[0], "district": key[1], "rural_households": rural_hh,
                         "household_size": r["household_size_avg"], "rural_share": r["rural_pop"] / r["population_total"],
                         "hh_source": "Census 2020"})
            continue
        members = [key] + families[key]
        total = sum(pop2026[m] for m in members)
        for m in members:
            share = pop2026[m] / total
            if m == key:
                src = f"Census 2020, minus new districts ({', '.join(x[1] for x in families[key])}) by 2026 population"
            else:
                src = f"parent {key[1]} (Census 2020), split by 2026 population"
            rows.append({"state": m[0], "district": m[1], "rural_households": rural_hh * share,
                         "household_size": r["household_size_avg"], "rural_share": r["rural_pop"] / r["population_total"],
                         "hh_source": src})
    out = pd.DataFrame(rows)
    out["census_year"] = 2020
    return out, parent


def categorise(clusters: pd.DataFrame, u: dict) -> pd.Series:
    """takeup_gap if a fixed tile is within 2 km (PROXY: fixed network likely nearby), else
    tower if households >= break-even, else satellite."""
    return pd.Series(np.where(clusters["fixed_nearby"], TAKEUP,
                              np.where(clusters["households"] >= u["breakeven_households"], "tower", "satellite")),
                     index=clusters.index)


def cost(clusters: pd.DataFrame, cat: pd.Series, u: dict, upper_bound: bool = False) -> pd.Series:
    """5-yr cost. Take-up-gap settlements cost 0 (no infrastructure), except in the upper-bound
    case, where each is costed as one fibre PoP (capex only)."""
    sat = clusters["unconnected_households"] * u["satellite_terminal"] + u["satellite_school"]
    takeup = u["fibre_pop"] if upper_bound else 0.0
    return pd.Series(np.select([cat == TAKEUP, cat == "tower"], [takeup, u["tower"]], sat), index=clusters.index)


def main_fix(clusters: pd.DataFrame, cat: pd.Series) -> pd.Series:
    """District's main fix = tower or satellite, whichever serves more unconnected households among
    the planned (non take-up) settlements; 'none (take-up gap only)' if there are none."""
    idx = pd.MultiIndex.from_frame(clusters[["state", "district"]].drop_duplicates())
    infra = clusters.assign(cat=cat)[cat != TAKEUP]
    t = infra.groupby(["state", "district", "cat"])["unconnected_households"].sum()
    dom = t.groupby(level=[0, 1]).idxmax().map(lambda k: k[2])
    return dom.reindex(idx).fillna("none (take-up gap only)")


def main() -> None:
    c = yaml.safe_load(COSTS.read_text(encoding="utf-8"))
    d = gpd.read_file(PROC / "districts.geojson")
    hh, parent = census_households(d)
    gi = pd.read_csv(PROC / "gap_index_districts.csv")

    # --- rural schools as cluster anchors, with fixed-tile distances
    sch = assign_districts(load_schools(states=None), d)
    rural = sch[(sch["urban_rural"] == "Luar Bandar") & sch["district"].notna()].copy()
    year, q = latest_quarter()
    cols = ["tile_x", "tile_y", "tests", "avg_d_kbps"]
    fixed = pd.read_parquet(PROC / f"ookla_my_fixed_{year}q{q}.parquet", columns=cols)
    mobile = pd.read_parquet(PROC / f"ookla_my_mobile_{year}q{q}.parquet", columns=cols)
    m = tile_metrics(rural, fixed, mobile)
    rural = rural.join(m[["fixed_tiles_2km", "nearest_fixed_tile_km"]])
    rural["fixed_nearby"] = rural["fixed_tiles_2km"].fillna(0) > 0

    n_rural = rural.groupby(["state", "district"]).size().rename("rural_schools")
    cl = rural.merge(n_rural.reset_index(), on=["state", "district"]).merge(hh, on=["state", "district"], how="left")
    cl = cl.merge(gi[["state", "district", "access_gap", "small_sample_flag"]], on=["state", "district"], how="left")
    miss = cl[cl["rural_households"].isna() | cl["access_gap"].isna()]
    assert miss.empty, f"clusters without households or access data:\n{miss[['state', 'district']].drop_duplicates()}"
    cl["households"] = cl["rural_households"] / cl["rural_schools"]
    cl["unconnected_households"] = cl["households"] * cl["access_gap"] / 100
    cl["unconnected_people"] = cl["unconnected_households"] * cl["household_size"]

    # --- scenarios: category and 5-yr cost per settlement
    scen = {"main": unit_costs(c, "residential"), "lite": unit_costs(c, "residential_lite"),
            "cost_minus30": unit_costs(c, "residential", 0.7), "cost_plus30": unit_costs(c, "residential", 1.3)}
    for k, u in scen.items():
        cl[f"category_{k}"] = categorise(cl, u)
        cl[f"cost_{k}"] = cost(cl, cl[f"category_{k}"], u)
    cl["cost_upper_bound"] = cost(cl, cl["category_main"], scen["main"], upper_bound=True)

    cl_out = cl[["state", "district", "school_code", "school_name", "students", "lon", "lat", "rural_schools",
                 "rural_households", "household_size", "hh_source", "households", "access_gap",
                 "unconnected_households", "unconnected_people", "small_sample_flag", "fixed_tiles_2km",
                 "nearest_fixed_tile_km", "fixed_nearby"]
                + [f"{p}_{k}" for k in scen for p in ("category", "cost")] + ["cost_upper_bound"]].copy()
    cl_out.insert(0, "ookla_quarter", f"{year}Q{q}")
    cl_out.sort_values(["state", "district", "school_code"]).to_csv(OUT_CLUSTERS, index=False)

    # --- districts
    planned = cl["category_main"] != TAKEUP
    key = ["state", "district"]
    g, gp, gt = cl.groupby(key), cl[planned].groupby(key), cl[~planned].groupby(key)
    dist = pd.DataFrame({
        "rural_settlements": g.size(),
        "household_size": g["household_size"].first(),
        "hh_source": g["hh_source"].first(),
        "rural_households": g["rural_households"].first(),
        "rural_people_without_internet": g["unconnected_people"].sum(),
        "students_rural_schools": g["students"].sum(),
        "n_takeup_gap": gt.size(),
        "takeup_gap_people_without_internet": gt["unconnected_people"].sum(),
        "n_tower": gp["category_main"].apply(lambda s: int((s == "tower").sum())),
        "n_satellite": gp["category_main"].apply(lambda s: int((s == "satellite").sum())),
        "planned_people_without_internet": gp["unconnected_people"].sum(),
        "planned_students": gp["students"].sum(),
    })
    fill0 = ["n_takeup_gap", "takeup_gap_people_without_internet", "n_tower", "n_satellite",
             "planned_people_without_internet", "planned_students"]
    dist[fill0] = dist[fill0].fillna(0)
    for c_ in ["n_takeup_gap", "n_tower", "n_satellite"]:
        dist[c_] = dist[c_].astype(int)
    dist["share_settlements_takeup_gap"] = dist["n_takeup_gap"] / dist["rural_settlements"]
    for k in [*scen, "upper_bound"]:
        dist[f"cost_{k}_rm"] = g[f"cost_{k}"].sum()
    dist["main_fix"] = main_fix(cl, cl["category_main"])
    dist["main_fix_lite"] = main_fix(cl, cl["category_lite"])
    dist = dist.reset_index().merge(
        gi[["state", "district", "cgi", "rank_national", "rank_sarawak", "small_sample_flag",
            "people_without_home_internet", "population_k", "access_gap"]], on=key, how="left")

    def per_m(num: pd.Series, cost_: pd.Series) -> pd.Series:
        return (num / (cost_ / 1e6)).where(cost_ > 0)

    for k in scen:
        # MAIN value metric: rural people without home internet in the planned settlements per RM1m
        dist[f"people_per_rm_m_{k}"] = per_m(dist["planned_people_without_internet"], dist[f"cost_{k}_rm"])
        dist[f"students_per_rm_m_{k}"] = per_m(dist["planned_students"], dist[f"cost_{k}_rm"])
        # secondary: whole-district people without home internet (urban included) per RM1m
        dist[f"people_per_rm_m_district_{k}"] = per_m(dist["people_without_home_internet"], dist[f"cost_{k}_rm"])
    # upper bound covers every rural settlement (take-up group costed as PoPs)
    dist["people_per_rm_m_upper_bound"] = per_m(dist["rural_people_without_internet"], dist["cost_upper_bound_rm"])
    dist["students_per_rm_m_upper_bound"] = per_m(dist["students_rural_schools"], dist["cost_upper_bound_rm"])

    def rank(col: str, mask: pd.Series | None = None) -> pd.Series:
        s = dist[col] if mask is None else dist[col].where(mask)
        return s.rank(ascending=False, method="min").astype("Int64")

    sk = dist["state"] == FOCUS
    dist["value_rank_national"] = rank("people_per_rm_m_main")
    dist["value_rank_sarawak"] = rank("people_per_rm_m_main", sk)
    for k in ["lite", "cost_minus30", "cost_plus30", "upper_bound"]:
        dist[f"value_rank_national_{k}"] = rank(f"people_per_rm_m_{k}")
    dist["fibre_pop_opex_unsourced_upper_bound"] = dist["n_takeup_gap"] > 0
    dist.insert(0, "ookla_quarter", f"{year}Q{q}")
    dist = dist.sort_values(["value_rank_national", "state", "district"], na_position="last")
    dist.to_csv(OUT_DISTRICTS, index=False)

    # --- report
    u = scen["main"]
    print(f"unit 5-yr costs (main, Residential): tower RM{u['tower']:,.0f}, satellite terminal RM{u['satellite_terminal']:,.0f}, "
          f"school terminal RM{u['satellite_school']:,.0f}; fibre PoP RM{u['fibre_pop']:,.0f} (capex only, upper bound only); "
          f"break-even {u['breakeven_households']:.1f} households (Lite {scen['lite']['breakeven_households']:.1f})")
    print("new-district parents (largest overlap with 2022 DOSM polygon):", {k[1]: v[1] for k, v in parent.items()})
    no_cl = gi[~gi.set_index(key).index.isin(dist.set_index(key).index)]
    print(f"\nwrote {OUT_CLUSTERS.relative_to(ROOT)}: {len(cl)} settlements (rural schools) in {len(dist)} districts")
    print(f"wrote {OUT_DISTRICTS.relative_to(ROOT)}: {len(dist)} districts; {len(no_cl)} indexed districts have no rural school")
    print("rural schools excluded (no district / missing coords):",
          int(((sch["urban_rural"] == "Luar Bandar") & sch["district"].isna()).sum()))
    print("settlements by category (main):", cl["category_main"].value_counts().to_dict())
    print(f"take-up gap group: {int((~planned).sum())} settlements, "
          f"{cl.loc[~planned, 'unconnected_people'].sum():,.0f} rural people without home internet | planned "
          f"(tower/satellite): {int(planned.sum())} settlements, {cl.loc[planned, 'unconnected_people'].sum():,.0f} people")
    only = dist[dist["main_fix"].str.startswith("none")]
    print(f"districts with only take-up-gap settlements (no infrastructure cost, no value rank): {len(only)}")

    print("\n=== Totals: 5-yr cost to provide service ===")
    lab = {"main": "Main (Residential)", "lite": "Lite plan", "upper_bound": "Upper bound (+1 PoP per take-up settlement)",
           "cost_minus30": "All costs -30%", "cost_plus30": "All costs +30%"}
    for k in ["main", "lite", "upper_bound", "cost_minus30", "cost_plus30"]:
        extra = ""
        if k == "lite":
            ch = dist[dist["main_fix"] != dist["main_fix_lite"]]
            ncl = int((cl["category_lite"] != cl["category_main"]).sum())
            extra = f" | main fix changes in {len(ch)} districts, {ncl} settlements: {sorted(ch['district'])}"
        elif k.startswith("cost_"):
            extra = f" | settlements changing category: {int((cl[f'category_{k}'] != cl['category_main']).sum())}"
        print(f"  {lab[k]:<45} Malaysia RM{dist[f'cost_{k}_rm'].sum() / 1e9:5.2f}bn | "
              f"Sarawak RM{dist.loc[sk, f'cost_{k}_rm'].sum() / 1e9:5.2f}bn{extra}")

    show = ["value_rank_sarawak", "district", "rank_sarawak", "main_fix", "share_settlements_takeup_gap",
            "people_per_rm_m_main", "people_per_rm_m_district_main", "students_per_rm_m_main", "cost_main_rm",
            "n_tower", "n_satellite", "n_takeup_gap", "planned_people_without_internet", "small_sample_flag"]
    t = dist[(dist["state"] == FOCUS) & dist["value_rank_sarawak"].notna()].sort_values("value_rank_sarawak").head(15)[show].copy()
    t["rank_sarawak"] = t["rank_sarawak"].astype("Int64")
    t["planned_people_without_internet"] = t["planned_people_without_internet"].round().astype(int)
    t["share_settlements_takeup_gap"] = (100 * t["share_settlements_takeup_gap"]).round().astype(int).astype(str) + "%"
    t["cost_main_rm"] = (t["cost_main_rm"] / 1e6).round(1)
    t = t.rename(columns={"rank_sarawak": "need_rank", "share_settlements_takeup_gap": "takeup_share",
                          "people_per_rm_m_main": "rural_ppl_per_rm_m", "people_per_rm_m_district_main": "district_ppl_per_rm_m",
                          "students_per_rm_m_main": "students_per_rm_m", "cost_main_rm": "cost_rm_m",
                          "planned_people_without_internet": "rural_ppl_planned"})
    print("\n=== Sarawak top 15 by value (rural people without home internet in planned settlements per RM1m) ===")
    print(t.to_string(index=False, float_format=lambda x: f"{x:.1f}"))
    sk_only = dist[(dist["state"] == FOCUS) & dist["main_fix"].str.startswith("none")]["district"].tolist()
    if sk_only:
        print(f"  Sarawak districts with only take-up-gap settlements (not ranked): {sk_only}")


if __name__ == "__main__":
    main()
