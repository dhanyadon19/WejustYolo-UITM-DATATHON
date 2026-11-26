"""Settlement attributes and settlement types -> data/processed/settlements.csv (+ settlement_types_summary.csv).

One row per rural settlement (rural MOE school) in costing_clusters.csv, same keys (state, district, school_code).
All attributes are PROXIES computed here and cached; the app never fetches them.

  demand          households / people without home internet (from costing_clusters.csv, unchanged)
  fixed_nearby    Ookla fixed tile within 2 km (existing proxy, unchanged)
  mobile_quality  nearest Ookla MOBILE tile (centroid) within 2 km: good (mean download >= 35 Mbps, JENDELA
                  Phase 1 target) / weak / no_tests
  terrain         mean slope over a 500 m circle from Terrain Tiles z12 (SRTM-based): flat / hilly / steep
  road            straight-line km to the nearest motorable OSM road (Geofabrik extract): near / far / very_far
  settlement_type A-E by the ordered rules in config/settlement_types.yaml (first match wins)
  type cost       five-year cost ONLY where costs.yaml has a cited unit cost (tower, satellite, FWA);
                  otherwise empty and type_costed = False ('not costed (no public cost source)')

A missing input (failed tile, no OSM file) leaves that column empty with a *_missing flag; it is never guessed.
A settlement whose type depends on a missing attribute gets type 'U' (not classified: missing data).

Inputs: data/processed/costing_clusters.csv, data/processed/ookla_my_mobile_{y}q{q}.parquet,
        data/raw/terrain_tiles/ and data/raw/osm/*.osm.pbf (scripts/download_settlement_inputs.py),
        config/settlement_types.yaml, config/costs.yaml
Usage: python scripts/build_settlements.py
"""
from __future__ import annotations

import io
import math
import re
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _checks import fail, require_columns, require_files, require_nonempty  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"
CFG = ROOT / "config"
OUT = PROC / "settlements.csv"
OUT_SUMMARY = PROC / "settlement_types_summary.csv"
KEY = ["state", "district", "school_code"]


def yml(name: str) -> dict:
    return yaml.safe_load((CFG / f"{name}.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- mobile quality
def mobile_quality(cl: pd.DataFrame, quarter: str, cfg: dict) -> pd.DataFrame:
    y, q = re.match(r"(\d{4})Q(\d)", quarter).groups()
    path = PROC / f"ookla_my_mobile_{y}q{q}.parquet"
    require_files(path)
    mb = pd.read_parquet(path, columns=["tile_x", "tile_y", "avg_d_kbps", "tests"])
    require_nonempty(mb, path.name)
    pts = gpd.GeoDataFrame(cl[KEY], geometry=gpd.points_from_xy(cl.lon, cl.lat), crs=4326)
    tiles = gpd.GeoDataFrame(mb, geometry=gpd.points_from_xy(mb.tile_x, mb.tile_y), crs=4326)
    search = cfg["search_km"] * 1000
    parts = []
    for st in sorted(cl.state.unique()):
        p = pts[pts.state == st]
        utm = p.estimate_utm_crs()
        minx, miny, maxx, maxy = p.total_bounds
        t = tiles.cx[minx - 0.1:maxx + 0.1, miny - 0.1:maxy + 0.1]
        j = gpd.sjoin_nearest(p.to_crs(utm), t.to_crs(utm)[["avg_d_kbps", "tests", "geometry"]], how="left",
                              max_distance=search, distance_col="d")
        j = j[~j.index.duplicated()]  # ties: keep one
        parts.append(pd.DataFrame({"mobile_tile_km": j["d"] / 1000, "mobile_tile_dl_mbps": j["avg_d_kbps"] / 1000,
                                   "mobile_tile_tests": j["tests"]}, index=j.index))
    m = pd.concat(parts).reindex(cl.index)
    good = cfg["good_min_mbps"]
    m["mobile_quality"] = np.where(m.mobile_tile_km.isna(), "no_tests",
                                   np.where(m.mobile_tile_dl_mbps >= good, "good", "weak"))
    return m


# ---------------------------------------------------------------- terrain
class Tiles:
    """Decoded terrarium tiles from data/raw/terrain_tiles (None where a tile is missing)."""

    def __init__(self, z: int, dec: dict):
        self.z, self.dec, self.cache = z, dec, {}

    def get(self, x: int, y: int):
        if (x, y) not in self.cache:
            f = RAW / "terrain_tiles" / str(self.z) / str(x) / f"{y}.png"
            if not f.exists() or f.stat().st_size == 0:
                self.cache[(x, y)] = None
            else:
                a = np.asarray(Image.open(io.BytesIO(f.read_bytes())).convert("RGB"), dtype=np.float64)
                self.cache[(x, y)] = a[..., 0] * self.dec["r"] + a[..., 1] * self.dec["g"] + \
                    a[..., 2] * self.dec["b"] + self.dec["offset"]
        return self.cache[(x, y)]

    def window(self, lon: float, lat: float, r_px: int):
        """Elevation window centred on (lon, lat), (2 r_px + 1)^2 pixels; None if any tile is missing."""
        n = 2 ** self.z * 256
        rad = math.radians(lat)
        px = (lon + 180) / 360 * n
        py = (1 - math.log(math.tan(rad) + 1 / math.cos(rad)) / math.pi) / 2 * n
        cx, cy = int(px), int(py)
        x0, y0, x1, y1 = cx - r_px, cy - r_px, cx + r_px + 1, cy + r_px + 1
        out = np.empty((y1 - y0, x1 - x0))
        for ty in range(y0 // 256, (y1 - 1) // 256 + 1):
            for tx in range(x0 // 256, (x1 - 1) // 256 + 1):
                a = self.get(tx, ty)
                if a is None:
                    return None
                gx0, gy0 = max(x0, tx * 256), max(y0, ty * 256)
                gx1, gy1 = min(x1, (tx + 1) * 256), min(y1, (ty + 1) * 256)
                out[gy0 - y0:gy1 - y0, gx0 - x0:gx1 - x0] = a[gy0 - ty * 256:gy1 - ty * 256, gx0 - tx * 256:gx1 - tx * 256]
        return out


def terrain(cl: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    dec = yml("map_tiles")["elevation"]["decoder"]
    t = Tiles(cfg["zoom"], dec)
    rows = []
    for lon, lat in zip(cl.lon, cl.lat):
        res = 40075016.686 * math.cos(math.radians(lat)) / (2 ** cfg["zoom"] * 256)  # ground metres per pixel
        r_px = int(math.ceil(cfg["radius_m"] / res)) + 1
        w = t.window(lon, lat, r_px)
        if w is None:
            rows.append((np.nan, np.nan, np.nan))
            continue
        gy, gx = np.gradient(w, res)
        slope = np.degrees(np.arctan(np.hypot(gx, gy)))
        yy, xx = np.mgrid[-r_px:r_px + 1, -r_px:r_px + 1]
        inside = np.hypot(xx, yy) * res <= cfg["radius_m"]
        rows.append((w[r_px, r_px], slope[inside].mean(), np.ptp(w[inside])))
    m = pd.DataFrame(rows, columns=["elevation_m", "slope_mean_deg", "relief_m"], index=cl.index)
    s = m.slope_mean_deg
    m["terrain"] = np.select([s.isna(), s < cfg["flat_max_deg"], s >= cfg["steep_min_deg"]],
                             [None, "flat", "steep"], "hilly")
    m["terrain"] = m["terrain"].where(s.notna())
    return m


# ---------------------------------------------------------------- roads
def roads(cl: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, str | None]:
    pbfs = sorted((RAW / "osm").glob("*.osm.pbf"))
    if not pbfs:
        print("WARNING: no OSM extract in data/raw/osm (run scripts/download_settlement_inputs.py): road = missing")
        return pd.DataFrame({"road_km": np.nan, "road": None}, index=cl.index), None
    pbf = pbfs[-1]
    import pyogrio
    t0 = time.time()
    cls = ", ".join(f"'{c}'" for c in cfg["motorable"])
    r = pyogrio.read_dataframe(pbf, layer="lines", columns=["highway"], where=f"highway IN ({cls})")
    require_nonempty(r, f"motorable roads in {pbf.name}")
    print(f"roads: {len(r):,} motorable ways from {pbf.name} in {time.time() - t0:.0f}s")
    r = r.set_crs(4326, allow_override=True)
    pts = gpd.GeoDataFrame(cl[KEY], geometry=gpd.points_from_xy(cl.lon, cl.lat), crs=4326)
    parts = []
    for st in sorted(cl.state.unique()):
        p = pts[pts.state == st]
        utm = p.estimate_utm_crs()
        minx, miny, maxx, maxy = p.total_bounds
        rr = r.cx[minx - 0.5:maxx + 0.5, miny - 0.5:maxy + 0.5].to_crs(utm)
        j = gpd.sjoin_nearest(p.to_crs(utm), rr[["geometry"]], how="left", distance_col="d")
        parts.append((j.groupby(level=0)["d"].min() / 1000).rename("road_km"))
    m = pd.concat(parts).reindex(cl.index).to_frame()
    d = m.road_km
    m["road"] = np.select([d <= cfg["near_max_km"], d > cfg["very_far_min_km"]], ["near", "very_far"], "far")
    m["road"] = m["road"].where(d.notna())
    return m, pbf.name


# ---------------------------------------------------------------- types and costs
def assign_types(s: pd.DataFrame, cfg: dict, be_hh: float, tcfg: dict, rcfg: dict) -> pd.Series:
    no_fixed = ~s.fixed_nearby
    below = s.unconnected_households < be_hh
    steep = s.slope_mean_deg >= tcfg["steep_min_deg"]
    very_far = s.road_km > rcfg["very_far_min_km"]
    isolated_known = s.slope_mean_deg.notna() & s.road_km.notna()
    # D needs only one of the two to be true; it is unknown only when neither is true and one is missing
    isolated = (steep.fillna(False) | very_far.fillna(False))
    isolated_unknown = ~isolated & ~isolated_known
    rules = {
        "A": s.fixed_nearby,
        "B": no_fixed & ~below,
        "E": no_fixed & below & (s.mobile_quality == "good"),
        "D": no_fixed & below & isolated,
        "U": no_fixed & below & isolated_unknown,
        "C": no_fixed & below,
    }
    out = pd.Series(None, index=s.index, dtype=object)
    # config order, with 'not classified' just before the catch-all C (C would otherwise absorb unknowns)
    for k in [k for k in cfg["order"] if k != "C"] + ["U", "C"]:
        out = out.where(out.notna(), pd.Series(np.where(rules[k], k, None), index=s.index))
    return out


def main() -> None:
    cfg, costs = yml("settlement_types"), yml("costs")
    cl_path = PROC / "costing_clusters.csv"
    require_files(cl_path)
    cl = pd.read_csv(cl_path)
    require_columns(cl, KEY + ["lon", "lat", "fixed_nearby", "unconnected_households", "unconnected_people",
                               "households", "category_main", "cost_main", "ookla_quarter"], cl_path.name)
    quarter = cl.ookla_quarter.iloc[0]

    t0 = time.time()
    mob = mobile_quality(cl, quarter, cfg["mobile_quality"])
    print(f"mobile quality: {mob.mobile_quality.value_counts().to_dict()} ({time.time() - t0:.0f}s)")
    t0 = time.time()
    ter = terrain(cl, cfg["terrain"])
    print(f"terrain: {ter.terrain.value_counts(dropna=False).to_dict()} ({time.time() - t0:.0f}s)")
    print("  slope (deg) quantiles 10/25/50/75/90/95:",
          ter.slope_mean_deg.quantile([.1, .25, .5, .75, .9, .95]).round(1).tolist())
    rd, osm_file = roads(cl, cfg["road"])
    print(f"road: {rd.road.value_counts(dropna=False).to_dict()}")
    print("  road km quantiles 50/75/90/95/99:", rd.road_km.quantile([.5, .75, .9, .95, .99]).round(2).tolist())

    s = pd.concat([cl[KEY + ["school_name", "lon", "lat", "households", "unconnected_households", "unconnected_people",
                             "fixed_nearby", "nearest_fixed_tile_km", "category_main", "cost_main"]], mob, ter, rd], axis=1)
    s["terrain_missing"] = s.terrain.isna()
    s["road_missing"] = s.road.isna()

    # break-even from costs.yaml, exactly as build_costing.py (main case: Residential plan)
    t, sat = costs["tower"], costs["satellite"]
    tower5 = t["capex_per_site_rm"]["central"] + 5 * t["opex_per_site_per_year_rm"]
    term5 = sat["kit_rm"] + 60 * sat["monthly_rm"]["residential"]
    school5 = sat["kit_rm"] + 60 * sat["monthly_rm"]["business_from"]
    fwa5 = costs["fwa"]["cpe_rm"] + 60 * costs["fwa"]["monthly_rm"]
    s["settlement_type"] = assign_types(s, cfg, tower5 / term5, cfg["terrain"], cfg["road"])
    if s.settlement_type.isna().any():
        fail(f"{int(s.settlement_type.isna().sum())} settlements got no type: check the rules")
    labels = {k: v["label"] for k, v in cfg["types"].items()}
    labels["U"] = "Not classified (missing data)"
    s["type_label"] = s.settlement_type.map(labels)
    s["candidate_technologies"] = s.settlement_type.map({k: v["candidates"] for k, v in cfg["types"].items()})
    s.loc[s.settlement_type == "U", "candidate_technologies"] = "Not classified: terrain or road data missing"

    # costed option per type (only cited unit costs)
    costed = s.settlement_type.map({k: v["costed"] for k, v in cfg["types"].items()}).fillna("none")
    s["type_cost_basis"] = costed.map({"tower": "4G/5G macro tower, five-year (costs.yaml)",
                                       "satellite": "Satellite per household + school terminal, five-year (costs.yaml)",
                                       "fwa": "FWA retail plan per household, five-year (costs.yaml)",
                                       "none": "not costed (no public cost source)"})
    s["type_cost_5yr_rm"] = np.select(
        [costed == "tower", costed == "satellite", costed == "fwa"],
        [tower5, s.unconnected_households * term5 + school5, s.unconnected_households * fwa5], np.nan)
    s["type_costed"] = costed != "none"
    # reconciliation with the existing cost screen (main case)
    for k, cat in (("B", "tower"), ("D", "satellite")):
        sub = s[s.settlement_type == k]
        if not (sub.category_main == cat).all() or not np.allclose(sub.type_cost_5yr_rm, sub.cost_main):
            fail(f"type {k} costs do not reconcile with costing_clusters cost_main ({cat})")

    s["ookla_quarter"] = quarter
    s["osm_extract"] = osm_file
    cols = KEY + ["school_name", "lon", "lat", "households", "unconnected_households", "unconnected_people",
                  "fixed_nearby", "nearest_fixed_tile_km", "mobile_tile_km", "mobile_tile_dl_mbps", "mobile_tile_tests",
                  "mobile_quality", "elevation_m", "slope_mean_deg", "relief_m", "terrain", "terrain_missing",
                  "road_km", "road", "road_missing", "settlement_type", "type_label", "candidate_technologies",
                  "type_cost_basis", "type_costed", "type_cost_5yr_rm", "category_main", "cost_main",
                  "ookla_quarter", "osm_extract"]
    s[cols].sort_values(KEY).to_csv(OUT, index=False)

    # summary by scope x type
    rows = []
    for scope, sub in (("All Malaysia", s), ("Sarawak", s[s.state == "Sarawak"])):
        for k in cfg["order"] + ["U"]:
            g = sub[sub.settlement_type == k]
            if k == "U" and g.empty:
                continue
            rows.append({"scope": scope, "settlement_type": k, "type_label": labels[k],
                         "settlements": len(g), "people_without_home_internet": g.unconnected_people.sum(),
                         "candidate_technologies": cfg["types"].get(k, {}).get("candidates", ""),
                         "type_cost_basis": g.type_cost_basis.iloc[0] if len(g) else "",
                         "type_cost_5yr_rm": g.type_cost_5yr_rm.sum() if (len(g) and g.type_costed.all()) else np.nan,
                         "screen_cost_main_rm": g.cost_main.sum()})
    pd.DataFrame(rows).to_csv(OUT_SUMMARY, index=False)
    print(f"wrote {OUT.name} ({len(s)} rows) and {OUT_SUMMARY.name}")
    print(pd.DataFrame(rows)[["scope", "settlement_type", "settlements", "people_without_home_internet",
                              "type_cost_5yr_rm", "screen_cost_main_rm"]].round(0).to_string(index=False))


if __name__ == "__main__":
    main()
