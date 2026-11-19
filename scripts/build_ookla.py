"""Aggregate Ookla performance tiles to districts.

Input : data/processed/ookla_my_{fixed,mobile}_{year}q{quarter}.parquet  (from download_ookla.py)
        data/processed/districts.geojson                                 (from build_boundaries.py)
Output: data/processed/ookla_district_{year}q{quarter}.csv, one row per district x type
        (all 164 polygons x 2 types, including districts with no tiles).

Method
  - Each tile (zoom-16 web-mercator tile, about 600 m across) is assigned to the district
    polygon containing its centroid (tile_x, tile_y). Tiles outside every polygon (neighbouring
    countries, sea, or the small OSM/DOSM edge gap in Sarawak) are dropped and counted. The
    simplified DOSM 2022 polygons overlap by slivers along some shared edges; a centroid inside
    two polygons goes to the one it lies deepest inside (a handful of tiles per quarter).
  - dl_mbps, ul_mbps   test-weighted mean of tile avg_d_kbps / avg_u_kbps, divided by 1000
  - latency_median_ms  test-weighted median of tile avg_lat_ms (each test counted once,
                       using its tile's average; tile averages are all Ookla publishes)
  - n_tiles, tests     count of tiles, sum of tests
  - devices            sum of tile device counts; one device testing in several tiles is
                       counted more than once, so this is an upper bound on unique devices
  - low_sample         tests < 50 (includes districts with no tiles)

Usage: python scripts/build_ookla.py [--year Y --quarter Q]   (default: latest processed quarter)
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
PROC = ROOT / "data" / "processed"
DISTRICTS = PROC / "districts.geojson"
DOSM_OUTLINE = ROOT / "data" / "raw" / "boundaries" / "dosm_administrative_2_district.geojson"
TYPES = ("fixed", "mobile")
LOW_SAMPLE_TESTS = 50


def latest_quarter() -> tuple[int, int]:
    found = []
    for p in PROC.glob("ookla_my_fixed_*q*.parquet"):
        m = re.search(r"_(\d{4})q(\d)\.parquet$", p.name)
        if m and (PROC / p.name.replace("_fixed_", "_mobile_")).exists():
            found.append((int(m.group(1)), int(m.group(2))))
    if not found:
        raise SystemExit("No processed Ookla files; run scripts/download_ookla.py first.")
    return max(found)


def weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    ok = ~np.isnan(values) & (weights > 0)
    values, weights = values[ok], weights[ok]
    if len(values) == 0:
        return float("nan")
    order = np.argsort(values)
    values, weights = values[order], weights[order]
    cum = np.cumsum(weights)
    return float(values[np.searchsorted(cum, cum[-1] / 2.0)])


def aggregate(tiles: pd.DataFrame) -> pd.Series:
    w = tiles["tests"].to_numpy(dtype=float)
    return pd.Series({
        "n_tiles": len(tiles),
        "tests": int(w.sum()),
        "devices": int(tiles["devices"].sum()),
        "dl_mbps": float(np.average(tiles["avg_d_kbps"], weights=w)) / 1000,
        "ul_mbps": float(np.average(tiles["avg_u_kbps"], weights=w)) / 1000,
        "latency_median_ms": weighted_median(tiles["avg_lat_ms"].to_numpy(dtype=float), w),
    })


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int)
    ap.add_argument("--quarter", type=int)
    a = ap.parse_args()
    year, q = (a.year, a.quarter) if a.year and a.quarter else latest_quarter()

    require_files(DISTRICTS, DOSM_OUTLINE, *[PROC / f"ookla_my_{k}_{year}q{q}.parquet" for k in TYPES])
    d = gpd.read_file(DISTRICTS)
    keys = ["state", "district", "dosm_district", "boundary_source", "contains_unmapped"]
    d["contains_unmapped"] = d["contains_unmapped"].fillna("")
    # DOSM's own national land outline: unassigned tiles inside it fell in edge gaps between sources
    national = gpd.read_file(DOSM_OUTLINE).make_valid().union_all()

    parts = []
    for kind in TYPES:
        src = PROC / f"ookla_my_{kind}_{year}q{q}.parquet"
        t = pd.read_parquet(src, columns=["quadkey", "tile_x", "tile_y", "avg_d_kbps", "avg_u_kbps",
                                          "avg_lat_ms", "tests", "devices"])
        require_nonempty(t, src.name, "Rerun scripts/download_ookla.py.")
        pts = gpd.GeoDataFrame(t, geometry=gpd.points_from_xy(t["tile_x"], t["tile_y"]), crs=4326)
        j = gpd.sjoin(pts, d[keys + ["geometry"]], how="left", predicate="within")
        # The simplified DOSM 2022 polygons overlap by slivers along shared edges. A centroid in
        # two polygons goes to the one it lies deepest inside (largest distance to the boundary).
        dup = j.index.duplicated(keep=False)
        n_dup = int(j.index[dup].nunique())
        if n_dup:
            bnd = d.set_index(["state", "district"]).geometry.boundary.to_crs(3375)
            pm = j.loc[dup].geometry.to_crs(3375)
            depth = [pm.iloc[k].distance(bnd.loc[(s, di)])
                     for k, (s, di) in enumerate(zip(j.loc[dup, "state"], j.loc[dup, "district"]))]
            jd = j.loc[dup].assign(_depth=depth)
            keep = jd.reset_index().sort_values("_depth").drop_duplicates("index", keep="last")
            j = pd.concat([j.loc[~dup], j.loc[dup].reset_index()
                           .merge(keep[["index", "state", "district"]], on=["index", "state", "district"])
                           .set_index("index")]).sort_index()
        assert not j.index.duplicated().any()
        un = j[j["district"].isna()]
        in_outline = un.geometry.within(national) if len(un) else pd.Series(dtype=bool)
        print(f"{kind}: {len(t):,} bbox tiles ({int(t.tests.sum()):,} tests) -> "
              f"{int(j['district'].notna().sum()):,} assigned; {len(un):,} unassigned "
              f"({int(un.tests.sum()):,} tests; {int(in_outline.sum())} tiles / "
              f"{int(un.loc[in_outline.values, 'tests'].sum()) if len(un) else 0} tests inside DOSM's Malaysia "
              f"outline, i.e. in edge gaps); "
              f"{n_dup} on overlapping polygon edges resolved by depth")

        agg = (j[j["district"].notna()].groupby(["state", "district"]).apply(aggregate, include_groups=False)
               .reset_index())
        out = d[keys].merge(agg, on=["state", "district"], how="left")
        out[["n_tiles", "tests", "devices"]] = out[["n_tiles", "tests", "devices"]].fillna(0).astype(int)
        out.insert(0, "type", kind)
        parts.append(out)

    res = pd.concat(parts, ignore_index=True)
    res["low_sample"] = res["tests"] < LOW_SAMPLE_TESTS
    res.insert(0, "quarter", q)
    res.insert(0, "year", year)
    res = res.sort_values(["type", "state", "district"]).reset_index(drop=True)
    dest = PROC / f"ookla_district_{year}q{q}.csv"
    res.to_csv(dest, index=False)
    print(f"\nwrote {dest.relative_to(ROOT)}: {len(res)} rows "
          f"({res.groupby('type')['low_sample'].sum().to_dict()} low_sample; "
          f"{res.groupby('type')['n_tiles'].apply(lambda s: int((s == 0).sum())).to_dict()} with no tiles)")

    show = ["district", "dl_mbps", "ul_mbps", "latency_median_ms", "n_tiles", "tests", "devices", "low_sample"]
    for kind in TYPES:
        sk = res[(res["type"] == kind) & (res["state"] == "Sarawak")]
        print(f"\n=== 10 slowest Sarawak districts, {kind}, {year} Q{q} (test-weighted mean download) ===")
        print(sk.nsmallest(10, "dl_mbps")[show].to_string(index=False, float_format=lambda x: f"{x:.1f}"))
        no = sk[sk["n_tiles"] == 0]["district"].tolist()
        if no:
            print(f"  (no {kind} tiles at all: {no})")


if __name__ == "__main__":
    main()
