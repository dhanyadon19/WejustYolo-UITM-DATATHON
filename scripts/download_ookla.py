"""Download Ookla Open Data performance tiles (fixed + mobile) and clip them to Malaysia.

Source: Ookla for Good Open Data, public AWS bucket s3://ookla-open-data (no credentials),
        read over HTTPS. Licence: CC BY-NC-SA 4.0 (attribution: "Speedtest by Ookla Global
        Fixed and Mobile Network Performance Maps").

Steps
  1. List the bucket and pick the most recent quarter available for BOTH fixed and mobile
     (or use --year/--quarter).
  2. Download the global tile files to data/raw/ookla/ (gitignored, ~550 MB); existing files
     are kept unless --force.
  3. Keep tiles whose centroid (tile_x, tile_y) falls inside Malaysia's bounding box, taken from
     the DOSM district boundaries (+0.1 degree buffer). The box also covers parts of Brunei,
     Singapore, Thailand and Indonesia; build_ookla.py drops those when assigning districts.
  4. Write data/processed/ookla_my_{fixed,mobile}_{year}q{quarter}.parquet.

Usage: python scripts/download_ookla.py [--year Y --quarter Q] [--force]
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import geopandas as gpd
import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "ookla"
OUT = ROOT / "data" / "processed"
BOUNDS_SRC = ROOT / "data" / "raw" / "boundaries" / "dosm_administrative_2_district.geojson"
BUCKET = "https://ookla-open-data.s3.amazonaws.com"
TYPES = ("fixed", "mobile")
BUFFER_DEG = 0.1


def list_keys(prefix: str) -> list[str]:
    keys, token = [], None
    while True:
        url = f"{BUCKET}/?list-type=2&prefix={prefix}"
        if token:
            url += "&continuation-token=" + urllib.parse.quote(token)
        xml = urllib.request.urlopen(url, timeout=60).read().decode()
        keys += re.findall(r"<Key>([^<]+\.parquet)</Key>", xml)
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", xml)
        if not m:
            return keys
        token = m.group(1)


def available_quarters(kind: str) -> dict[tuple[int, int], str]:
    out = {}
    for k in list_keys(f"parquet/performance/type={kind}/"):
        m = re.search(r"year=(\d{4})/quarter=(\d)/", k)
        if m:
            out[(int(m.group(1)), int(m.group(2)))] = k
    return out


def download(key: str, dest: Path, force: bool) -> None:
    if dest.exists() and not force:
        print(f"[skip] {dest.name} exists ({dest.stat().st_size:,} B)")
        return
    part = dest.with_suffix(".part")
    print(f"[get]  {BUCKET}/{key}", flush=True)
    with urllib.request.urlopen(f"{BUCKET}/{key}", timeout=600) as r, part.open("wb") as f:
        shutil.copyfileobj(r, f, length=8 << 20)
    pq.ParquetFile(part)  # raises if not a valid parquet file
    part.replace(dest)
    print(f"       saved {dest.name} ({dest.stat().st_size:,} B)", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int)
    ap.add_argument("--quarter", type=int)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    avail = {k: available_quarters(k) for k in TYPES}
    common = sorted(set(avail["fixed"]) & set(avail["mobile"]))
    if a.year and a.quarter:
        yq = (a.year, a.quarter)
        if yq not in common:
            sys.exit(f"{yq} not available for both types; latest common: {common[-1]}")
    else:
        yq = common[-1]
    year, q = yq
    print(f"Quarter: {year} Q{q} (latest available for both fixed and mobile: {common[-1]})")

    minx, miny, maxx, maxy = gpd.read_file(BOUNDS_SRC).total_bounds
    bbox = (minx - BUFFER_DEG, miny - BUFFER_DEG, maxx + BUFFER_DEG, maxy + BUFFER_DEG)
    print("Malaysia bbox (lon/lat, from DOSM boundaries + buffer):", tuple(round(v, 3) for v in bbox))

    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    for kind in TYPES:
        key = avail[kind][yq]
        src = RAW / Path(key).name
        download(key, src, a.force)
        t = pq.read_table(src)
        n_global = t.num_rows
        assert {"tile_x", "tile_y"} <= set(t.column_names), f"no tile_x/tile_y in {src.name}: {t.column_names}"
        mask = pc.and_(
            pc.and_(pc.greater_equal(t["tile_x"], bbox[0]), pc.less_equal(t["tile_x"], bbox[2])),
            pc.and_(pc.greater_equal(t["tile_y"], bbox[1]), pc.less_equal(t["tile_y"], bbox[3])),
        )
        my = t.filter(mask)
        dest = OUT / f"ookla_my_{kind}_{year}q{q}.parquet"
        pq.write_table(my, dest)
        print(f"wrote {dest.relative_to(ROOT)}: {my.num_rows:,} of {n_global:,} global tiles; "
              f"columns={my.column_names}", flush=True)


if __name__ == "__main__":
    main()
