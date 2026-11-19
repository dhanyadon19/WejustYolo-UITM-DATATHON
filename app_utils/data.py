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
def district_table() -> pd.DataFrame:
    """One row per district joining index, costing, Ookla, access 2024/25 and amenities."""
    gi = csv("gap_index_districts")
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
    return df


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
