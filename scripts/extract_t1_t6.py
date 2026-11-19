"""Extract household internet / broadband by state from DOSM ICTHS Table 1.2 and Table 6.4-6.6.

Inputs (raw, untouched): data/raw/icths_{2024,2025}_table1.xlsx (sheet 1.2),
                         data/raw/icths_{2024,2025}_table6.xlsx (sheets 6.4, 6.5, 6.6)
Outputs:
  data/processed/dosm_hh_internet_state.csv   Table 1.2, both editions (year = survey year)
  data/processed/dosm_hh_internet_trend.csv   Table 6.4 internet, 6.5 fixed broadband,
                                              6.6 mobile broadband, 2021-2025
Long format: year, state, indicator (internet | mobile_broadband | fixed_broadband),
strata (total | urban | rural), pct. "n.a." (no rural population: KL, Putrajaya) -> blank.

Table 6 editions overlap (2024 file: 2021-2024; 2025 file: 2022-2025). For each year the newest
edition is used (column `edition`); differences between editions in overlapping years are
printed. Older years in Table 6 are rounded to one decimal by DOSM.

Usage: python scripts/extract_t1_t6.py
"""
from __future__ import annotations

from pathlib import Path

import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW, PROC = ROOT / "data" / "raw", ROOT / "data" / "processed"
EDITIONS = (2024, 2025)
STRATA = {"jumlah": "total", "bandar": "urban", "luar bandar": "rural"}
T1_GROUPS = {"internet": "internet", "jalur lebar mudah alih": "mobile_broadband",
             "jalur lebar tetap": "fixed_broadband"}
T6_SHEETS = {"6.4": "internet", "6.5": "fixed_broadband", "6.6": "mobile_broadband"}


def strata_of(cell) -> str | None:
    if not isinstance(cell, str):
        return None
    malay = cell.split("\n")[0].strip().lower()
    return STRATA.get(malay)


def state_rows(rows):
    for r in rows:
        name = r[0]
        if not isinstance(name, str):
            continue
        name = " ".join(name.split())
        # header cell reads "Negeri \nState" (not to be confused with the state Negeri Sembilan)
        if name == "Negeri State" or name.startswith(("Jadual", "Table", "Nota", "Note", "Sumber", "Source", "(")):
            continue
        yield ("Malaysia" if name.upper() == "MALAYSIA" else name), r


def num(v):
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str) and v.strip().lower() in ("n.a.", "na", "-"):
        return None
    raise ValueError(f"unexpected cell value {v!r}")


def header_row(rows, test):
    for i, r in enumerate(rows):
        if test(r):
            return i
    raise ValueError("header row not found")


def parse_t1(edition: int) -> pd.DataFrame:
    ws = openpyxl.load_workbook(RAW / f"icths_{edition}_table1.xlsx", read_only=True, data_only=True)["1.2"]
    rows = list(ws.iter_rows(values_only=True))
    gi = header_row(rows, lambda r: isinstance(r[0], str) and r[0].strip().startswith("Negeri"))
    groups, cur = {}, None
    for j, v in enumerate(rows[gi]):
        if j and isinstance(v, str):
            cur = T1_GROUPS[v.split("\n")[0].strip().lower()]
        groups[j] = cur
    si = header_row(rows[gi:], lambda r: sum(strata_of(v) is not None for v in r) >= 6) + gi
    cols = {j: (groups[j], strata_of(v)) for j, v in enumerate(rows[si]) if strata_of(v)}
    assert len(cols) == 9, f"Table 1.2 {edition}: expected 9 columns, got {cols}"
    out = []
    for state, r in state_rows(rows[si + 1:]):
        for j, (ind, st) in cols.items():
            out.append({"year": edition, "state": state, "indicator": ind, "strata": st, "pct": num(r[j])})
    return pd.DataFrame(out)


def parse_t6(edition: int, sheet: str) -> pd.DataFrame:
    ws = openpyxl.load_workbook(RAW / f"icths_{edition}_table6.xlsx", read_only=True, data_only=True)[sheet]
    rows = list(ws.iter_rows(values_only=True))
    yi = header_row(rows, lambda r: isinstance(r[0], str) and r[0].strip().startswith("Negeri"))
    years, cur = {}, None
    for j, v in enumerate(rows[yi]):
        if j and isinstance(v, (int, float)):
            cur = int(v)
        years[j] = cur
    si = yi + 1
    cols = {j: (years[j], strata_of(v)) for j, v in enumerate(rows[si]) if strata_of(v)}
    assert len(cols) == 12, f"Table {sheet} {edition}: expected 12 columns, got {cols}"
    out = []
    for state, r in state_rows(rows[si + 1:]):
        for j, (yr, st) in cols.items():
            out.append({"year": yr, "state": state, "indicator": T6_SHEETS[sheet], "strata": st,
                        "pct": num(r[j]), "edition": edition})
    return pd.DataFrame(out)


def main() -> None:
    t1 = pd.concat([parse_t1(e) for e in EDITIONS], ignore_index=True)
    assert t1["state"].nunique() == 17, sorted(t1["state"].unique())
    t1.to_csv(PROC / "dosm_hh_internet_state.csv", index=False)
    print(f"wrote data/processed/dosm_hh_internet_state.csv: {len(t1)} rows, years {sorted(t1.year.unique())}")

    t6 = pd.concat([parse_t6(e, s) for e in EDITIONS for s in T6_SHEETS], ignore_index=True)
    k = ["year", "state", "indicator", "strata"]
    wide = t6.pivot_table(index=k, columns="edition", values="pct").dropna()
    diff = wide[(wide[2024] - wide[2025]).abs() > 0.051]
    print(f"Table 6 overlapping years compared: {len(wide)} values; differing by more than rounding (0.05 pp): {len(diff)}")
    if len(diff):
        print(diff.head(20).to_string())
    trend = t6.sort_values("edition").drop_duplicates(k, keep="last").sort_values(k)
    trend.to_csv(PROC / "dosm_hh_internet_trend.csv", index=False)
    print(f"wrote data/processed/dosm_hh_internet_trend.csv: {len(trend)} rows, years {sorted(trend.year.unique())}")

    # cross-check: Table 1.2 (2025) equals Table 6.4 (2025) for internet
    a = t1[(t1.year == 2025) & (t1.indicator == "internet")].set_index(["state", "strata"])["pct"]
    b = trend[(trend.year == 2025) & (trend.indicator == "internet")].set_index(["state", "strata"])["pct"]
    j = pd.concat([a, b], axis=1, keys=["t1", "t6"]).dropna()
    print(f"check Table 1.2 vs 6.4 (2025 internet): max abs difference {float((j.t1 - j.t6).abs().max()):.3f} pp over {len(j)} values")
    m = t1[(t1.year == 2025) & (t1.state == "Malaysia")].pivot(index="indicator", columns="strata", values="pct").round(2)
    print("Malaysia 2025 (Table 1.2):\n" + m.to_string())


if __name__ == "__main__":
    main()
