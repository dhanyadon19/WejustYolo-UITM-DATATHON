"""Connectivity Gap Index (CGI) per district, with need ranking, sensitivity and beneficiaries.

Inputs (latest available year of each source; the year used is recorded per row)
  access_gap    100 - household internet access %   dosm_hh_ict_district_2025.csv (ICTHS Table 3)
  mobile_speed  Ookla mobile test-weighted download  ookla_district_{y}q{q}.csv (inverted)
  fixed_reach   Ookla fixed tests per 1,000 residents (PROXY; inverted)
  low_income    median household income               raw/hh_income_district.parquet (inverted)
  population    raw/population_district.parquet (thousands; sex=both, age=overall, ethnicity=overall)
  students      MOE school list (Jun 2022): pupils (MURID) of schools located in the district.
                MOE's enrolment_school_district is by education office (PPD), whose areas do not
                match administrative districts (merged, split and renamed offices), so it is used
                only as a state-level cross-check.
  weights       config/weights.yaml

Method
  Each indicator is min-max normalised across all indexed districts so 1 = worst, 0 = best;
  CGI = sum(weight x normalised indicator). Need rank 1 = highest CGI (worst), nationally and
  within Sarawak. A district is indexed only if all four indicators exist (missing ones listed).
  Perlis (single district, DOSM publishes only its state row) is indexed as district "Perlis".

Sensitivity (data/processed/gap_index_sensitivity.csv)
  - equal weights (0.25 each)
  - 1,000 Dirichlet(1,1,1,1) weight sets (seed 42): median and 5th-95th percentile rank
  - small-sample districts: access set to p -/+ its 95% MOE (clipped to 0-100), everything
    else unchanged, CGI and ranks recomputed; rank range over low / central / high

Beneficiaries (ESTIMATES)
  people_without_home_internet = population x 1000 x access_gap / 100 (assumes individuals
  follow the household rate); students as above.

Usage: python scripts/build_index.py
"""
from __future__ import annotations

import re
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
RAW, PROC = ROOT / "data" / "raw", ROOT / "data" / "processed"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_schools import assign_districts, load_schools  # noqa: E402

OUT = PROC / "gap_index_districts.csv"
OUT_SENS = PROC / "gap_index_sensitivity.csv"
WEIGHTS = ROOT / "config" / "weights.yaml"
INDICATORS = ["access_gap", "mobile_speed", "fixed_reach", "low_income"]
INVERTED = {"access_gap": False, "mobile_speed": True, "fixed_reach": True, "low_income": True}
N_RUNS, SEED, FOCUS = 1000, 42, "Sarawak"


def aliases() -> dict[tuple[str, str], str]:
    a = pd.read_csv(PROC / "district_aliases.csv")
    return {(r.state, r.alias): r.canonical for r in a.itertuples()}


def canon(df: pd.DataFrame, amap) -> pd.DataFrame:
    df = df.copy()
    df["district"] = [amap.get((s, d), d) for s, d in zip(df["state"], df["district"])]
    # territories and single-district Perlis appear as "All Districts" or under their own name
    single = df["state"].str.startswith("W.P.") | (df["state"] == "Perlis")
    df.loc[single & (df["district"] == "All Districts"), "district"] = \
        df.loc[single & (df["district"] == "All Districts"), "state"]
    return df


def latest_per_district(df: pd.DataFrame, value_cols: list[str], year_col: str) -> pd.DataFrame:
    df = df[df["district"] != "All Districts"].dropna(subset=value_cols).copy()
    df[year_col] = pd.to_datetime(df["date"]).dt.year
    df = df.sort_values("date").drop_duplicates(["state", "district"], keep="last")
    return df[["state", "district", year_col] + value_cols]


def latest_ookla() -> tuple[pd.DataFrame, str]:
    files = sorted(PROC.glob("ookla_district_*q*.csv"),
                   key=lambda p: tuple(map(int, re.search(r"(\d{4})q(\d)", p.name).groups())))
    f = files[-1]
    return pd.read_csv(f), re.search(r"(\d{4})q(\d)", f.name).expand(r"\1Q\2")


def build_base() -> tuple[pd.DataFrame, list[str]]:
    amap = aliases()
    t3 = pd.read_csv(PROC / "dosm_hh_ict_district_2025.csv")
    t3 = t3[(t3["level"] != "state") | (t3["state"] == "Perlis")].copy()
    t3.loc[t3["state"] == "Perlis", ["district", "level"]] = ["Perlis", "district"]
    base = t3[["state", "district", "level", "internet_pct", "small_sample_flag",
               "implied_sample_n", "internet_moe95_pp"]].copy()
    base["access_year"] = int(t3["year"].iloc[0])
    base["access_gap"] = 100 - base["internet_pct"]

    ook, quarter = latest_ookla()
    ook["district"] = ook["district"]  # districts.geojson already uses Table 3 spelling
    for kind, cols in [("mobile", {"dl_mbps": "mobile_dl_mbps", "tests": "mobile_tests"}),
                       ("fixed", {"tests": "fixed_tests", "n_tiles": "fixed_tiles"})]:
        o = ook[ook["type"] == kind][["state", "district", *cols]].rename(columns=cols)
        base = base.merge(o, on=["state", "district"], how="left")
    base["ookla_quarter"] = quarter

    pop = canon(pd.read_parquet(RAW / "population_district.parquet"), amap)
    pop = pop[(pop["sex"] == "both") & (pop["age"] == "overall") & (pop["ethnicity"] == "overall")]
    pop = latest_per_district(pop.rename(columns={"population": "population_k"}), ["population_k"], "population_year")
    base = base.merge(pop, on=["state", "district"], how="left")

    inc = canon(pd.read_parquet(RAW / "hh_income_district.parquet"), amap)
    inc = latest_per_district(inc, ["income_median"], "income_year")
    base = base.merge(inc, on=["state", "district"], how="left")

    base["mobile_speed"] = base["mobile_dl_mbps"]
    base["fixed_reach"] = base["fixed_tests"] / base["population_k"]  # tests per 1,000 residents
    base["low_income"] = base["income_median"]

    # students from the MOE school list (Jun 2022), by school location
    d = gpd.read_file(PROC / "districts.geojson")
    sch = assign_districts(load_schools(states=None), d)
    st = (sch.dropna(subset=["district"]).groupby(["state", "district"])["students"].sum()
          .rename("students").reset_index())
    base = base.merge(st, on=["state", "district"], how="left")
    base["students_source"] = "MOE school list, 30 Jun 2022 (pupils of schools located in district)"
    unplaced = sch["district"].isna().sum()

    base["people_without_home_internet"] = (base["population_k"] * 1000 * base["access_gap"] / 100).round()

    notes = [f"schools not placed in any district (missing/suspect coordinates): {unplaced}"]
    e = pd.read_parquet(RAW / "enrolment_school_district.parquet")
    e = e[(e["date"] == e["date"].max()) & (e["sex"] == "both") & (e["district"] == "All Districts")]
    e_state = e.groupby("state")["students"].sum()
    s_state = sch.groupby("state")["students"].sum()
    cmp_ = pd.DataFrame({"enrolment_2025": e_state, "school_list_2022": s_state}).dropna()
    cmp_["pct_diff"] = (100 * (cmp_["school_list_2022"] - cmp_["enrolment_2025"]) / cmp_["enrolment_2025"]).round(1)
    notes.append("students cross-check by state (school list 2022 vs enrolment 2025):\n" + cmp_.to_string())
    return base, notes


def normalise(x: pd.Series, inverted: bool) -> pd.Series:
    lo, hi = x.min(), x.max()
    z = (x - lo) / (hi - lo) if hi > lo else x * 0.0
    return 1 - z if inverted else z


def cgi(df: pd.DataFrame, w: dict[str, float]) -> pd.Series:
    return sum(w[k] * normalise(df[k], INVERTED[k]) for k in INDICATORS)


def ranks(score: pd.Series, state: pd.Series) -> tuple[pd.Series, pd.Series]:
    nat = score.rank(ascending=False, method="min").astype(int)
    sk = score[state == FOCUS].rank(ascending=False, method="min").astype(int)
    return nat, sk.reindex(score.index)


def main() -> None:
    cfg = yaml.safe_load(WEIGHTS.read_text(encoding="utf-8"))["weights"]
    w = {k: float(cfg[k]["weight"]) for k in INDICATORS}
    assert abs(sum(w.values()) - 1) < 1e-9, f"weights must sum to 1: {w}"

    base, notes = build_base()
    complete = base[INDICATORS].notna().all(axis=1)
    missing = base.loc[~complete, ["state", "district"] + INDICATORS]
    df = base[complete].reset_index(drop=True)

    for k in INDICATORS:
        df[f"{k}_norm"] = normalise(df[k], INVERTED[k])
    df["cgi"] = cgi(df, w)
    df["rank_national"], df["rank_sarawak"] = ranks(df["cgi"], df["state"])

    # --- sensitivity: equal weights
    eq = {k: 1 / len(INDICATORS) for k in INDICATORS}
    s_eq = cgi(df, eq)
    r_eq_n, r_eq_s = ranks(s_eq, df["state"])

    # --- sensitivity: Dirichlet weights
    rng = np.random.default_rng(SEED)
    W = rng.dirichlet(np.ones(len(INDICATORS)), size=N_RUNS)
    Z = np.column_stack([df[f"{k}_norm"] for k in INDICATORS])
    S = Z @ W.T                                            # districts x runs
    RN = pd.DataFrame(S).rank(ascending=False, method="min").to_numpy()
    sk_mask = (df["state"] == FOCUS).to_numpy()
    RS = np.full_like(RN, np.nan)
    RS[sk_mask] = pd.DataFrame(S[sk_mask]).rank(ascending=False, method="min").to_numpy()

    # --- sensitivity: MOE bounds for small-sample districts
    moe_rows = {}
    for i in df.index[df["small_sample_flag"] & df["internet_moe95_pp"].notna()]:
        res = []
        for sign in (-1, 1):
            alt = df.copy()
            alt.at[i, "access_gap"] = 100 - float(np.clip(df.at[i, "internet_pct"] + sign * df.at[i, "internet_moe95_pp"], 0, 100))
            n, s = ranks(cgi(alt, w), alt["state"])
            res.append((n[i], s[i]))
        rn = [df.at[i, "rank_national"]] + [r[0] for r in res]
        rs = [df.at[i, "rank_sarawak"]] + [r[1] for r in res]
        moe_rows[i] = (min(rn), max(rn), np.nanmin(rs) if df.at[i, "state"] == FOCUS else np.nan,
                       np.nanmax(rs) if df.at[i, "state"] == FOCUS else np.nan)

    sens = df[["state", "district", "small_sample_flag", "cgi", "rank_national", "rank_sarawak"]].copy()
    sens["cgi_equal"] = s_eq
    sens["rank_national_equal"], sens["rank_sarawak_equal"] = r_eq_n, r_eq_s
    with warnings.catch_warnings():  # non-Sarawak rows have no Sarawak rank (all-NaN, expected)
        warnings.simplefilter("ignore", RuntimeWarning)
        for lab, R in [("national", RN), ("sarawak", RS)]:
            sens[f"rank_{lab}_dirichlet_median"] = np.nanmedian(R, axis=1)
            sens[f"rank_{lab}_dirichlet_p05"] = np.nanpercentile(R, 5, axis=1)
            sens[f"rank_{lab}_dirichlet_p95"] = np.nanpercentile(R, 95, axis=1)
    m = pd.DataFrame.from_dict(moe_rows, orient="index",
                               columns=["rank_national_moe_min", "rank_national_moe_max",
                                        "rank_sarawak_moe_min", "rank_sarawak_moe_max"])
    sens = sens.join(m)
    for c in [c for c in sens.columns if c.startswith("rank_")]:
        sens[c] = sens[c].astype("Int64") if not c.endswith(("median", "p05", "p95")) else sens[c]
    sens.insert(0, "n_runs", N_RUNS)
    sens.sort_values("rank_national").to_csv(OUT_SENS, index=False)

    # --- main output
    df["rank_national_p05"], df["rank_national_p95"] = sens["rank_national_dirichlet_p05"], sens["rank_national_dirichlet_p95"]
    df["rank_sarawak_p05"], df["rank_sarawak_p95"] = sens["rank_sarawak_dirichlet_p05"], sens["rank_sarawak_dirichlet_p95"]
    cols = ["state", "district", "level", "cgi", "rank_national", "rank_sarawak",
            "rank_national_p05", "rank_national_p95", "rank_sarawak_p05", "rank_sarawak_p95",
            *INDICATORS, *[f"{k}_norm" for k in INDICATORS],
            "internet_pct", "access_year", "small_sample_flag", "implied_sample_n", "internet_moe95_pp",
            "mobile_dl_mbps", "mobile_tests", "fixed_tests", "fixed_tiles", "ookla_quarter",
            "population_k", "population_year", "income_median", "income_year",
            "people_without_home_internet", "students", "students_source"]
    df[cols].sort_values("rank_national").to_csv(OUT, index=False)

    print(f"wrote {OUT.relative_to(ROOT)}: {len(df)} districts indexed; weights {w}")
    print(f"wrote {OUT_SENS.relative_to(ROOT)}")
    print("years used: access", df["access_year"].unique().tolist(), "| Ookla", df["ookla_quarter"].unique().tolist(),
          "| population", df["population_year"].value_counts().to_dict(), "| income", df["income_year"].value_counts().to_dict())
    print(f"\nNot indexed (missing an indicator), {len(missing)}:")
    print(missing.to_string(index=False) if len(missing) else "  none")
    for n in notes:
        print("\n" + n)

    sk = df[df["state"] == FOCUS].sort_values("rank_sarawak").merge(
        sens[["state", "district", "rank_sarawak_moe_min", "rank_sarawak_moe_max",
              "rank_sarawak_dirichlet_median"]], on=["state", "district"])
    sk["dirichlet_p05_p95"] = sk["rank_sarawak_p05"].astype(int).astype(str) + "-" + sk["rank_sarawak_p95"].astype(int).astype(str)
    sk["moe_range"] = np.where(sk["rank_sarawak_moe_min"].notna(),
                               sk["rank_sarawak_moe_min"].astype("string") + "-" + sk["rank_sarawak_moe_max"].astype("string"), "")
    show = ["rank_sarawak", "district", "cgi", "access_gap", "mobile_dl_mbps", "fixed_reach", "income_median",
            "rank_national", "dirichlet_p05_p95", "moe_range", "small_sample_flag", "internet_moe95_pp",
            "people_without_home_internet", "students"]
    print(f"\n=== Top 15 Sarawak districts by CGI (rank 1 = worst; ranks within Sarawak unless stated) ===")
    top15 = sk.head(15)[show].copy()
    for c in ["rank_sarawak", "rank_national", "people_without_home_internet", "students"]:
        top15[c] = top15[c].astype("Int64")
    print(top15.to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    for lab, R, base_rank, mask in [("national", RN, df["rank_national"], np.ones(len(df), bool)),
                                    ("Sarawak", RS, df["rank_sarawak"], sk_mask)]:
        top = df.index[(base_rank <= 10).to_numpy() & mask]
        stay = (R[top] <= 10).mean(axis=1)
        overlap = np.array([np.isin(np.where(R[:, j] <= 10)[0], top).sum() for j in range(N_RUNS)])
        print(f"\n=== Top-10 stability ({lab}) over {N_RUNS} Dirichlet runs ===")
        print(f"baseline top 10 still in top 10 per run: median {np.median(overlap):.0f}/10, "
              f"5th pct {np.percentile(overlap, 5):.0f}/10, min {overlap.min()}/10")
        t = df.loc[top, ["district", "state"]].assign(base_rank=base_rank[top].astype(int).values,
                                                      pct_runs_in_top10=(100 * stay).round(1))
        print(t.sort_values("base_rank").to_string(index=False))


if __name__ == "__main__":
    main()
