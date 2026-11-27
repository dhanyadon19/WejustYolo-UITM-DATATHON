BEYOND COVERAGE: CONNECTIVITY INTELLIGENCE MALAYSIA
Team WejustYolo · MDIT Datathon 2026 · last updated 27 Nov 2026

A dashboard that finds rural communities that are "covered" on paper but not truly connected, and shows where
connectivity investment is needed most, which candidate technologies fit each kind of settlement, and the
estimated cost where a public cost source exists.

Live dashboard: https://wejustyolo-uitm-datathon-beyond-coverage.streamlit.app/

Package contents
  Data Product.pdf      screenshots of every page and key views, in page order, one-line caption each
  README.txt            this file
  source/               the code repository (without the Python environment and raw downloads)
  source/data/processed the cleaned data the dashboard reads (CSV, plus districts.geojson and two Ookla parquet files)


5.1 SOFTWARE AND VERSIONS
--------------------------
  Python      3.12
  streamlit   1.67.0     (web app)
  pandas      3.1.1
  geopandas   1.2.0      (district boundaries)
  pydeck      0.9.3      (maps, deck.gl)
  plotly      7.1.0      (charts)
  pyarrow     26.0.1
  openpyxl    3.1.5
  pyyaml      6.0.3
Exact pins: source/requirements.txt. Tests (development only): source/requirements-dev.txt (pytest).
Browser: any recent Chrome, Edge, Firefox or Safari. The 3D map needs WebGL (on by default in modern browsers).


5.2 STEP BY STEP
----------------
A. Open the live dashboard
  1. Open https://wejustyolo-uitm-datathon-beyond-coverage.streamlit.app/ in a browser.
  2. Use the menu on the left (on a phone: the >> button at the top left). It is grouped as a route:
     Start here (Overview) -> Explore (Sarawak map, District profile, Schools) -> Plan (Where to invest)
     -> About the data (Method & limitations).

B. Page-by-page guide (follow the menu from top to bottom)
  Reading aids on every page
     - Section titles state the finding (for example "Rural Sarawak: about 1 in 5 homes offline"); the line under
       each title says what the chart or table shows.
     - Confidence labels beside estimates: Solid (official figures as published), Indicative (our estimates and
       proxies), Low confidence (small survey samples, or the schools screen). The rule is on the Method page.
     - Uncertainty is given as numbers: "estimated 62% (±13 points)", "rank 1 (range 1–9)".
     - "More detail" under a chart opens the rest of its explanation; dotted-underlined terms show a plain-words
       explanation on hover. "Terms in plain words" (Overview and Method) lists them all.
  START HERE
  1. Overview
     - "Start here" box: three key findings, and a link that opens the Sarawak map at Sarawak's highest-need district.
     - "Covered is not the same as connected": the network reaches 99.71% of populated areas (mainly outdoor), yet
       some rural homes are still offline. Two different indicators, not a measured gap.
     - Headline cards: households with internet, rural households with internet, rural fixed broadband.
     - Tabs: "What would close the gap" (opens first: a bar of where the rural settlements fall by type, a collapsible
       "How settlements are grouped" flow, and the settlement-type table; switch All Malaysia / Sarawak) ·
       "By state" · "Urban vs rural" · "Trend" (pick an area and indicator).
  EXPLORE
  2. Sarawak map
     - "3D terrain" (default): every dot is a rural settlement (one per rural school, named after it), coloured by
       settlement type. Hover a dot for its type, candidate technologies, mobile signal, terrain, road distance,
       people and cost. Drag to pan, scroll to zoom, right-drag (or two fingers) to tilt.
     - Click a district, or pick one in the list under the map, to zoom to it. "Open <district> in District profile"
       goes to its full page. "Show all of Sarawak" zooms back out.
     - "Need score blocks": districts as 3D blocks, height = Need score (the Connectivity Gap Index). Colour by the
       largest group of rural people without home internet, or by the share of settlements needing take-up support.
     - "Table view" lists every district with a CSV download.
     Try: pick Kanowit -> "Open Kanowit in District profile".
  3. District profile
     - Pick a state and a district (or arrive from the map).
     - "What to do" box: need rank with its range, one card per settlement type (settlements, people offline,
       candidate technologies, cost or "not costed"), the reference cost and the checks to make on the ground.
       "Download action plan (CSV)" gives one row per rural settlement.
     - Tabs: "Settlements" (every rural settlement by school name, sortable, CSV) · "Households & speeds" (household
       access with margin of error, speeds, context) · "Need score" (rank, range and the four indicators) ·
       "Reference cost" (the tower-or-satellite cost screen used in the rankings, with sensitivity cases).
  4. Schools
     - Schools without fibre by state, as stated in Parliament (Hansard, 11 Nov 2026).
     - Map of MOE schools; pick a state. Switch on the "screening layer" to see schools with no fixed-broadband
       test nearby (low confidence). The table beside it compares that screen with Parliament's figures.
  PLAN
  5. Where to invest
     - The reference cost, shown once with its range; the sensitivity cases are in "Range and sensitivity cases".
     - Need score (the main ranking) vs people reached per RM1m, for Sarawak or all Malaysia, with the Residential
       or Lite satellite plan. Click a bubble to open that district.
     - Ranks with ranges (table, CSV download).
     - Budget planner: move the slider to set a five-year budget; districts are funded in order of need. A screening
       tool, not a funding recommendation.
  ABOUT THE DATA
  6. Method & limitations
     - How the Need score, the schools screen, the costing and the settlement types are built (with the grouping
       flow and terms in plain words), the confidence-label rule, sources, weights, sensitivity checks and limitations.
  Every page ends with its sources, the data years used and the date last updated.

C. Run it on your own computer (Windows commands; on macOS/Linux use python3.12 and .venv/bin/)
  1. Install Python 3.12.
  2. Open a terminal in the source/ folder.
  3. py -3.12 -m venv .venv
  4. .venv\Scripts\pip install -r requirements.txt
  5. .venv\Scripts\streamlit run app.py
  6. The dashboard opens at http://localhost:8501 (open it by hand if the browser does not start).
  Optional checks: .venv\Scripts\pip install -r requirements-dev.txt, then .venv\Scripts\python -m pytest tests
  Rebuilding data/processed from the raw downloads is not needed to run the app; the scripts and their order are
  listed in source/CLAUDE.md ("Pipeline") and the sources in source/data/README.md.


5.3 REQUIREMENTS
----------------
  - An internet connection. The 3D map streams elevation and satellite tiles and a basemap from public servers
    while you use it. If part of the 3D map stays dark, wait a few seconds or reload, or use "Need score blocks".
    On phones the map opens in the lighter "Need score blocks" view.
  - Hosted app asleep: Streamlit Community Cloud puts apps to sleep when unused. If you see "This app has gone to
    sleep", click "Yes, get this app back up!" and wait about 30-60 seconds.
  - Local run: Python 3.12 and disk space for the Python packages; a normal laptop is enough.


5.4 LIMITATIONS AND ASSUMPTIONS
-------------------------------
  - Two different indicators: network coverage of populated areas (99.71%, mainly outdoor, as stated by the Minister
    of Communications) and DOSM household internet access measure different things. We show them side by side and
    never subtract them into a "gap".
  - Proxies: "fixed network nearby", mobile signal quality and the schools screen come from where people ran
    Ookla speed tests, not from operator coverage maps. Many test tiles hold only a few tests. Terrain is a mean slope
    from a ~38 m elevation model; road distance is straight-line to the nearest mapped road (rivers not counted).
  - Estimates: costs, people without home internet per settlement, settlement types, people reached per RM1m and
    school flags are our estimates (labelled Indicative or Low confidence). Each rural MOE school stands for one settlement, and a district's rural
    households are split equally across its rural schools.
  - Costs only where a public unit cost was found (tower, satellite, a retail FWA plan). Take-up support, small cells,
    community Wi-Fi and microwave links are "not costed (no public cost source)", so costs are never added up across
    settlement types. The tower-vs-satellite total is a reference: the cost if every settlement without a nearby
    network were served by towers or satellite only.
  - The schools screen is low confidence: against Parliament's figures it is off by a large margin at state level
    (the error is shown on the Schools and Method pages). It is a screening list, not a count of schools without fibre.
  - Small samples: some districts' DOSM figures rest on small samples; they are flagged as low confidence and every
    rank is shown with a range.
  - Not available: no tower locations, no fibre routes and no indoor signal data are public, so the dashboard
    cannot model line-of-sight or indoor connectivity. The 3D terrain is context only.
  - Data years differ: DOSM ICTHS 2021-2025, Ookla 2026 Q3, MOE school list June 2022, Census 2020,
    OpenStreetMap Nov 2026, Hansard 11 Nov 2026 (every page footer lists them).
  - Licences: Ookla open data and EOxCloudless imagery are CC BY-NC-SA 4.0 (non-commercial use only); OpenStreetMap
    data is ODbL (district boundaries in Sarawak, roads); OpenDOSM data is CC BY 4.0. Only aggregated public data are
    used; there is no personal data.
  - Expert input: the settlement types and the "mainly outdoor" wording follow expert feedback from a telecom
    industry expert (Nov 2026). Candidate technologies are a screening list, not a recommendation; a site survey decides.
