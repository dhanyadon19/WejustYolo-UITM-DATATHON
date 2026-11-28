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

# The menu must always show every page under its group heading (judges should not miss Explore):
# - expanded=True: never a "View more" button;
# - group headings cannot be clicked, so a section is never collapsed (Streamlit 1.67 makes them collapsible);
# - on phones the sidebar sits behind a button, so the same grouped menu is repeated at the top of the page body,
#   shown only below 768 px (the width at which Streamlit hides the sidebar).
st.html("<style>"
        "[data-testid=stNavSectionHeader]{pointer-events:none;cursor:default}"
        "[data-testid=stNavSectionHeader] svg{display:none}"
        ".st-key-mobile_menu{display:none}"
        "@media (max-width:767px){.st-key-mobile_menu{display:flex}}"
        ".st-key-mobile_menu p.bc-menu-h{margin:0.3rem 0 0 0;font-size:0.78rem;color:#52514e}"
        "</style>")
with st.sidebar:
    st.caption("Beyond Coverage · Connectivity Intelligence Malaysia")
pg = st.navigation(pages, expanded=True)  # registered first, so the page links below resolve
with st.container(key="mobile_menu", border=True, gap="small"):
    for g, pgs in pages.items():
        st.markdown(f"<p class='bc-menu-h'>{g}</p>", unsafe_allow_html=True)
        with st.container(horizontal=True, gap="small"):
            for p in pgs:
                st.page_link(p)
pg.run()
