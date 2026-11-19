"""Small derived tables the dashboard reads (so the app only reads data/processed and config).

Outputs (data/processed/)
  hansard_schools.csv      copy of data/raw/hansard_schools_2026-11-11.csv (Parliament's figures)
  schools_all.csv          all 10,230 MOE schools (Jun 2022) with coordinates, district,
                           level, urban/rural, students, coord_flag (map points)
  amenities_district.csv   household access to electricity / piped water / sanitation, latest
                           year per district (OpenDOSM hh_access_amenities), Table 3 spelling

Usage: python scripts/build_app_data.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW, PROC = ROOT / "data" / "raw", ROOT / "data" / "processed"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_schools import assign_districts, load_schools  # noqa: E402


def main() -> None:
    shutil.copyfile(RAW / "hansard_schools_2026-11-11.csv", PROC / "hansard_schools.csv")
    print("wrote data/processed/hansard_schools.csv")

    d = gpd.read_file(PROC / "districts.geojson")
    s = assign_districts(load_schools(states=None), d).drop(columns="geometry")
    cols = ["school_code", "school_name", "state", "district", "ppd", "level", "type", "urban_rural",
            "aid_status", "students", "teachers", "lon", "lat", "district_method", "coord_flag"]
    s[cols].to_csv(PROC / "schools_all.csv", index=False)
    print(f"wrote data/processed/schools_all.csv: {len(s)} schools; coord_flag {s['coord_flag'].value_counts().to_dict()}")

    amap = {(r.state, r.alias): r.canonical for r in pd.read_csv(PROC / "district_aliases.csv").itertuples()}
    a = pd.read_parquet(RAW / "hh_access_amenities.parquet")
    a["district"] = [amap.get((st, x), x) for st, x in zip(a["state"], a["district"])]
    single = a["state"].str.startswith("W.P.") | (a["state"] == "Perlis")
    a.loc[single & (a["district"] == "All Districts"), "district"] = a.loc[single & (a["district"] == "All Districts"), "state"]
    a = a[a["district"] != "All Districts"].copy()
    a["amenities_year"] = pd.to_datetime(a["date"]).dt.year
    a = a.sort_values("date").drop_duplicates(["state", "district"], keep="last")
    a = a[["state", "district", "amenities_year", "electricity", "piped_water", "sanitation"]]
    a.to_csv(PROC / "amenities_district.csv", index=False)
    t3 = pd.read_csv(PROC / "dosm_hh_ict_district_2025.csv")
    t3 = t3[t3["level"] != "state"]
    miss = set(zip(t3.state, t3.district)) - set(zip(a.state, a.district))
    print(f"wrote data/processed/amenities_district.csv: {len(a)} districts, years {a['amenities_year'].value_counts().to_dict()}; "
          f"Table 3 districts without amenities: {sorted(miss)}")


if __name__ == "__main__":
    main()
