Beyond Coverage: Connectivity Intelligence Malaysia

MDIT 2026 Datathon entry. Submission deadline: 29 Nov 2026 (dashboard link + report + video). Full team plan: https://claude.ai/artifact/GcM5gN8sHf8mHFSRQcLftH

What we are building

A Streamlit dashboard that finds rural communities that are "covered" on paper but not truly connected, and ranks where connectivity investment should go first, which fix fits (fibre, tower, satellite), and at roughly what cost. Users: MCMC (JENDELA), Ministry of Communications, Ministry of Education, Sarawak/Sabah state governments. SDG 9.c (main), SDG 4.a and 4.4 (second).

Key contrast: official coverage 99.71% of populated areas vs DOSM household access 90.7% rural (2025), and 1,180 of 5,362 schools in six states without fibre (Hansard, Dewan Rakyat, 11 Nov 2026; Sarawak 759).

Scope (Option C)
Layer	Geography
National overview	All 16 states and territories
Validation	6 Hansard states: Kelantan, Terengganu, Pahang, Kedah, Sabah, Sarawak
Deep dive (district map, rankings, fixes, simulator)	Sarawak; Sabah only if time allows
Hard rules
Never hardcode a statistic. Every number shown in the app or report is read from a file in data/. The only typed constants allowed are the cited headline figures above, kept in config/facts.yaml with their source URL.
Never invent or estimate missing data. If a download fails or a value is missing, stop and say so.
Keep raw downloads untouched in data/raw/. Cleaned outputs go to data/processed/, produced only by scripts in scripts/. Anyone must be able to rerun the pipeline from raw to processed.
Every dataset gets a short note in data/README.md: source, URL, date downloaded, licence, caveats.
Aggregated public data only. No personal data.
Label every estimate as an estimate (costs, weak-school flags, line-of-sight coverage).
Data

Full per-file notes (source, URL, licence, units, caveats): data/README.md.

Environment: Python 3.12 venv in .venv (py -3.12 -m venv .venv; pip install -r requirements.txt). Run scripts with .venv\Scripts\python.

Pipeline (rerun in order):
scripts/download_raw.py      downloads + validates all raw files except Ookla; skips existing ones (--force to re-download)
scripts/extract_t3.py        ICTHS Table 3 -> data/processed/ + district_aliases.csv, then runs the 2024 checks (exits non-zero on failure)
scripts/build_boundaries.py  -> data/processed/districts.geojson (needs district_aliases.csv from extract_t3.py)
scripts/download_ookla.py    latest Ookla quarter (fixed + mobile) -> data/raw/ookla/ (gitignored, ~550 MB) -> ookla_my_{type}_{y}q{q}.parquet
scripts/build_ookla.py       tiles -> districts -> ookla_district_{y}q{q}.csv (needs districts.geojson)
scripts/build_schools.py     MOE schools (6 Hansard states) + Ookla -> schools_connectivity.csv, prints Hansard validation
scripts/build_index.py       CGI per district (weights from config/weights.yaml) -> gap_index_districts.csv + gap_index_sensitivity.csv
scripts/extract_t1_t6.py     ICTHS Table 1.2 + Tables 6.4-6.6 -> dosm_hh_internet_state.csv, dosm_hh_internet_trend.csv
scripts/build_app_data.py    hansard_schools.csv, schools_all.csv, amenities_district.csv (needs districts.geojson)
scripts/build_costing.py     fix per rural-school cluster + 5-yr cost + estimated beneficiaries per RM1m (config/costs.yaml) -> costing_clusters.csv + costing_districts.csv (needs gap_index_districts.csv)

In data/raw/ (downloaded 2026-11-19, untouched):

OpenDOSM / data.gov.my Parquet (CC BY 4.0): hh_access_internet (households, state), icths_internet_strata (individuals, state), hh_access_amenities, hh_income_district (RM/month), population_district (thousands of people), schools_district, teachers_district, enrolment_school_district (the three MOE files are hosted on storage.data.gov.my)
hansard_schools_2026-11-11.csv: schools without fibre in the 6 states, from Hansard DR 11.11.2026 p.33 (official PDF; Bernama omits Sarawak's 52%). Per-state totals are derived from rounded % (marked, with min/max); only the 5,362 / 1,180 totals are exact.
moe/senarai_sekolah_rendah_menengah_jun2022.xlsx: MOE list of all 10,230 government + aided schools as at 30 Jun 2022 (newest MOE publishes), WITH coordinates (KOORDINATXX = lon, KOORDINATYY = lat), so no geocoding. 6 Hansard states: 5,349 schools vs Parliament's 5,362 (-0.2%).
boundaries/: DOSM district polygons (2022, DOSM Open Data Licence) and an OpenStreetMap Sarawak snapshot (ODbL)
census/census_district.csv: DOSM Census by district 1970-2020 (household_size_avg, rural population in column density_rural, area); 160 districts in 2020
DOSM ICTHS report tables, 2024 and 2025: icths_{year}_table{1,2,3,6,7}.xlsx. Table 1 (1.2 mobile vs fixed broadband), 2 (2.4/2.5 ICT skills), 3 (by district), 6 (time series: 2024 file = 2021-2024, 2025 file = 2022-2025), 7 (relative standard errors, national/urban/rural only). Licence not stated on DOSM release pages. Only Table 3 is cleaned so far.

In data/processed/ (written by extract_t3.py):

dosm_hh_ict_district_{2024,2025}.csv: household ICT access, Table 3.1 (178 rows: 162 districts, 13 states, 3 territories; 7 indicators)
dosm_ind_ict_district_{2024,2025}.csv: individual ICT use, Table 3.2 (172 rows; DOSM omits Membakut, Gedong, Lingga, Pantu, Sebuyau, Siburan)
dosm_hh_internet_district_2024_2025.csv: household internet both years, 165 rows all matched, with change and change_beyond_noise
district_aliases.csv: 14 spelling-only aliases (incl. Census "Larut dan Matang") -> Table 3 (2025) spelling (Seberang Prai/S.P.->Seberang Perai, Ulu->Hulu, Kecil Lojing->Lojing, Meradong->Maradong, Larut & Matang, Lubok antu, Terengganu "Hulu"). Apply before joining anything to the Table 3 files.
districts.geojson: 164 polygons named like Table 3. DOSM 2022 polygons everywhere except Sarawak, which uses OSM (has the new districts Gedong, Lingga, Pantu, Sebuyau). ODbL because of the OSM part. Join on dosm_district (Perlis links to its state row). Siburan and Membakut have no polygon anywhere: table only; their area sits inside Kuching and Beaufort (contains_unmapped column).
Naming follows OpenDOSM: title-case states, territories as "W.P. Kuala Lumpur" (state = district), state rows have district "All Districts".
Columns include small_sample_flag, implied_sample_n (call it "inferred sample size"), internet_moe95_pp (call it "approximate margin of error (simple random-sampling formula)"); both are our estimates from the published percentages, never DOSM figures (method in data/README.md). Districts with small_sample_flag = True must be shown as low confidence with these, never ranked as precise. No flagged district's 2024->2025 change exceeds its MOE (change_beyond_noise is False for all 31), so don't present those changes as real trends.

ookla_my_{fixed,mobile}_2026q3.parquet: Ookla tiles clipped to Malaysia's bbox (CC BY-NC-SA 4.0, non-commercial)
ookla_district_2026q3.csv: per district x type: dl_mbps, ul_mbps (test-weighted mean), latency_median_ms (test-weighted median), n_tiles, tests, devices (upper bound), low_sample (tests < 50). Fixed-speed tests only come from homes that already have fixed broadband: always read speed together with DOSM access.

schools_connectivity.csv: 5,349 schools in the 6 states with district, fixed tiles/tests within 1 and 2 km, nearest fixed tile, mobile tests + speed within 2 km, likely_no_fibre (no fixed tile within 2 km; _1km variant), confidence (mobile tests within 2 km: high >=100, medium 20-99, low <20). ESTIMATE: validation vs Hansard is poor at state level (2 km: 786 vs 1,180, -33%; 1 km total -1.9% only by offsetting errors, e.g. Terengganu 83 vs 4). Present flags as a low-confidence screening list, always with the state-level error; never as a count of schools without fibre.

gap_index_districts.csv: 164 districts (Siburan, Membakut not indexed: no Ookla). CGI from access_gap (2025), mobile_speed + fixed_reach (Ookla 2026Q3, fixed_reach is a PROXY), low_income (2024; 2022 for Perlis + territories); ranks national + Sarawak with Dirichlet p05-p95; people_without_home_internet (ESTIMATE, household rate applied to individuals); students from MOE school list 2022 (enrolment file is by PPD, not district). gap_index_sensitivity.csv: equal weights, 1,000 Dirichlet runs, MOE rank range for small-sample districts. Only Sarawak's top 3 (Kanowit, Song, Tebedu) are stable; always show rank ranges.

costing_clusters.csv / costing_districts.csv (ESTIMATES; method in docs/costing_method.md): one settlement per rural MOE school; households = Census 2020 rural households / rural schools (4 new Sarawak districts: parent values, split by 2026 population). Settlements with any Ookla fixed tile within 2 km = 'fixed network likely nearby: take-up gap' (PROXY): NO infrastructure cost, reported per district (80% of settlements, ~468k people); costed as fibre PoPs only in the upper bound. Others: tower if UNCONNECTED households (households x access gap, the ones the costs pay for) >= break-even (144.1 Residential / 228.3 Lite), else satellite: 7 towers, 859 satellite, none in Sarawak. Sensitivity rule_all_hh keeps the earlier all-households test (804 tower). Totals: main RM0.44bn (Sarawak 0.26), Lite 0.29 (0.17), upper bound 5.51 (1.41), rule_all_hh 1.73 (0.82). Main metric = ESTIMATED BENEFICIARIES PER RM1m (rural people without home internet in planned settlements per RM1m; never call it 'value'); whole-district per RM1m is secondary; students per RM1m separate. Take-up wording: 'Our proxy suggests many rural settlements already have a fixed network nearby, so take-up support may matter as much as new infrastructure.' Always show the cost-screen caveat (equal households per rural school; towers and satellite are different services; not a full cost-benefit comparison). Never present solar-hybrid or fibre extension as recommendations; fibre PoPs are an upper-bound cost sensitivity only. JENDELA's ~80 residents/site is far below break-even: present the rule as a cost screen.

All planned raw data is collected.

Method
Clean and merge by state and district.
Schools come with MOE coordinates (no geocoding); attach Ookla speeds from tiles within 1-2 km.
Flag "likely weak" schools: speeds far below fibre level (300-800 Mbps) or almost no tests nearby; add a confidence level.
Validate: sum flags per state, compare with the six Hansard totals; report the error.
Connectivity Gap Index per district: CGI_d = sum_i(w_i * S_di), min-max normalised indicators (district household access gap, speed gap, share of likely weak schools, population affected, low income). Weights documented in config/weights.yaml; include a sensitivity check.
Two rankings: need (CGI) and value (people and students helped per estimated RM).
Rule-based fix recommender; costs from cited sources in config/costs.yaml.
App structure (Streamlit)

User journey: national overview -> six Hansard states and validation -> Sarawak -> pick a district -> problems -> recommended fix, cost, beneficiaries -> priority on both rankings.

Pages (built; app.py uses st.navigation; page files live in views/, NOT pages/, because a pages/ folder makes Streamlit also load them as an old-style multipage app that bypasses app.py): 1 Overview (coverage 99.71% from config/facts.yaml vs DOSM household access, urban/rural, rural mobile vs fixed broadband, 2021-2025 trend), 2 Schools (Hansard by state, MOE school map, low-confidence screening layer + validation table), 3 Sarawak map (pydeck 3D, height = CGI, colour = largest settlement group or main fix, small-sample outlines, Siburan listed as no boundary), 4 District detail, 5 Priorities (need vs value scatter, rank ranges, Residential/Lite toggle), 6 Method & limitations. Optional bonus: Tower Simulator, only if time allows.
Design: every page calls st.set_page_config(layout="wide"). app_utils/ui.py holds the palette (one accent #2a78d6, muted greys; fix colours tower #1c5cab / satellite #eb6834 / take-up gap #58b98c, validated all-pairs) and the shared wording (BENEFIT, INFERRED_N, MOE_TXT, TAKEUP_TXT, COST_SCREEN), what(text, data=...) captions under every chart and table with the data year (e.g. 'DOSM ICTHS 2025 · Ookla 2026Q3'), footer() sources on every page, OSM credit where Sarawak boundaries or basemaps appear. app_utils/data.py reads data/processed and config only, via st.cache_data. Pages must not contain typed statistics.
Run locally: .venv\Scripts\streamlit run app.py. Headless check: streamlit.testing.v1.AppTest per page; visual check: screenshots at 1366 px and ~480 px. Scripts share defensive checks in scripts/_checks.py (missing files, empty Ookla, coordinates, unmatched districts).

Repo layout
app.py              Streamlit entry (st.navigation)
app_utils/          data.py (cached loaders), ui.py (palette, chart style, captions, footers)
views/              one file per page (not pages/: see above)
.streamlit/         config.toml (theme)
scripts/            download and cleaning scripts
config/             facts.yaml, weights.yaml, costs.yaml
data/raw/           untouched downloads
data/processed/     cleaned outputs
requirements.txt    pinned: streamlit, pandas, geopandas, pydeck, plotly, pyarrow, openpyxl
Checks before saying a task is done
Run the script or streamlit run app.py and confirm it works.
Spot-check 3 numbers in the output against the original source.
The app must deploy on Streamlit Community Cloud and run on a normal laptop.