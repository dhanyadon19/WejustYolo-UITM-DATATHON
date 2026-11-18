"""Download every raw dataset into data/raw/.

Sources (all official links, found on each dataset's catalogue / release page):
  - OpenDOSM / data.gov.my Parquet files (storage.dosm.gov.my, storage.data.gov.my)
  - DOSM "ICT Use and Access by Individuals and Households Survey Report"
    2024 and 2025, Tables 1, 2, 3, 6, 7 (release-document-log links)

Existing files are kept as-is (raw data stays untouched); pass --force to re-download.
Each file is validated (Parquet magic bytes / real .xlsx zip with a workbook) before
it is moved into place. Any failure stops the script with a non-zero exit code.

Usage:  python scripts/download_raw.py [--force]
"""
from __future__ import annotations

import argparse
import sys
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


def fetch(name: str, url: str, check, force: bool) -> None:
    dest = RAW / name
    if dest.exists() and not force:
        status = "ok" if check(dest) else "INVALID"
        print(f"[skip]  {name} exists ({dest.stat().st_size:,} B, {status})")
        if status != "ok":
            sys.exit(f"Existing file {dest} failed validation; rerun with --force.")
        return
    part = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers=UA)
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
    print(f"All {len(PARQUET) + len(XLSX)} files present and valid in {RAW}")


if __name__ == "__main__":
    main()
