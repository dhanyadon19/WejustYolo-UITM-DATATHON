"""Download the two raw inputs for the settlement attributes (build_settlements.py).

1. OpenStreetMap extract for Malaysia, Singapore and Brunei (Geofabrik, ODbL 1.0):
   https://download.geofabrik.de/asia/malaysia-singapore-brunei-latest.osm.pbf
   The 'latest' URL redirects to a dated file (e.g. ...-261124.osm.pbf); it is saved under that dated name in
   data/raw/osm/ (gitignored, ~250 MB) so the build always says which snapshot it used.
2. Terrain Tiles (AWS Open Data, terrarium PNG; config/map_tiles.yaml 'elevation'): every zoom-12 tile
   (~38 m pixels at Malaysia's latitude) within about 1.1 km of a rural settlement, saved to
   data/raw/terrain_tiles/12/{x}/{y}.png (gitignored). These are the tiles the Sarawak 3D map streams;
   Malaysian tiles come from SRTM (~30 m).

Existing files are kept unless --force. A failed tile is reported and the build marks the settlements it
affects as missing terrain (never guessed).

Usage: python scripts/download_settlement_inputs.py [--force] [--skip-osm] [--skip-terrain]
"""
from __future__ import annotations

import argparse
import math
import shutil
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _checks import fail, require_files  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OSM_DIR = ROOT / "data" / "raw" / "osm"
TILE_DIR = ROOT / "data" / "raw" / "terrain_tiles"
CLUSTERS = ROOT / "data" / "processed" / "costing_clusters.csv"
OSM_URL = "https://download.geofabrik.de/asia/malaysia-singapore-brunei-latest.osm.pbf"
ZOOM = 12
PAD_DEG = 0.01  # ~1.1 km around each settlement, so the slope window never runs off the tiles fetched
UA = {"User-Agent": "beyond-coverage-datathon/1.0 (research; non-commercial)"}


def tile_xy(lon: float, lat: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    r = math.radians(lat)
    return int((lon + 180) / 360 * n), int((1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n)


def needed_tiles(df: pd.DataFrame) -> set[tuple[int, int]]:
    out = set()
    for lon, lat in zip(df["lon"], df["lat"]):
        for dx in (-PAD_DEG, 0, PAD_DEG):
            for dy in (-PAD_DEG, 0, PAD_DEG):
                out.add(tile_xy(lon + dx, lat + dy, ZOOM))
    return out


def download_osm(force: bool) -> None:
    OSM_DIR.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(OSM_URL, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        name = Path(r.geturl()).name  # the dated file the redirect points to
        dest = OSM_DIR / name
        if dest.exists() and not force:
            print(f"OSM: {dest.name} already present, kept")
            return
        size = int(r.headers.get("Content-Length", 0))
        tmp = dest.with_suffix(".part")
        with open(tmp, "wb") as f:
            shutil.copyfileobj(r, f, length=1 << 20)
    if size and tmp.stat().st_size != size:
        tmp.unlink()
        fail(f"OSM download incomplete ({tmp.stat().st_size} of {size} bytes)")
    tmp.replace(dest)
    print(f"OSM: saved {dest.name} ({dest.stat().st_size / 1e6:.0f} MB)")


def download_terrain(force: bool) -> None:
    require_files(CLUSTERS)
    url = yaml.safe_load((ROOT / "config" / "map_tiles.yaml").read_text(encoding="utf-8"))["elevation"]["url"]
    tiles = sorted(needed_tiles(pd.read_csv(CLUSTERS, usecols=["lon", "lat"])))

    def get(xy: tuple[int, int]) -> str | None:
        x, y = xy
        dest = TILE_DIR / str(ZOOM) / str(x) / f"{y}.png"
        if dest.exists() and dest.stat().st_size > 0 and not force:
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            req = urllib.request.Request(url.format(z=ZOOM, x=x, y=y), headers=UA)
            dest.write_bytes(urllib.request.urlopen(req, timeout=60).read())
            return None
        except Exception as e:  # reported, never filled in
            return f"{ZOOM}/{x}/{y}: {e}"

    with ThreadPoolExecutor(8) as ex:
        errors = [e for e in ex.map(get, tiles) if e]
    print(f"Terrain: {len(tiles)} zoom-{ZOOM} tiles needed, {len(tiles) - len(errors)} present")
    if errors:
        print(f"WARNING: {len(errors)} tiles failed (settlements on them get terrain = missing):", errors[:5])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--skip-osm", action="store_true")
    ap.add_argument("--skip-terrain", action="store_true")
    a = ap.parse_args()
    if not a.skip_terrain:
        download_terrain(a.force)
    if not a.skip_osm:
        download_osm(a.force)
