"""Download every raw dataset into data/raw/.

Sources (all official links, found on each dataset's catalogue / release page):
  - OpenDOSM / data.gov.my Parquet files (storage.dosm.gov.my, storage.data.gov.my)
  - DOSM "ICT Use and Access by Individuals and Households Survey Report"
    2024 and 2025, Tables 1, 2, 3, 6, 7 (release-document-log links)
  - DOSM district boundaries (github.com/dosm-malaysia/data-open)
  - OpenStreetMap Sarawak district boundaries + two town points (Overpass API snapshot)

Existing files are kept as-is (raw data stays untouched); pass --force to re-download.
Each file is validated (Parquet magic bytes / real .xlsx zip with a workbook) before
it is moved into place. Any failure stops the script with a non-zero exit code.

Usage:  python scripts/download_raw.py [--force]
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
UA = {"User-Agent": "Mozilla/5.0 (datathon data pipeline)"}

PARQUET = {
    "hh_access_internet.parquet": "https://storage.dosm.gov.my/icths/hh_access_internet.parquet",
    "icths_internet_strata.parquet": "https://storage.dosm.gov.my/icths/icths_internet_strata.parquet",
    "hh_access_amenities.parquet": "https://storage.dosm.gov.my/hies/hh_access_amenities.parquet",
    "hh_income_district.parquet": "https://storage.dosm.gov.my/hies/hh_income_district.parquet",
    "population_district.parquet": "https://storage.dosm.gov.my/population/population_district.parquet",
    # MOE datasets: listed in the OpenDOSM catalogue, hosted on data.gov.my storage
    "schools_district.parquet": "https://storage.data.gov.my/education/schools_district.parquet",
    "teachers_district.parquet": "https://storage.data.gov.my/education/teachers_district.parquet",
    "enrolment_school_district.parquet": "https://storage.data.gov.my/education/enrolment_school_district.parquet",
}

# DOSM release pages:
#   https://www.dosm.gov.my/portal-main/release-content/ict-use-and-access-by-individuals-and-households-survey-report-2024
#   https://www.dosm.gov.my/portal-main/release-content/ict-use-and-access-by-individuals-and-households-survey-report-2025
DOSM_DOC = "https://www.dosm.gov.my/portal-main/release-document-log?release_document_id={}"
ICTHS_DOC_IDS = {
    2024: {1: 13942, 2: 13943, 3: 13949, 6: 13947, 7: 13948},
    2025: {1: 19016, 2: 19017, 3: 19018, 6: 19021, 7: 19022},
}
XLSX = {
    f"icths_{year}_table{t}.xlsx": DOSM_DOC.format(doc_id)
    for year, tables in ICTHS_DOC_IDS.items()
    for t, doc_id in tables.items()
}


# District boundaries (see data/README.md for the choice between candidates)
DOSM_GEO = "https://raw.githubusercontent.com/dosm-malaysia/data-open/main/datasets/geodata/"
BOUNDARIES = {
    "boundaries/dosm_administrative_2_district.geojson": DOSM_GEO + "administrative_2_district.geojson",
    "boundaries/dosm_state_district.csv": DOSM_GEO + "state_district.csv",
}

# OpenStreetMap snapshot (ODbL) via Overpass: Sarawak district relations (admin_level 6) with
# geometry, plus the town points of the two new districts that have no boundary anywhere.
# Overpass returns the live OSM state, so the saved file is the reproducible snapshot.
OVERPASS = "https://overpass-api.de/api/interpreter"
OSM_QUERIES = {
    "boundaries/osm_sarawak_admin6.json": (
        '[out:json][timeout:180];area["name:en"="Sarawak"]["admin_level"="4"]->.s;'
        'rel(area.s)["boundary"="administrative"]["admin_level"="6"];out geom;'
    ),
    "boundaries/osm_new_district_towns.json": (
        '[out:json][timeout:60];area["ISO3166-1"="MY"][admin_level=2]->.my;'
        'node(area.my)["place"="town"]["name"~"^(Siburan|Membakut)$"];out;'
    ),
}


# Hansard Dewan Rakyat 11.11.2026 (corrected edition), linked from
# https://www.parlimen.gov.my/hansard-dewan-rakyat.html?uweb=dr&lang=bm . Source of
# data/raw/hansard_schools_2026-11-11.csv (oral question 11, printed p.33 / PDF p.39).
# PDFs are gitignored; this keeps the original re-downloadable.
HANSARD = {
    "hansard/DR-11112026_pembetulan_Tumpat.pdf":
        "https://www.parlimen.gov.my/files/hindex/pdf/DR-11112026%20-%20pembetulan%20Tumpat.pdf",
}


# MOE "Senarai Sekolah Rendah dan Menengah" (government + government-aided schools), data as at
# 30 Jun 2022, the newest complete list in MOE's download area (www.moe.gov.my/muatturun,
# folder laporan_dan_statistik/senarai_sekolah). Served by the site's elFinder connector; the
# target is the folder path base64url-encoded. Includes KOORDINATXX (lon) / KOORDINATYY (lat).
MOE_CONNECTOR = "https://www.moe.gov.my/muatturun/connector?cmd=file&download=1&target="
MOE = {
    "moe/senarai_sekolah_rendah_menengah_jun2022.xlsx": MOE_CONNECTOR
    + "l1_bGFwb3Jhbl9kYW5fc3RhdGlzdGlrL3NlbmFyYWlfc2Vrb2xhaC9TZW5hcmFpIFNla29sYWggUmVuZGFoIGRhbiBNZW5lbmdhaCBKdW4gMjAyMi54bHN4",
}


def is_pdf(p: Path) -> bool:
    with p.open("rb") as f:
        return f.read(5) == b"%PDF-"


def is_geojson(p: Path) -> bool:
    try:
        return len(json.loads(p.read_text(encoding="utf-8"))["features"]) > 0
    except (ValueError, KeyError):
        return False


def is_csv(p: Path) -> bool:
    head = p.read_text(encoding="utf-8", errors="replace")[:200]
    return "," in head and "<html" not in head.lower()


def is_overpass(p: Path) -> bool:
    try:
        return len(json.loads(p.read_text(encoding="utf-8"))["elements"]) > 0
    except (ValueError, KeyError):
        return False


def is_parquet(p: Path) -> bool:
    if p.stat().st_size < 12:
        return False
    with p.open("rb") as f:
        head = f.read(4)
        f.seek(-4, 2)
        tail = f.read(4)
    return head == b"PAR1" and tail == b"PAR1"


def is_xlsx(p: Path) -> bool:
    if not zipfile.is_zipfile(p):
        return False
    with zipfile.ZipFile(p) as z:
        return "xl/workbook.xml" in z.namelist()


def fetch(name: str, url: str, check, force: bool, post_query: str | None = None) -> None:
    dest = RAW / name
    if dest.exists() and not force:
        status = "ok" if check(dest) else "INVALID"
        print(f"[skip]  {name} exists ({dest.stat().st_size:,} B, {status})")
        if status != "ok":
            sys.exit(f"Existing file {dest} failed validation; rerun with --force.")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    data = urllib.parse.urlencode({"data": post_query}).encode() if post_query else None
    # Overpass rejects browser-like User-Agents (HTTP 406); it gets a plain client name.
    headers = {"User-Agent": "datathon-pipeline/1.0"} if post_query else UA
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r, part.open("wb") as out:
        out.write(r.read())
        ctype = r.headers.get("Content-Type", "")
    if not check(part):
        part.unlink()
        sys.exit(f"FAILED: {url} did not return a valid file (Content-Type: {ctype}). Not saved.")
    part.replace(dest)
    print(f"[get]   {name} ({dest.stat().st_size:,} B) <- {url}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-download files that already exist")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    for name, url in PARQUET.items():
        fetch(name, url, is_parquet, args.force)
    for name, url in XLSX.items():
        fetch(name, url, is_xlsx, args.force)
    for name, url in BOUNDARIES.items():
        fetch(name, url, is_geojson if name.endswith(".geojson") else is_csv, args.force)
    for name, query in OSM_QUERIES.items():
        fetch(name, OVERPASS, is_overpass, args.force, post_query=query)
    for name, url in HANSARD.items():
        fetch(name, url, is_pdf, args.force)
    for name, url in MOE.items():
        fetch(name, url, is_xlsx, args.force)
    n = len(PARQUET) + len(XLSX) + len(BOUNDARIES) + len(OSM_QUERIES) + len(HANSARD) + len(MOE)
    print(f"All {n} files present and valid in {RAW}")
    print("Ookla tiles are large and handled separately: python scripts/download_ookla.py")


if __name__ == "__main__":
    main()
