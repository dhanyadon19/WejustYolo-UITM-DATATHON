"""Data access for the dashboard. Every number shown in the app is read here, from
data/processed/ and config/ only; each file is read once per session (st.cache_data)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
CONFIG = ROOT / "config"

SIX_STATES = ["Kelantan", "Terengganu", "Pahang", "Kedah", "Sabah", "Sarawak"]


@st.cache_data(show_spinner=False)
def yaml_config(name: str) -> dict:
    return yaml.safe_load((CONFIG / f"{name}.yaml").read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def csv(name: str) -> pd.DataFrame:
    return pd.read_csv(PROC / f"{name}.csv")


def latest(prefix: str) -> str:
    """Name (without .csv) of the newest processed file for a quarterly source, e.g. ookla_district_."""
    files = sorted(PROC.glob(f"{prefix}*.csv"))
    return files[-1].stem


@st.cache_data(show_spinner=False)
def district_geojson(state: str | None = None, simplify_deg: float = 0.002) -> dict:
    """districts.geojson as a GeoJSON dict, optionally one state, simplified for fast rendering."""
    import geopandas as gpd

    g = gpd.read_file(PROC / "districts.geojson")
    if state:
        g = g[g["state"] == state]
    g["geometry"] = g.geometry.simplify(simplify_deg, preserve_topology=True)
    return json.loads(g.to_json())


@st.cache_data(show_spinner=False)
def boundary_keys() -> set[tuple[str, str]]:
    """(state, district) pairs that have a polygon in districts.geojson."""
    g = json.loads((PROC / "districts.geojson").read_text(encoding="utf-8"))
    return {(f["properties"]["state"], f["properties"]["district"]) for f in g["features"]}


@st.cache_data(show_spinner=False)
def unmapped_host() -> dict[tuple[str, str], str]:
    """Districts without a polygon -> the polygon that contains their town (contains_unmapped)."""
    g = json.loads((PROC / "districts.geojson").read_text(encoding="utf-8"))
    out = {}
    for f in g["features"]:
        p = f["properties"]
        for name in filter(None, (p.get("contains_unmapped") or "").split(";")):
            out[(p["state"], name)] = p["district"]
    return out


@st.cache_data(show_spinner=False)
def district_table() -> pd.DataFrame:
    """One row per district joining index, costing, Ookla, access 2024/25 and amenities.

    Includes every DOSM Table 3 district: those without a boundary (Siburan, Membakut) have no
    index, Ookla or costing values (NaN). Columns `indexed` and `has_boundary` say which is which."""
    gi = csv("gap_index_districts")
    t3 = csv("dosm_hh_ict_district_2025")
    extra = t3[(t3["level"] != "state")][["state", "district", "level"]]
    extra = extra[~extra.set_index(["state", "district"]).index.isin(gi.set_index(["state", "district"]).index)]
    gi = pd.concat([gi, extra], ignore_index=True)
    co = csv("costing_districts")
    ok = csv(latest("ookla_district_"))
    acc = csv("dosm_hh_internet_district_2024_2025")
    am = csv("amenities_district")
    sens = csv("gap_index_sensitivity")
    key = ["state", "district"]
    fixed = ok[ok["type"] == "fixed"][key + ["dl_mbps", "ul_mbps", "latency_median_ms", "tests", "low_sample"]]
    mobile = ok[ok["type"] == "mobile"][key + ["dl_mbps", "ul_mbps", "latency_median_ms", "tests", "low_sample"]]
    df = (gi.merge(fixed.add_prefix("fx_").rename(columns={"fx_state": "state", "fx_district": "district"}), on=key, how="left")
            .merge(mobile.add_prefix("mb_").rename(columns={"mb_state": "state", "mb_district": "district"}), on=key, how="left")
            .merge(acc.drop(columns=["level"]), on=key, how="left")
            .merge(am, on=key, how="left")
            .merge(sens[key + [c for c in sens.columns if c.endswith(("_moe_min", "_moe_max", "_equal")) or "dirichlet" in c]],
                   on=key, how="left")
            .merge(co.drop(columns=[c for c in ["cgi", "rank_national", "rank_sarawak", "small_sample_flag",
                                                 "people_without_home_internet", "population_k", "access_gap",
                                                 "household_size", "ookla_quarter"] if c in co.columns]),
                   on=key, how="left"))
    df = df.copy()  # de-fragment after the joins
    df["indexed"] = df["cgi"].notna()
    keys = boundary_keys()
    df["has_boundary"] = [(s, d) in keys for s, d in zip(df["state"], df["district"])]
    return df


FIX_CATS = ["takeup_gap", "satellite", "tower"]


@st.cache_data(show_spinner=False)
def fix_breakdown() -> pd.DataFrame:
    """One row per (state, district, category) for the main case: settlements, estimated rural people
    without home internet, five-year cost (main, Residential) and the same settlements' Lite-plan cost.
    Every district in costing_clusters gets all three categories (0 where none)."""
    cl = csv("costing_clusters")
    g = cl.groupby(["state", "district", "category_main"]).agg(
        n=("school_code", "size"), people=("unconnected_people", "sum"),
        cost_main=("cost_main", "sum"), cost_lite=("cost_lite", "sum")).reset_index().rename(columns={"category_main": "category"})
    full = cl[["state", "district"]].drop_duplicates().merge(pd.DataFrame({"category": FIX_CATS}), how="cross")
    g = full.merge(g, on=["state", "district", "category"], how="left")
    num = ["n", "people", "cost_main", "cost_lite"]
    g[num] = g[num].fillna(0)
    g["n"] = g["n"].astype(int)
    return g


@st.cache_data(show_spinner=False)
def census_year() -> int | None:
    """Census year behind the settlement households, read from costing_clusters.hh_source."""
    years = csv("costing_clusters")["hh_source"].astype(str).str.extract(r"Census (\d{4})")[0].dropna()
    return int(years.mode().iloc[0]) if not years.empty else None


@st.cache_data(show_spinner=False)
def settlement_groups() -> pd.DataFrame:
    """Per district: rural people without home internet by settlement category (main case)."""
    cl = csv("costing_clusters")
    t = cl.pivot_table(index=["state", "district"], columns="category_main", values="unconnected_people",
                       aggfunc="sum", fill_value=0).reset_index()
    for c in ["takeup_gap", "tower", "satellite"]:
        if c not in t:
            t[c] = 0.0
    t["largest_group"] = t[["takeup_gap", "tower", "satellite"]].idxmax(axis=1)
    return t
