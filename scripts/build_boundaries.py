"""Build data/processed/districts.geojson (district polygons, named as in DOSM Table 3).

Sources (raw, untouched; fetched by download_raw.py)
  - DOSM district boundaries, data/raw/boundaries/dosm_administrative_2_district.geojson
    github.com/dosm-malaysia/data-open, DOSM Open Data Licence, last updated 2022-06-22.
    Used for every state except Sarawak.
  - OpenStreetMap, data/raw/boundaries/osm_sarawak_admin6.json (Overpass snapshot, ODbL 1.0).
    Used for Sarawak: it includes the newer districts Gedong, Lingga, Pantu and Sebuyau, which the
    2022 DOSM file predates. OSM polygons are clipped to the DOSM Sarawak outline so the coast
    and state borders match the rest of the map.
  - data/raw/boundaries/osm_new_district_towns.json: town points of Siburan and Membakut, the two
    DOSM districts with no boundary in any source. Used only to say which polygon contains them.
  - data/processed/district_aliases.csv (from extract_t3.py), applied to boundary names.

Output columns
  state, district        spelled as in data/processed/dosm_hh_ict_district_2025.csv
  boundary_source        "DOSM 2022" or "OpenStreetMap"
  source_id              DOSM code_state_district, or OSM relation id
  boundary_district      name as written in the source (before aliases)
  dosm_level, dosm_district   join keys into DOSM Table 3 files (Perlis: its state-level row)
  dosm_match             True if the polygon links to a DOSM row
  contains_unmapped      DOSM districts with no polygon whose town lies inside this polygon

No district is merged, split or renamed beyond district_aliases.csv. Every mismatch, in both
directions, is printed. Invalid polygons are repaired with make_valid (geometry only).
Because Sarawak uses OSM data, districts.geojson is a derived database under ODbL 1.0.

Usage: python scripts/build_boundaries.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point
from shapely.ops import polygonize, unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _checks import check_coords, fail, report_unmatched, require_columns, require_files, require_nonempty  # noqa: E402,F401

ROOT = Path(__file__).resolve().parent.parent
RAWB = ROOT / "data" / "raw" / "boundaries"
DOSM_GEO = RAWB / "dosm_administrative_2_district.geojson"
OSM_SARAWAK = RAWB / "osm_sarawak_admin6.json"
OSM_TOWNS = RAWB / "osm_new_district_towns.json"
DOSM_T3 = ROOT / "data" / "processed" / "dosm_hh_ict_district_2025.csv"
ALIASES = ROOT / "data" / "processed" / "district_aliases.csv"
OUT = ROOT / "data" / "processed" / "districts.geojson"
OSM_STATE = "Sarawak"
METRIC_CRS = 3375  # Malaysia RSO, for areas


def osm_polygons(path: Path) -> gpd.GeoDataFrame:
    """Assemble OSM relations (Overpass 'out geom') into polygons: outer rings minus inner rings."""
    rows = []
    for e in json.loads(path.read_text(encoding="utf-8"))["elements"]:
        rings = {"outer": [], "inner": []}
        for m in e.get("members", []):
            if m["type"] == "way" and m.get("geometry"):
                role = "inner" if m.get("role") == "inner" else "outer"
                rings[role].append(LineString([(p["lon"], p["lat"]) for p in m["geometry"]]))
        outer = unary_union(list(polygonize(unary_union(rings["outer"])))) if rings["outer"] else None
        if outer is None or outer.is_empty:
            print(f"  [warn] OSM relation {e['id']} ({e['tags'].get('name')}) has no closed outer ring; skipped")
            continue
        if rings["inner"]:
            outer = outer.difference(unary_union(list(polygonize(unary_union(rings["inner"])))))
        rows.append({"boundary_district": e["tags"]["name"].strip(), "source_id": f"osm:relation/{e['id']}",
                     "geometry": outer})
    return gpd.GeoDataFrame(rows, crs=4326)


def main() -> None:
    require_files(DOSM_GEO, OSM_SARAWAK, OSM_TOWNS, DOSM_T3, ALIASES)
    aliases = pd.read_csv(ALIASES)
    amap = {(r.state, r.alias): r.canonical for r in aliases.itertuples()}

    # --- DOSM 2022 for all states except Sarawak
    dg = gpd.read_file(DOSM_GEO)
    assert dg.crs is not None and dg.crs.to_epsg() == 4326, f"unexpected CRS {dg.crs}"
    dg["geometry"] = dg.geometry.make_valid()
    dg["state"] = dg["state"].str.strip()
    sarawak_outline = unary_union(dg.loc[dg["state"] == OSM_STATE, "geometry"])
    dg = dg[dg["state"] != OSM_STATE].copy()
    dg["boundary_district"] = dg["district"].str.strip()
    dg["source_id"] = "dosm:" + dg["code_state_district"].astype(str)
    dg["boundary_source"] = "DOSM 2022"

    # --- OSM for Sarawak, clipped to the DOSM Sarawak outline
    og = osm_polygons(OSM_SARAWAK)
    require_nonempty(og, "OpenStreetMap Sarawak districts", "Re-download with download_raw.py --force.")
    og["geometry"] = og.geometry.make_valid().intersection(sarawak_outline)
    og = og[~og.geometry.is_empty].copy()
    og["state"] = OSM_STATE
    og["boundary_source"] = "OpenStreetMap"

    cols = ["state", "boundary_district", "boundary_source", "source_id", "geometry"]
    g = gpd.GeoDataFrame(pd.concat([dg[cols], og[cols]], ignore_index=True), crs=4326)
    g["geometry"] = g.geometry.make_valid()
    g["district"] = [amap.get((s, d), d) for s, d in zip(g["state"], g["boundary_district"])]
    assert not g.duplicated(["state", "district"]).any(), \
        f"duplicate state+district:\n{g[g.duplicated(['state', 'district'], keep=False)]}"

    # --- Sarawak coverage check (OSM vs DOSM outline): gaps and overlaps
    gm = g.to_crs(METRIC_CRS)
    sk = gm[gm["state"] == OSM_STATE]
    outline_km2 = gpd.GeoSeries([sarawak_outline], crs=4326).to_crs(METRIC_CRS).area.iloc[0] / 1e6
    covered_km2 = unary_union(sk.geometry).area / 1e6
    overlap_km2 = (sk.area.sum() / 1e6) - covered_km2

    # --- Link to DOSM Table 3
    t3_all = pd.read_csv(DOSM_T3)
    t3 = t3_all[t3_all["level"] != "state"]
    level_of = dict(zip(zip(t3["state"], t3["district"]), t3["level"]))
    keys = list(zip(g["state"], g["district"]))
    g["dosm_level"] = [level_of.get(k) for k in keys]
    g["dosm_district"] = [k[1] if k in level_of else None for k in keys]
    # A state with a single polygon and no DOSM district rows (Perlis) -> its DOSM state-level row
    states_with_rows = set(t3["state"])
    state_rows = set(t3_all.loc[t3_all["level"] == "state", "state"])
    single = g.groupby("state")["district"].transform("size") == 1
    for i in g.index[single & g["dosm_level"].isna()]:
        st = g.at[i, "state"]
        if st not in states_with_rows and st in state_rows:
            g.at[i, "dosm_level"], g.at[i, "dosm_district"] = "state", "All Districts"
            print(f"linked single-district state {st}/{g.at[i, 'district']} to DOSM state-level row")
    g["dosm_match"] = g["dosm_level"].notna()

    # --- DOSM districts without a polygon: which polygon contains their town point?
    dk, gk = set(level_of), set(keys)
    unmapped = sorted(dk - gk)
    towns = {e["tags"]["name"]: Point(e["lon"], e["lat"])
             for e in json.loads(OSM_TOWNS.read_text(encoding="utf-8"))["elements"]}
    g["contains_unmapped"] = ""
    located = {}
    for st, d in unmapped:
        pt = towns.get(d)
        hit = g[(g["state"] == st) & g.contains(pt)] if pt is not None else g.iloc[0:0]
        if len(hit) == 1:
            i = hit.index[0]
            g.at[i, "contains_unmapped"] = ";".join(filter(None, [g.at[i, "contains_unmapped"], d]))
            located[(st, d)] = g.at[i, "district"]

    out = g[["state", "district", "boundary_source", "source_id", "boundary_district",
             "dosm_level", "dosm_district", "dosm_match", "contains_unmapped", "geometry"]]
    out = out.sort_values(["state", "district"]).reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_file(OUT, driver="GeoJSON")

    renamed = out[out["district"] != out["boundary_district"]]
    print(f"wrote {OUT.relative_to(ROOT)}: {len(out)} polygons "
          f"({out['boundary_source'].value_counts().to_dict()})")
    print("renamed via district_aliases.csv:",
          [f"{r.boundary_district} -> {r.district}" for r in renamed.itertuples()])
    print(f"Sarawak: {len(sk)} OSM polygons; cover {covered_km2:,.0f} of {outline_km2:,.0f} km2 of the "
          f"DOSM outline ({100 * covered_km2 / outline_km2:.2f}%); gap {outline_km2 - covered_km2:,.0f} km2; "
          f"overlap between polygons {overlap_km2:,.1f} km2")
    print(f"DOSM 2025 districts + territories: {len(dk)}; matched to a polygon: {len(dk & gk)}; "
          f"polygons linked to a DOSM row: {int(out['dosm_match'].sum())} / {len(out)}")
    print(f"\nIn DOSM but NOT in boundaries ({len(unmapped)}):")
    for st, d in unmapped:
        where = f"town point lies in polygon '{located[(st, d)]}'" if (st, d) in located else "town not located"
        print(f"  {st:<14} {d:<12} {where}")
    unlinked = sorted(tuple(x) for x in out.loc[~out["dosm_match"], ["state", "district"]].itertuples(index=False))
    print(f"\nIn boundaries but NOT linked to DOSM ({len(unlinked)}):")
    for st, d in unlinked:
        print(f"  {st:<14} {d}")


if __name__ == "__main__":
    main()
