"""Defensive checks shared by the pipeline scripts: fail early with a clear message instead of a
stack trace deep inside pandas. Each check names the file / step that produces the missing input."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# which script produces each input (for error messages)
PRODUCED_BY = {
    "raw": "scripts/download_raw.py",
    "ookla_raw": "scripts/download_ookla.py",
    "dosm_hh_ict_district": "scripts/extract_t3.py",
    "district_aliases": "scripts/extract_t3.py",
    "districts.geojson": "scripts/build_boundaries.py",
    "ookla_my_": "scripts/download_ookla.py",
    "ookla_district_": "scripts/build_ookla.py",
    "gap_index_districts": "scripts/build_index.py",
}


def _hint(p: Path) -> str:
    for k, v in PRODUCED_BY.items():
        if k in p.name:
            return v
    return PRODUCED_BY["ookla_raw"] if "ookla" in str(p).replace("\\", "/") and "/raw/" in str(p).replace("\\", "/") \
        else PRODUCED_BY["raw"] if "/raw/" in str(p).replace("\\", "/") else "the pipeline (see CLAUDE.md)"


def fail(msg: str) -> None:
    sys.exit(f"\nERROR: {msg}")


def require_files(*paths: Path) -> None:
    """Stop if any input file is missing, saying which script creates it."""
    missing = [Path(p) for p in paths if not Path(p).exists()]
    if missing:
        fail("missing input file(s):\n" + "\n".join(f"  - {p}  (run {_hint(p)})" for p in missing))


def require_nonempty(df: pd.DataFrame, label: str, hint: str = "") -> None:
    if df is None or len(df) == 0:
        fail(f"{label} is empty. {hint}".strip())


def require_columns(df: pd.DataFrame, cols: list[str], label: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        fail(f"{label} lacks expected column(s) {missing}; found {list(df.columns)[:20]}. "
             "Has the source format changed?")


def check_coords(df: pd.DataFrame, lon: str, lat: str, label: str, name_col: str | None = None,
                 max_missing_share: float = 0.05) -> None:
    """Report rows without usable coordinates; stop if too many are missing (likely a format change)."""
    require_columns(df, [lon, lat], label)
    x, y = pd.to_numeric(df[lon], errors="coerce"), pd.to_numeric(df[lat], errors="coerce")
    bad = x.isna() | y.isna() | ~x.between(95, 125) | ~y.between(-2, 10)  # outside Malaysia's region
    n = int(bad.sum())
    if n == 0:
        return
    share = n / max(len(df), 1)
    names = df.loc[bad, name_col].astype(str).head(10).tolist() if name_col else []
    msg = f"{label}: {n} of {len(df)} rows ({100 * share:.1f}%) have missing or out-of-range coordinates" + \
          (f", e.g. {names}" if names else "")
    if share > max_missing_share:
        fail(msg + f". More than {100 * max_missing_share:.0f}% missing: check the source file.")
    print(f"WARNING: {msg}; they are kept but flagged and not placed on maps.")


def report_unmatched(left: set, right: set, left_label: str, right_label: str, fatal: bool = False,
                     allowed: set | None = None) -> None:
    """Print keys present on one side only. With fatal=True, stop unless every gap is in `allowed`."""
    allowed = allowed or set()
    a, b = sorted(left - right), sorted(right - left)
    if a:
        print(f"UNMATCHED: {len(a)} in {left_label} but not in {right_label}: {a[:25]}")
    if b:
        print(f"UNMATCHED: {len(b)} in {right_label} but not in {left_label}: {b[:25]}")
    unexpected = (set(a) | set(b)) - allowed
    if fatal and unexpected:
        fail(f"unexpected unmatched districts {sorted(unexpected)[:25]}: add a spelling alias in "
             "scripts/extract_t3.py (ALIASES) or check the source; districts are never merged or renamed silently.")
