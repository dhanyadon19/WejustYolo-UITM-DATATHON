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

In data/raw/ (downloaded 2026-11-19, untouched):

OpenDOSM / data.gov.my Parquet (CC BY 4.0): hh_access_internet (households, state), icths_internet_strata (individuals, state), hh_access_amenities, hh_income_district (RM/month), population_district (thousands of people), schools_district, teachers_district, enrolment_school_district (the three MOE files are hosted on storage.data.gov.my)
hansard_schools_2026-11-11.csv: schools without fibre in the 6 states, from Hansard DR 11.11.2026 p.33 (official PDF; Bernama omits Sarawak's 52%). Per-state totals are derived from rounded % (marked, with min/max); only the 5,362 / 1,180 totals are exact.
moe/senarai_sekolah_rendah_menengah_jun2022.xlsx: MOE list of all 10,230 government + aided schools as at 30 Jun 2022 (newest MOE publishes), WITH coordinates (KOORDINATXX = lon, KOORDINATYY = lat), so no geocoding. 6 Hansard states: 5,349 schools vs Parliament's 5,362 (-0.2%).
boundaries/: DOSM district polygons (2022, DOSM Open Data Licence) and an OpenStreetMap Sarawak snapshot (ODbL)
DOSM ICTHS report tables, 2024 and 2025: icths_{year}_table{1,2,3,6,7}.xlsx. Table 1 (1.2 mobile vs fixed broadband), 2 (2.4/2.5 ICT skills), 3 (by district), 6 (time series: 2024 file = 2021-2024, 2025 file = 2022-2025), 7 (relative standard errors, national/urban/rural only). Licence not stated on DOSM release pages. Only Table 3 is cleaned so far.

In data/processed/ (written by extract_t3.py):

dosm_hh_ict_district_{2024,2025}.csv: household ICT access, Table 3.1 (178 rows: 162 districts, 13 states, 3 territories; 7 indicators)
dosm_ind_ict_district_{2024,2025}.csv: individual ICT use, Table 3.2 (172 rows; DOSM omits Membakut, Gedong, Lingga, Pantu, Sebuyau, Siburan)
dosm_hh_internet_district_2024_2025.csv: household internet both years, 165 rows all matched, with change and change_beyond_noise
district_aliases.csv: spelling-only aliases -> Table 3 (2025) spelling (Seberang Prai->Perai, Ulu Langat/Selangor->Hulu, Kecil Lojing->Lojing, Meradong->Maradong). Apply before joining anything to the Table 3 files.
districts.geojson: 164 polygons named like Table 3. DOSM 2022 polygons everywhere except Sarawak, which uses OSM (has the new districts Gedong, Lingga, Pantu, Sebuyau). ODbL because of the OSM part. Join on dosm_district (Perlis links to its state row). Siburan and Membakut have no polygon anywhere: table only; their area sits inside Kuching and Beaufort (contains_unmapped column).
Naming follows OpenDOSM: title-case states, territories as "W.P. Kuala Lumpur" (state = district), state rows have district "All Districts".
Columns include small_sample_flag, implied_sample_n, internet_moe95_pp (inferred from the published percentages; method in data/README.md). Districts with small_sample_flag = True must be shown as low confidence with their margin of error, never ranked as precise. No flagged district's 2024->2025 change exceeds its MOE (change_beyond_noise is False for all 31), so don't present those changes as real trends.

ookla_my_{fixed,mobile}_2026q3.parquet: Ookla tiles clipped to Malaysia's bbox (CC BY-NC-SA 4.0, non-commercial)
ookla_district_2026q3.csv: per district x type: dl_mbps, ul_mbps (test-weighted mean), latency_median_ms (test-weighted median), n_tiles, tests, devices (upper bound), low_sample (tests < 50). Fixed-speed tests only come from homes that already have fixed broadband: always read speed together with DOSM access.

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

Pages: 1 National Overview, 2 Validation, 3 Sarawak Gap Map (pydeck 3D, height = CGI), 4 Prioritisation (need vs value scatter), 5 Fix Recommender, 6 Tower Simulator (bonus, one area, only if pages 1-5 are done by 26 Nov).

Repo layout
app.py              Streamlit entry
pages/              one file per page
scripts/            download and cleaning scripts
config/             facts.yaml, weights.yaml, costs.yaml
data/raw/           untouched downloads
data/processed/     cleaned outputs
requirements.txt    pinned: streamlit, pandas, geopandas, pydeck, plotly, pyarrow, openpyxl
Checks before saying a task is done
Run the script or streamlit run app.py and confirm it works.
Spot-check 3 numbers in the output against the original source.
The app must deploy on Streamlit Community Cloud and run on a normal laptop.