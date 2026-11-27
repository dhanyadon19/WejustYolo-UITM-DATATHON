"""Beyond Coverage: Connectivity Intelligence Malaysia (MDIT 2026 Datathon).

Run: streamlit run app.py
"""
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Beyond Coverage", page_icon="📶", layout="wide")

# Menu grouped as a story (design guide): Start here -> Explore -> Plan -> About the data.
# Titles are plain names; file names (and so URLs such as /District_detail) stay unchanged.
GROUPS = {
    "Start here": [("views/1_Overview.py", "Overview", "🧭")],
    "Explore": [("views/3_Sarawak_map.py", "Sarawak map", "🗺️"),
                ("views/4_District_detail.py", "District profile", "🔎"),
                ("views/2_Schools.py", "Schools", "🏫")],
    "Plan": [("views/5_Priorities.py", "Where to invest", "🎯")],
    "About the data": [("views/6_Method.py", "Method & limitations", "📐")],
}
pages = {g: [st.Page(p, title=t, icon=i, default=(p == "views/1_Overview.py")) for p, t, i in items if (ROOT / p).exists()]
         for g, items in GROUPS.items()}

with st.sidebar:
    st.caption("Beyond Coverage · Connectivity Intelligence Malaysia")
st.navigation(pages).run()
