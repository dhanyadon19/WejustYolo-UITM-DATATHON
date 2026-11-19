"""Estimate which schools in the 6 Hansard states are likely not on fibre, from Ookla tiles.

Inputs
  data/raw/moe/senarai_sekolah_rendah_menengah_jun2022.xlsx   MOE school list with coordinates
  data/processed/districts.geojson                            district polygons
  data/processed/ookla_my_{fixed,mobile}_{year}q{quarter}.parquet   Ookla tiles (latest quarter)
  data/raw/hansard_schools_2026-11-11.csv                     Parliament's counts, for validation
Output
  data/processed/schools_connectivity.csv   one row per school in Kelantan, Terengganu, Pahang,
                                            Kedah, Sabah, Sarawak (MOE list as at 30 Jun 2022)

Method (all distances in metres, in each state's UTM zone, school point to tile centroid)
  district          polygon of the school's own state that contains it; if none, the nearest
                    polygon of its own state within 5 km (district_method = "nearest"); else blank
  coord_flag        ok | missing | outside_polygons (assigned to nearest, <= 5 km) |
                    other_state (point lies in another state's polygon, own state <= 5 km away) |
                    suspect (no own-state polygon within 5 km)
  fixed_tiles_1km, fixed_tests_1km, fixed_tiles_2km, fixed_tests_2km
  nearest_fixed_tile_km
  mobile_tests_2km, mobile_dl_mbps_2km   (test-weighted mean download of mobile tiles within 2 km)
  likely_no_fibre   True if no fixed tile within 2 km   (likely_no_fibre_1km: within 1 km)
  confidence        from mobile tests within 2 km, fixed in advance and not tuned:
                    high >= 100, medium 20-99, low < 20. Many mobile tests but no fixed tests
                    means people do test there, so missing fixed tiles are informative; few tests
                    of any kind means the area is barely sampled and absence says little.

Estimate, not a measurement: Ookla "fixed" tiles are home broadband tests by the public. A
fixed tile nearby does not prove the school has fibre, and fixed wireless or satellite home
connections also count as "fixed", so this likely under-counts schools without fibre.

Usage: python scripts/build_schools.py [--year Y --quarter Q]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _checks import check_coords, fail, report_unmatched, require_columns, require_files, require_nonempty  # noqa: E402,F401

ROOT = Path(__file__).resolve().parent.parent
MOE = ROOT / "data" / "raw" / "moe" / "senarai_sekolah_rendah_menengah_jun2022.xlsx"
HANSARD = ROOT / "data" / "raw" / "hansard_schools_2026-11-11.csv"
PROC = ROOT / "data" / "processed"
DISTRICTS = PROC / "districts.geojson"
OUT = PROC / "schools_connectivity.csv"

STATES = ["Kelantan", "Terengganu", "Pahang", "Kedah", "Sabah", "Sarawak"]
NEAREST_MAX_M = 5000
RADII = (1000, 2000)
CONF_HIGH, CONF_MED = 100, 20  # mobile tests within 2 km


def latest_quarter() -> tuple[int, int]:
    found = []
    for p in PROC.glob("ookla_my_fixed_*q*.parquet"):
        m = re.search(r"_(\d{4})q(\d)\.parquet$", p.name)
        if m and (PROC / p.name.replace("_fixed_", "_mobile_")).exists():
            found.append((int(m.group(1)), int(m.group(2))))
    return max(found)


MOE_STATE_NAMES = {  # MOE NEGERI -> DOSM / districts.geojson state names
    "Wilayah Persekutuan Kuala Lumpur": "W.P. Kuala Lumpur",
    "Wilayah Persekutuan Labuan": "W.P. Labuan",
    "Wilayah Persekutuan Putrajaya": "W.P. Putrajaya",
}


def load_schools(states: list[str] | None = STATES) -> gpd.GeoDataFrame:
    """MOE school list (Jun 2022) as points; states=None loads every state."""
    require_files(MOE)
    df = pd.read_excel(MOE, header=1, dtype={"KODSEKOLAH": str, "POSKODSURAT": str})
    require_columns(df, ["NEGERI", "KODSEKOLAH", "NAMASEKOLAH", "LOKASI", "MURID", "KOORDINATXX", "KOORDINATYY"],
                    MOE.name)
    df["state"] = df["NEGERI"].str.strip().str.title().replace(MOE_STATE_NAMES)
    if states is not None:
        df = df[df["state"].isin(states)].copy()
    check_coords(df, "KOORDINATXX", "KOORDINATYY", f"MOE school list ({len(df)} schools)", name_col="NAMASEKOLAH")
    df["lon"] = pd.to_numeric(df["KOORDINATXX"], errors="coerce")
    df["lat"] = pd.to_numeric(df["KOORDINATYY"], errors="coerce")
    out = pd.DataFrame({
        "school_code": df["KODSEKOLAH"].str.strip(), "school_name": df["NAMASEKOLAH"].str.strip(),
        "state": df["state"], "ppd": df["PPD"].str.strip(), "level": df["PERINGKAT"],
        "type": df["JENIS/LABEL"], "urban_rural": df["LOKASI"], "aid_status": df["BANTUAN"],
        "students": df["MURID"], "teachers": df["GURU"], "lon": df["lon"], "lat": df["lat"],
    })
    geom = gpd.points_from_xy(out["lon"], out["lat"])
    return gpd.GeoDataFrame(out, geometry=geom, crs=4326).reset_index(drop=True)


def assign_districts(s: gpd.GeoDataFrame, d: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    s = s.copy()
    s["district"], s["district_method"], s["coord_flag"] = None, None, None
    s.loc[s.geometry.is_empty | s["lon"].isna(), "coord_flag"] = "missing"
    has = s["coord_flag"].isna()
    j = gpd.sjoin(s.loc[has, ["state", "geometry"]], d[["state", "district", "geometry"]],
                  how="left", predicate="within", lsuffix="s", rsuffix="d")
    own = j[j["state_s"] == j["state_d"]]
    own = own[~own.index.duplicated()]
    s.loc[own.index, ["district", "district_method", "coord_flag"]] = \
        np.column_stack([own["district"], ["within"] * len(own), ["ok"] * len(own)])
    in_other = set(j[j["state_d"].notna() & (j["state_s"] != j["state_d"])].index) - set(own.index)

    for idx in s.index[has & s["district"].isna()]:
        st, pt = s.at[idx, "state"], s.loc[[idx]]
        cand = d[d["state"] == st]
        utm = pt.estimate_utm_crs()
        dist = cand.to_crs(utm).distance(pt.to_crs(utm).geometry.iloc[0])
        k = dist.idxmin()
        if dist[k] <= NEAREST_MAX_M:
            s.at[idx, "district"] = cand.at[k, "district"]
            s.at[idx, "district_method"] = f"nearest ({dist[k] / 1000:.1f} km)"
            s.at[idx, "coord_flag"] = "other_state" if idx in in_other else "outside_polygons"
        else:
            s.at[idx, "coord_flag"] = "suspect"
    return s


def tile_metrics(s: gpd.GeoDataFrame, fixed: pd.DataFrame, mobile: pd.DataFrame) -> pd.DataFrame:
    """Per school: fixed tiles/tests within 1 and 2 km, nearest fixed tile, mobile within 2 km."""
    rows = []
    for st in sorted(s["state"].unique()):
        sub = s[(s["state"] == st) & (s["coord_flag"] != "missing")]
        if sub.empty:
            continue
        utm = sub.estimate_utm_crs()
        su = sub.to_crs(utm)
        minx, miny, maxx, maxy = sub.total_bounds
        pad = 0.5  # degrees, generous margin for nearest-tile search

        def tiles(t: pd.DataFrame) -> gpd.GeoDataFrame:
            t = t[t.tile_x.between(minx - pad, maxx + pad) & t.tile_y.between(miny - pad, maxy + pad)]
            return gpd.GeoDataFrame(t.reset_index(drop=True),
                                    geometry=gpd.points_from_xy(t.tile_x, t.tile_y), crs=4326).to_crs(utm)

        fx, mb = tiles(fixed), tiles(mobile)
        res = pd.DataFrame(index=sub.index)
        jf = gpd.sjoin(su[["geometry"]], fx[["tests", "geometry"]], how="inner",
                       predicate="dwithin", distance=max(RADII))
        jf["dist"] = [su.geometry.loc[i].distance(fx.geometry.iloc[r])
                      for i, r in zip(jf.index, jf["index_right"])]
        for r in RADII:
            w = jf[jf["dist"] <= r].groupby(level=0)
            res[f"fixed_tiles_{r // 1000}km"] = w.size()
            res[f"fixed_tests_{r // 1000}km"] = w["tests"].sum()
        near = gpd.sjoin_nearest(su[["geometry"]], fx[["geometry"]], how="left", distance_col="d")
        res["nearest_fixed_tile_km"] = near.groupby(level=0)["d"].min() / 1000

        jm = gpd.sjoin(su[["geometry"]], mb[["tests", "avg_d_kbps", "geometry"]], how="inner",
                       predicate="dwithin", distance=2000)
        g = jm.groupby(level=0)
        res["mobile_tests_2km"] = g["tests"].sum()
        res["mobile_dl_mbps_2km"] = g.apply(
            lambda x: np.average(x["avg_d_kbps"], weights=x["tests"]) / 1000, include_groups=False)
        rows.append(res)
    m = pd.concat(rows)
    for c in [c for c in m.columns if c.startswith(("fixed_tiles", "fixed_tests")) or c == "mobile_tests_2km"]:
        m[c] = m[c].fillna(0).astype(int)
    return m


def validate(out: pd.DataFrame) -> None:
    h = pd.read_csv(HANSARD).set_index("state")
    rows = []
    for st in STATES + ["Total (6 states)"]:
        sub = out if st.startswith("Total") else out[out["state"] == st]
        hv = int(h.loc[st, "schools_without_fibre"])
        row = {"state": st, "schools_moe": len(sub), "hansard_no_fibre": hv}
        for col, lab in [("likely_no_fibre", "2km"), ("likely_no_fibre_1km", "1km")]:
            est = int(sub[col].eq(True).sum())
            row[f"est_{lab}"] = est
            row[f"diff_{lab}"] = est - hv
            row[f"pct_diff_{lab}"] = round(100 * (est - hv) / hv, 1)
        rows.append(row)
    v = pd.DataFrame(rows)
    v.to_csv(PROC / "schools_validation.csv", index=False)
    print("\n=== Validation: estimated schools without fibre vs Hansard (11 Nov 2026) ===")
    print(v.to_string(index=False))
    print("wrote data/processed/schools_validation.csv")
    conf = (out[out["likely_no_fibre"] == True].groupby(["state", "confidence"]).size()
            .unstack(fill_value=0).reindex(STATES).fillna(0).astype(int))
    print("\nFlagged (2 km) by confidence:")
    print(conf.to_string())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int)
    ap.add_argument("--quarter", type=int)
    a = ap.parse_args()
    year, q = (a.year, a.quarter) if a.year and a.quarter else latest_quarter()

    require_files(DISTRICTS, HANSARD, PROC / f"ookla_my_fixed_{year}q{q}.parquet", PROC / f"ookla_my_mobile_{year}q{q}.parquet")
    d = gpd.read_file(DISTRICTS)
    s = assign_districts(load_schools(), d)
    cols = ["tile_x", "tile_y", "tests", "avg_d_kbps"]
    fixed = pd.read_parquet(PROC / f"ookla_my_fixed_{year}q{q}.parquet", columns=cols)
    mobile = pd.read_parquet(PROC / f"ookla_my_mobile_{year}q{q}.parquet", columns=cols)
    out = s.drop(columns="geometry").join(tile_metrics(s, fixed, mobile))
    count_cols = [c for c in out.columns if c.startswith(("fixed_tiles", "fixed_tests")) or c == "mobile_tests_2km"]
    out[count_cols] = out[count_cols].astype("Int64")  # blank only for schools without coordinates

    has = (out["coord_flag"] != "missing").to_numpy()
    f2 = out["fixed_tiles_2km"].to_numpy(dtype=float, na_value=np.nan)
    f1 = out["fixed_tiles_1km"].to_numpy(dtype=float, na_value=np.nan)
    out["likely_no_fibre"] = pd.array(np.where(has, f2 == 0, pd.NA), dtype="boolean")
    out["likely_no_fibre_1km"] = pd.array(np.where(has, f1 == 0, pd.NA), dtype="boolean")
    mt = out["mobile_tests_2km"].to_numpy(dtype=float, na_value=0)
    out["confidence"] = np.where(~has, None, np.where(mt >= CONF_HIGH, "high", np.where(mt >= CONF_MED, "medium", "low")))
    out.insert(0, "ookla_quarter", f"{year}Q{q}")

    out = out.sort_values(["state", "district", "school_code"], na_position="last")
    out.to_csv(OUT, index=False)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(out)} schools, Ookla {year} Q{q}")
    print("coord_flag:", out["coord_flag"].value_counts().to_dict())
    print("district_method:", out["district_method"].fillna("none").str.replace(r" \(.*", "", regex=True)
          .value_counts().to_dict())
    print("suspect coordinates:", out.loc[out["coord_flag"] == "suspect", ["state", "school_code", "school_name", "lon", "lat"]]
          .to_dict("records"))
    validate(out)


if __name__ == "__main__":
    main()
