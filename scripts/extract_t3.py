"""Extract DOSM ICTHS Table 3 (ICT access and use by administrative district) into tidy CSVs.

Input  (untouched raw):  data/raw/icths_{2024,2025}_table3.xlsx
Output (data/processed/):
  dosm_hh_ict_district_{year}.csv    sheet 3.1, households with access to ICT (%)
  dosm_ind_ict_district_{year}.csv   sheet 3.2, individuals using ICT (%)
  dosm_hh_internet_district_2024_2025.csv   household internet, both years side by side
  district_aliases.csv               spelling aliases applied when matching years

Parsing rules
  - Each sheet repeats its title / "(%)" / header rows on every printed page; those are skipped.
  - Indicator columns are taken from the header row ("Malay\\nEnglish"); the English part
    becomes <indicator>_pct. Any value found outside those columns stops the script.
  - An UPPERCASE name is a state (level="state", district="All Districts").
  - Rows under "WILAYAH PERSEKUTUAN" are federal territories (level="territory"), named the
    OpenDOSM way, e.g. state = district = "W.P. Kuala Lumpur".
  - Everything else is a district of the most recent state above it. Names are whitespace-stripped.
  - Names are kept in DOSM spelling (states title-cased to match OpenDOSM files).

Small-sample flag (estimate, not published by DOSM)
  DOSM does not publish district sample sizes. If every indicator of a district/territory that
  is strictly between 0 and 100 lies within 0.02 percentage points of a multiple of 100/n for
  some n <= 60, the estimate rests on roughly n sampled units (households in 3.1, individuals in
  3.2). Requires >= 3 such indicators. implied_sample_n is the smallest such n, and
  internet_moe95_pp = 1.96 * sqrt(p(1-p)/n) * 100 (simple random sampling approximation).

Usage:  python scripts/extract_t3.py
Exit code is non-zero if a parsing assertion or a 2024 check fails.
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import openpyxl
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _checks import check_coords, fail, report_unmatched, require_columns, require_files, require_nonempty  # noqa: E402,F401

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
YEARS = (2024, 2025)
SHEETS = {"3.1": "hh", "3.2": "ind"}

MAX_N = 60
TOL_PP = 0.02
MIN_INTERIOR = 3
WP_HEADER = "WILAYAH PERSEKUTUAN"

# Spelling aliases -> canonical = spelling in DOSM ICTHS Table 3 (2025). Same unit, different
# spelling only; no merges or splits. Written to data/processed/district_aliases.csv.
#  - "Seberang Prai ..." appears in the 2024 Table 3 (2025 and OpenDOSM files use "Perai").
#    Applied when combining years; per-year CSVs keep DOSM's spelling for that year.
#  - "Ulu ..." / "Kecil Lojing" appear in the DOSM boundary file and OpenDOSM population,
#    income and school files. Applied by build_boundaries.py and any later joins.
#  - "Meradong" is OpenStreetMap's spelling (Sarawak boundaries). Applied by build_boundaries.py.
T3_2024 = "ICTHS Table 3 (2024)"
OTHER = "DOSM boundaries; OpenDOSM population/income/schools"
ALIASES = [
    *[("Pulau Pinang", f"Seberang Prai {p}", f"Seberang Perai {p}", T3_2024)
      for p in ("Utara", "Tengah", "Selatan")],
    ("Selangor", "Ulu Langat", "Hulu Langat", OTHER),
    ("Selangor", "Ulu Selangor", "Hulu Selangor", OTHER),
    ("Kelantan", "Kecil Lojing", "Lojing", OTHER),
    ("Sarawak", "Meradong", "Maradong", "OpenStreetMap boundaries; GADM; MOE enrolment"),
    ("Perak", "Larut & Matang", "Larut Dan Matang", "OpenDOSM income (2024)"),
    ("Pulau Pinang", "S.P. Selatan", "Seberang Perai Selatan", "OpenDOSM income (2024)"),
    ("Pulau Pinang", "S.P.Tengah", "Seberang Perai Tengah", "OpenDOSM income (2024)"),
    ("Pulau Pinang", "S.P.Utara", "Seberang Perai Utara", "OpenDOSM income (2024)"),
    ("Sarawak", "Lubok antu", "Lubok Antu", "OpenDOSM income (2024)"),
    ("Terengganu", "Hulu", "Hulu Terengganu", "OpenDOSM income (2024)"),
    ("Perak", "Larut dan Matang", "Larut Dan Matang", "DOSM Census 2020 (census_district.csv)"),
]


def clean_name(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def indicator_key(header: str) -> str:
    """'Telefon bimbit\\nMobile phone' -> 'mobile_phone_pct'; 'Internet' -> 'internet_pct'."""
    english = str(header).split("\n")[-1]
    return re.sub(r"[^a-z0-9]+", "_", english.strip().lower()).strip("_") + "_pct"


def is_header_row(first: str) -> bool:
    return first.startswith(("Jadual", "Table", "(%)", "Negeri"))


def parse_sheet(path: Path, sheet: str, year: int) -> pd.DataFrame:
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)[sheet]
    rows = list(ws.iter_rows(values_only=True))

    header = next(r for r in rows if isinstance(r[0], str) and r[0].strip().startswith("Negeri"))
    cols = {i: indicator_key(v) for i, v in enumerate(header) if i > 0 and v not in (None, "")}
    assert len(set(cols.values())) == len(cols), f"duplicate indicator names in {path.name} {sheet}: {cols}"

    records, state, in_wp = [], None, False
    for r_idx, row in enumerate(rows, 1):
        first = row[0]
        if first is None or str(first).strip() == "":
            # the repeated page header puts its "(%)" unit label in a later column
            stray = [v for v in row[1:] if v not in (None, "") and str(v).strip() != "(%)"]
            assert not stray, f"{path.name} {sheet} row {r_idx}: values without a name: {stray}"
            continue
        first = clean_name(first)
        if is_header_row(first):
            continue
        extra = [v for i, v in enumerate(row) if i > 0 and i not in cols and v not in (None, "")]
        assert not extra, f"{path.name} {sheet} row {r_idx}: values outside indicator columns: {extra}"
        values = {key: row[i] if i < len(row) else None for i, key in cols.items()}

        if first.upper() == WP_HEADER:
            in_wp, state = True, None
            assert all(v is None for v in values.values()), f"WP header row has values: {values}"
            continue
        if in_wp:
            name = f"W.P. {first}"
            level, st, dist = "territory", name, name
        elif first.isupper():
            state = first.title()
            level, st, dist = "state", state, "All Districts"
        else:
            assert state is not None, f"{path.name} {sheet} row {r_idx}: district '{first}' before any state"
            level, st, dist = "district", state, first

        bad = {k: v for k, v in values.items() if not isinstance(v, (int, float))}
        assert not bad, f"{path.name} {sheet} row {r_idx} ({first}): non-numeric values {bad}"
        records.append({"year": year, "level": level, "state": st, "district": dist,
                        **{k: float(v) for k, v in values.items()}})

    df = pd.DataFrame(records)
    dups = df[df.duplicated(["state", "district"], keep=False)]
    assert dups.empty, f"duplicate state+district in {path.name} {sheet}:\n{dups}"
    return df


def implied_n(values: list[float]) -> int | None:
    interior = [v for v in values if 0 < v < 100]
    if len(interior) < MIN_INTERIOR:
        return None
    for n in range(1, MAX_N + 1):
        step = 100 / n
        if all(abs(v - round(v / step) * step) <= TOL_PP for v in interior):
            return n
    return None


def add_small_sample(df: pd.DataFrame) -> pd.DataFrame:
    ind_cols = [c for c in df.columns if c.endswith("_pct")]
    ns = [
        implied_n(row[ind_cols].tolist()) if row["level"] != "state" else None
        for _, row in df.iterrows()
    ]
    df["implied_sample_n"] = pd.array(ns, dtype="Int64")
    df["small_sample_flag"] = df["implied_sample_n"].notna()

    def moe(row):
        n = row["implied_sample_n"]
        if pd.isna(n):
            return float("nan")
        p = row["internet_pct"] / 100
        return 1.96 * math.sqrt(p * (1 - p) / n) * 100

    df["internet_moe95_pp"] = df.apply(moe, axis=1)
    return df


def write_aliases(hh: dict[int, pd.DataFrame]) -> pd.DataFrame:
    """Write the alias table. Canonical names must exist in Table 3 2025; Table 3 aliases must
    exist in Table 3 2024 (other aliases are checked by the scripts that apply them)."""
    names = {y: set(zip(hh[y]["state"], hh[y]["district"])) for y in YEARS}
    rows = []
    for state, alias, canonical, found_in in ALIASES:
        assert (state, canonical) in names[2025], f"canonical {state}/{canonical} not in Table 3 2025"
        if found_in == T3_2024:
            assert (state, alias) in names[2024], f"alias {state}/{alias} not in Table 3 2024"
        rows.append({"state": state, "alias": alias, "canonical": canonical,
                     "alias_found_in": found_in, "canonical_source": "ICTHS Table 3 (2025)"})
    df = pd.DataFrame(rows)
    dest = OUT / "district_aliases.csv"
    df.to_csv(dest, index=False)
    print(f"wrote {dest.relative_to(ROOT)}: {len(df)} aliases")
    return df


def apply_aliases(df: pd.DataFrame, aliases: pd.DataFrame) -> pd.DataFrame:
    amap = {(r.state, r.alias): r.canonical for r in aliases.itertuples()}
    df = df.copy()
    df["district"] = [amap.get((s, d), d) for s, d in zip(df["state"], df["district"])]
    return df


def change_beyond_noise(row) -> object:
    """True if |change| exceeds every available 95% MOE; NA if neither year has an MOE."""
    moes = [m for m in (row["internet_moe95_pp_2024"], row["internet_moe95_pp_2025"]) if not pd.isna(m)]
    if not moes or pd.isna(row["internet_change_pp"]):
        return pd.NA
    return bool(abs(row["internet_change_pp"]) > max(moes))


def combine_internet(hh: dict[int, pd.DataFrame], aliases: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    keep = ["level", "state", "district", "internet_pct", "small_sample_flag", "internet_moe95_pp"]
    a, b = (apply_aliases(hh[y][hh[y]["level"] != "state"][keep], aliases) for y in YEARS)
    m = a.merge(b, on=["state", "district"], how="outer", suffixes=("_2024", "_2025"), indicator=True)
    m["level"] = m["level_2024"].fillna(m["level_2025"])
    m = m.rename(columns={"internet_pct_2024": "internet_2024", "internet_pct_2025": "internet_2025"})
    m["internet_change_pp"] = m["internet_2025"] - m["internet_2024"]
    m["change_beyond_noise"] = pd.array([change_beyond_noise(r) for _, r in m.iterrows()], dtype="boolean")
    m["matched"] = m["_merge"] == "both"
    unmatched = m[~m["matched"]][["state", "district", "_merge"]]
    cols = ["level", "state", "district", "internet_2024", "internet_2025", "internet_change_pp",
            "small_sample_flag_2024", "internet_moe95_pp_2024",
            "small_sample_flag_2025", "internet_moe95_pp_2025", "change_beyond_noise", "matched"]
    return m[cols].sort_values(["state", "district"]).reset_index(drop=True), unmatched


def run_checks(hh24: pd.DataFrame, hh25: pd.DataFrame) -> bool:
    ok = True
    print("\n=== Checks (2024 household file) ===")
    counts = hh24["level"].value_counts().to_dict()
    print(f"levels: {counts}")
    for lvl, exp, lo, hi in [("district", 162, 155, 170), ("state", 13, 13, 13), ("territory", 3, 3, 3)]:
        got = counts.get(lvl, 0)
        good = lo <= got <= hi
        ok &= good
        print(f"  [{'PASS' if good else 'FAIL'}] {lvl}: {got} (expected about {exp})")

    sk = hh24[hh24["state"] == "Sarawak"].set_index("district")
    show = ["internet_pct", "small_sample_flag", "implied_sample_n", "internet_moe95_pp"]
    expect = [
        ("Kanowit", 60.71, True, 56, 12.8),
        ("Song", 64.81, None, None, None),
        ("Tebedu", 66.67, None, None, None),
        ("Simunjan", 65.22, False, None, None),
    ]
    failed_rows = []
    for dist, pct, flag, n, moe in expect:
        if dist not in sk.index:
            ok = False
            print(f"  [FAIL] {dist}: not found in Sarawak 2024")
            continue
        r = sk.loc[dist]
        msgs, good = [], True
        good &= round(r["internet_pct"], 2) == pct
        msgs.append(f"internet={r['internet_pct']:.2f} (exp {pct})")
        if flag is not None:
            good &= bool(r["small_sample_flag"]) == flag
            msgs.append(f"flag={bool(r['small_sample_flag'])} (exp {flag})")
        if n is not None:
            got_n = r["implied_sample_n"]
            good &= (not pd.isna(got_n)) and int(got_n) == n
            msgs.append(f"n={got_n} (exp {n})")
        if moe is not None:
            got_m = r["internet_moe95_pp"]
            good &= (not pd.isna(got_m)) and abs(got_m - moe) <= 0.1
            msgs.append(f"MOE={got_m:.2f} (exp ~{moe})")
        ok &= bool(good)
        if not good:
            failed_rows.append(dist)
        print(f"  [{'PASS' if good else 'FAIL'}] {dist}: " + ", ".join(msgs))

    if failed_rows:
        print("\nFailing rows (full):")
        print(hh24[(hh24["state"] == "Sarawak") & hh24["district"].isin(failed_rows)].to_string())

    print("\n=== 10 lowest Sarawak districts, household internet 2025 ===")
    low = hh25[(hh25["state"] == "Sarawak") & (hh25["level"] == "district")].nsmallest(10, "internet_pct")
    print(low[["district"] + show].to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    return ok


def main() -> None:
    require_files(*[RAW / f"icths_{y}_table3.xlsx" for y in YEARS])
    OUT.mkdir(parents=True, exist_ok=True)
    out = {"hh": {}, "ind": {}}
    for year in YEARS:
        path = RAW / f"icths_{year}_table3.xlsx"
        for sheet, kind in SHEETS.items():
            df = add_small_sample(parse_sheet(path, sheet, year))
            dest = OUT / f"dosm_{kind}_ict_district_{year}.csv"
            df.to_csv(dest, index=False)
            out[kind][year] = df
            print(f"wrote {dest.relative_to(ROOT)}: {len(df)} rows, "
                  f"{int(df['small_sample_flag'].sum())} small-sample flagged, "
                  f"indicators={[c for c in df.columns if c.endswith('_pct')]}")

    aliases = write_aliases(out["hh"])
    combined, unmatched = combine_internet(out["hh"], aliases)
    dest = OUT / "dosm_hh_internet_district_2024_2025.csv"
    combined.to_csv(dest, index=False)
    print(f"wrote {dest.relative_to(ROOT)}: {len(combined)} rows "
          f"({combined['level'].value_counts().to_dict()})")
    cbn = combined["change_beyond_noise"]
    print(f"  change_beyond_noise: True={int((cbn == True).sum())}, False={int((cbn == False).sum())}, "
          f"blank={int(cbn.isna().sum())}")
    if unmatched.empty:
        print("  all rows matched between 2024 and 2025 (state + district, after aliases)")
    else:
        print(f"  {len(unmatched)} UNMATCHED rows (kept in file with matched=False):")
        print(unmatched.to_string(index=False))

    if not run_checks(out["hh"][2024], out["hh"][2025]):
        sys.exit("\n2024 checks FAILED, see rows above. Code not adjusted to force a match.")
    print("\nAll 2024 checks passed.")


if __name__ == "__main__":
    main()
