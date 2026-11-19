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

Fix per cluster (in order)
  fibre_pop  any Ookla fixed tile within 2 km of the school (PROXY for "fibre route nearby")
  tower      households >= break-even (tower 5-yr cost / satellite 5-yr cost per terminal)
  satellite  otherwise: one terminal per unconnected household + one Business terminal for the school

5-year cost to provide service (users' mobile plans excluded)
  tower      capex + 5 x opex
  satellite  (kit + 60 x monthly) per terminal; school terminal uses the Business plan
  fibre_pop  capex only; its running cost is UNSOURCED (flagged)
Main case: Residential plan, central costs. Sensitivity: all costs -30% and +30%, Lite plan.

Value: people_without_home_internet per RM1m and students (in rural schools of the district)
per RM1m, reported separately; value rank on people per RM1m.

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
FIXES = ["fibre_pop", "tower", "satellite"]


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


def choose(clusters: pd.DataFrame, u: dict) -> pd.Series:
    return pd.Series(np.where(clusters["fibre_nearby"], "fibre_pop",
                              np.where(clusters["households"] >= u["breakeven_households"], "tower", "satellite")),
                     index=clusters.index)


def cost(clusters: pd.DataFrame, fix: pd.Series, u: dict) -> pd.Series:
    sat = clusters["unconnected_households"] * u["satellite_terminal"] + u["satellite_school"]
    return pd.Series(np.select([fix == "fibre_pop", fix == "tower"], [u["fibre_pop"], u["tower"]], sat),
                     index=clusters.index)


def dominant(clusters: pd.DataFrame, fix: pd.Series) -> pd.Series:
    """District's recommended fix = the fix serving the most unconnected households."""
    t = clusters.assign(fix=fix).groupby(["state", "district", "fix"])["unconnected_households"].sum()
    return t.groupby(level=[0, 1]).idxmax().map(lambda k: k[2])


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
    rural["fibre_nearby"] = rural["fixed_tiles_2km"].fillna(0) > 0

    n_rural = rural.groupby(["state", "district"]).size().rename("rural_schools")
    cl = rural.merge(n_rural.reset_index(), on=["state", "district"]).merge(hh, on=["state", "district"], how="left")
    cl = cl.merge(gi[["state", "district", "access_gap", "small_sample_flag"]], on=["state", "district"], how="left")
    miss = cl[cl["rural_households"].isna() | cl["access_gap"].isna()]
    assert miss.empty, f"clusters without households or access data:\n{miss[['state', 'district']].drop_duplicates()}"
    cl["households"] = cl["rural_households"] / cl["rural_schools"]
    cl["unconnected_households"] = cl["households"] * cl["access_gap"] / 100

    # --- scenarios
    scen = {"main": unit_costs(c, "residential"), "cost_minus30": unit_costs(c, "residential", 0.7),
            "cost_plus30": unit_costs(c, "residential", 1.3), "lite": unit_costs(c, "residential_lite")}
    for k, u in scen.items():
        cl[f"fix_{k}"] = choose(cl, u)
        cl[f"cost_{k}"] = cost(cl, cl[f"fix_{k}"], u)

    cl_out = cl[["state", "district", "school_code", "school_name", "students", "lon", "lat", "rural_schools",
                 "rural_households", "household_size", "hh_source", "households", "access_gap",
                 "unconnected_households", "small_sample_flag", "fixed_tiles_2km", "nearest_fixed_tile_km",
                 "fibre_nearby"] + [f"{p}_{k}" for k in scen for p in ("fix", "cost")]].copy()
    cl_out.insert(0, "ookla_quarter", f"{year}Q{q}")
    cl_out.sort_values(["state", "district", "school_code"]).to_csv(OUT_CLUSTERS, index=False)

    # --- districts
    g = cl.groupby(["state", "district"])
    dist = pd.DataFrame({
        "rural_schools": g.size(),
        "students_rural_schools": g["students"].sum(),
        "rural_households": g["rural_households"].first(),
        "unconnected_rural_households": g["unconnected_households"].sum(),
        "household_size": g["household_size"].first(),
        "hh_source": g["hh_source"].first(),
    })
    for f in FIXES:
        dist[f"n_{f}"] = g["fix_main"].apply(lambda s, f=f: int((s == f).sum()))
    for k in scen:
        dist[f"cost_{k}_rm"] = g[f"cost_{k}"].sum()
        dist[f"fix_{k}"] = dominant(cl, cl[f"fix_{k}"])
    dist = dist.reset_index().merge(
        gi[["state", "district", "cgi", "rank_national", "rank_sarawak", "small_sample_flag",
            "people_without_home_internet", "population_k", "access_gap"]], on=["state", "district"], how="left")
    # cross-check only: people in the costed rural clusters (the plan does not reach urban areas)
    dist["rural_people_without_internet_est"] = (dist["unconnected_rural_households"] * dist["household_size"]).round()
    for k in scen:
        dist[f"people_per_rm_m_{k}"] = dist["people_without_home_internet"] / (dist[f"cost_{k}_rm"] / 1e6)
        dist[f"students_per_rm_m_{k}"] = dist["students_rural_schools"] / (dist[f"cost_{k}_rm"] / 1e6)
    dist["value_rank_national"] = dist["people_per_rm_m_main"].rank(ascending=False, method="min").astype("Int64")
    sk = dist["state"] == FOCUS
    dist.loc[sk, "value_rank_sarawak"] = dist.loc[sk, "people_per_rm_m_main"].rank(ascending=False, method="min")
    dist["value_rank_sarawak"] = dist["value_rank_sarawak"].astype("Int64")
    for k in ["cost_minus30", "cost_plus30", "lite"]:
        dist[f"value_rank_national_{k}"] = dist[f"people_per_rm_m_{k}"].rank(ascending=False, method="min").astype("Int64")
    dist["fibre_pop_opex_unsourced"] = dist["n_fibre_pop"] > 0
    dist.insert(0, "ookla_quarter", f"{year}Q{q}")
    dist = dist.sort_values("value_rank_national")
    dist.to_csv(OUT_DISTRICTS, index=False)

    # --- report
    u = scen["main"]
    print(f"unit 5-yr costs (main, Residential): tower RM{u['tower']:,.0f}, satellite terminal RM{u['satellite_terminal']:,.0f}, "
          f"school terminal RM{u['satellite_school']:,.0f}, fibre PoP RM{u['fibre_pop']:,.0f} (capex only); "
          f"break-even {u['breakeven_households']:.1f} households (Lite {scen['lite']['breakeven_households']:.1f})")
    print("new-district parents (largest overlap with 2022 DOSM polygon):", {k[1]: v[1] for k, v in parent.items()})
    no_cl = gi[~gi.set_index(["state", "district"]).index.isin(dist.set_index(["state", "district"]).index)]
    print(f"\nwrote {OUT_CLUSTERS.relative_to(ROOT)}: {len(cl)} clusters (rural schools) in {len(dist)} districts")
    print(f"wrote {OUT_DISTRICTS.relative_to(ROOT)}: {len(dist)} districts; "
          f"{len(no_cl)} indexed districts have no rural school, so no cost: {sorted(no_cl['district'])}")
    print("clusters by fix (main):", cl["fix_main"].value_counts().to_dict())
    print("rural schools excluded (no district / missing coords):",
          int(((sch["urban_rural"] == "Luar Bandar") & sch["district"].isna()).sum()))

    print("\n=== Sensitivity: districts whose recommended (dominant) fix changes vs main ===")
    for k in ["cost_minus30", "cost_plus30", "lite"]:
        ch = dist[dist[f"fix_{k}"] != dist["fix_main"]]
        ncl = int((cl[f"fix_{k}"] != cl["fix_main"]).sum())
        print(f"  {k:<13} districts changed: {len(ch):>3} | clusters changed: {ncl:>4} | "
              f"total cost RM{dist[f'cost_{k}_rm'].sum() / 1e9:,.2f}bn (main RM{dist['cost_main_rm'].sum() / 1e9:,.2f}bn)")
        if len(ch):
            print("    ", ch[["state", "district", "fix_main", f"fix_{k}"]].to_dict("records")[:12])

    show = ["value_rank_sarawak", "district", "rank_sarawak", "people_per_rm_m_main", "students_per_rm_m_main",
            "cost_main_rm", "fix_main", "n_fibre_pop", "n_tower", "n_satellite", "people_without_home_internet",
            "students_rural_schools", "small_sample_flag"]
    t = dist[dist["state"] == FOCUS].sort_values("value_rank_sarawak").head(15)[show].copy()
    t["rank_sarawak"] = t["rank_sarawak"].astype("Int64")
    t[["people_without_home_internet", "students_rural_schools"]] = \
        t[["people_without_home_internet", "students_rural_schools"]].astype("Int64")
    t["cost_main_rm"] = (t["cost_main_rm"] / 1e6).round(1)
    t = t.rename(columns={"rank_sarawak": "need_rank_sarawak", "cost_main_rm": "cost_rm_m"})
    print("\n=== Sarawak top 15 by value (people without home internet per RM1m), next to need rank ===")
    print(t.to_string(index=False, float_format=lambda x: f"{x:.1f}"))


if __name__ == "__main__":
    main()
