"""Beyond Coverage: Connectivity Intelligence Malaysia (MDIT 2026 Datathon).

Run: streamlit run app.py
"""
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Beyond Coverage", page_icon="📶", layout="wide")

PAGES = [
    ("pages/1_Overview.py", "Overview", "🧭"),
    ("pages/2_Schools.py", "Schools", "🏫"),
    ("pages/3_Sarawak_map.py", "Sarawak map", "🗺️"),
    ("pages/4_District_detail.py", "District detail", "🔎"),
    ("pages/5_Priorities.py", "Priorities", "🎯"),
    ("pages/6_Method.py", "Method & limitations", "📐"),
]
pages = [st.Page(p, title=t, icon=i, default=(n == 0))
         for n, (p, t, i) in enumerate(PAGES) if (ROOT / p).exists()]

with st.sidebar:
    st.caption("Beyond Coverage · Connectivity Intelligence Malaysia")
st.navigation(pages).run()
