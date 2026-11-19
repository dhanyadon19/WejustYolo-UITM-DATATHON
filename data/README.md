# Data

All raw files are in `data/raw/` and are never edited. Rebuild everything from scratch with:

```
py -3.12 -m venv .venv && .venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python scripts\download_raw.py      # downloads + validates; --force to re-download
.venv\Scripts\python scripts\extract_t3.py        # Table 3 -> data/processed/, runs checks
```

**Date downloaded:** 2026-11-19 for all raw files.
**Units:** unless stated otherwise, ICT indicators are **percentages (0–100)**.

---

## Raw: OpenDOSM / data.gov.my Parquet

Licence for all eight: **CC BY 4.0**, as stated on each catalogue page. Cite "Department of Statistics Malaysia (OpenDOSM)" or "Ministry of Education Malaysia (data.gov.my)" respectively.
Dates are `YYYY-01-01` (annual data).

| File | Source / catalogue page | Download URL | Columns | Units & caveats |
|---|---|---|---|---|
| `hh_access_internet.parquet` | DOSM ICTHS, [open.dosm.gov.my/data-catalogue/hh_access_internet](https://open.dosm.gov.my/data-catalogue/hh_access_internet) | https://storage.dosm.gov.my/icths/hh_access_internet.parquet | date, state, strata, proportion | % of **households** with Internet access. State level only; strata = overall/urban/rural. |
| `icths_internet_strata.parquet` | DOSM ICTHS, [open.dosm.gov.my/data-catalogue/icths_internet_strata](https://open.dosm.gov.my/data-catalogue/icths_internet_strata) | https://storage.dosm.gov.my/icths/icths_internet_strata.parquet | date, state, strata, proportion | % of **individuals** using the Internet (not households, so don't mix it with the file above). State level only. |
| `hh_access_amenities.parquet` | DOSM HIES, [open.dosm.gov.my/data-catalogue/hh_access_amenities](https://open.dosm.gov.my/data-catalogue/hh_access_amenities) | https://storage.dosm.gov.my/hies/hh_access_amenities.parquet | date, state, district, piped_water, sanitation, electricity | % of households. Survey years only (2016, 2019, 2022, 2024). State rows have district = "All Districts". |
| `hh_income_district.parquet` | DOSM HIES, [open.dosm.gov.my/data-catalogue/hh_income_district](https://open.dosm.gov.my/data-catalogue/hh_income_district) | https://storage.dosm.gov.my/hies/hh_income_district.parquet | state, district, date, income_mean, income_median | **RM per month**, gross household income (integer). Survey years 2019, 2022, 2024. |
| `population_district.parquet` | DOSM, [open.dosm.gov.my/data-catalogue/population_district](https://open.dosm.gov.my/data-catalogue/population_district) | https://storage.dosm.gov.my/population/population_district.parquet | state, district, date, sex, age, ethnicity, population | **Thousands of people ('000)**, e.g. 495.3 = 495,300. Breakdowns by sex/age/ethnicity; use `sex="both", age="overall", ethnicity="overall"` for totals. |
| `schools_district.parquet` | MOE, [data.gov.my/data-catalogue/schools_district](https://data.gov.my/data-catalogue/schools_district) | https://storage.data.gov.my/education/schools_district.parquet | state, district, stage, type, date, schools | Count of public schools/institutions. Listed in the OpenDOSM catalogue but hosted on data.gov.my storage. Includes "Malaysia / All Districts" totals; don't double-count them. |
| `teachers_district.parquet` | MOE, [data.gov.my/data-catalogue/teachers_district](https://data.gov.my/data-catalogue/teachers_district) | https://storage.data.gov.my/education/teachers_district.parquet | state, district, stage, sex, date, teachers | Count of teachers. Includes national and state totals. |
| `enrolment_school_district.parquet` | MOE, [data.gov.my/data-catalogue/enrolment_school_district](https://data.gov.my/data-catalogue/enrolment_school_district) | https://storage.data.gov.my/education/enrolment_school_district.parquet | state, district, stage, sex, date, students | Count of students enrolled; stage = primary / secondary / post-secondary (Form 6). Includes national and state totals. |

OpenDOSM names the federal territories `W.P. Kuala Lumpur`, `W.P. Labuan` and `W.P. Putrajaya`, using the same name for both state and district.

## Raw: DOSM ICT Use and Access by Individuals and Households Survey (ICTHS) report tables

- **Source:** Department of Statistics Malaysia, *ICT Use and Access by Individuals and Households Survey Report*.
- **Release pages:**
  - 2024: https://www.dosm.gov.my/portal-main/release-content/ict-use-and-access-by-individuals-and-households-survey-report-2024
  - 2025: https://www.dosm.gov.my/portal-main/release-content/ict-use-and-access-by-individuals-and-households-survey-report-2025
- **Download URL pattern:** `https://www.dosm.gov.my/portal-main/release-document-log?release_document_id=<id>` (redirects to the .xlsx).
- **Licence:** **not stated** on the release pages; the site links only a general [disclaimer](https://www.dosm.gov.my/portal-main/article/disclaimer). We treat it as © DOSM, cite DOSM as the source, and redistribute only aggregated figures derived from it.
- **Format caveats:** headers are two-language (Malay/English) and spread over several merged rows, so parse them by position. Values are unrounded floats, except older years in Table 6, which are rounded to one decimal.

| File | doc id | Content | Notes |
|---|---|---|---|
| `icths_2024_table1.xlsx` / `icths_2025_table1.xlsx` | 13942 / 19016 | Table 1: ICT access by households, by state × urban/rural. Sheets 1.1, **1.2 (Internet, mobile broadband, fixed broadband)**, 1.3a, 1.3b | % of households |
| `icths_2024_table2.xlsx` / `icths_2025_table2.xlsx` | 13943 / 19017 | Table 2: ICT use by individuals, 36 sheets incl. **2.4 (ICT skills, individuals)** and **2.5 (ICT skills, youth)** | % of individuals |
| `icths_2024_table3.xlsx` / `icths_2025_table3.xlsx` | 13949 / 19018 | Table 3: ICT access (3.1, households) and use (3.2, individuals) **by administrative district** | Processed by `scripts/extract_t3.py`, see below |
| `icths_2024_table6.xlsx` / `icths_2025_table6.xlsx` | 13947 / 19021 | Table 6: time series, 4 years per edition | 2024 file covers 2021–2024; 2025 file covers 2022–2025. Older years are rounded to one decimal. |
| `icths_2024_table7.xlsx` / `icths_2025_table7.xlsx` | 13948 / 19022 | Table 7: relative standard errors (7.1 household access, 7.2 individual use), with SE and 95% CI | National and urban/rural only, not district |

## Raw: Hansard, schools without fibre (`hansard_schools_2026-11-11.csv`)

| | |
|---|---|
| Source | **Hansard, Dewan Rakyat, 11 Nov 2026**, oral question 11 from Nurul Amin Hamid [Padang Terap], answered by Deputy Education Minister Wong Kah Woh. Corrected edition `DR-11112026 - pembetulan Tumpat.pdf`, **printed page 33 (PDF page 39)**. |
| URL | https://www.parlimen.gov.my/files/hindex/pdf/DR-11112026%20-%20pembetulan%20Tumpat.pdf (linked from the [Dewan Rakyat Hansard index](https://www.parlimen.gov.my/hansard-dewan-rakyat.html?uweb=dr&lang=bm)). A copy is at `data/raw/hansard/DR-11112026_pembetulan_Tumpat.pdf`, gitignored and re-downloaded by `download_raw.py`. |
| Secondary source | Bernama, 11 Nov 2026, https://bernama.com/en/news.php?id=2632735. Its figures match the Hansard, but it **omits Sarawak's 52%**. It also describes the answer as given in the question-and-answer session, i.e. an oral reply, not a written one. |
| Transcribed | 2026-11-19, by hand from the Hansard text |
| Licence | Parliamentary record; public. Cite as Hansard DR 11.11.2026, p.33. |

**Columns**

| Column | Meaning |
|---|---|
| `schools_without_fibre`, `pct_without_fibre` | As stated in the Hansard. The six counts sum to the stated 1,180. |
| `schools_total` | For each state, **derived** as count ÷ percentage × 100, rounded half-up. Marked by `schools_total_derived = True`. The "Total (6 states)" row (5,362 schools, 1,180 without fibre, 22%) is stated, not derived. |
| `schools_total_min` / `_max` | The range each derived total could fall in, because the Hansard rounds percentages to whole numbers (p ± 0.5). Small counts give wide ranges: Terengganu (4 schools, "1%") is 267–800, Kedah (14, "2%") is 560–933. |

**Caveats**
- **Derived totals don't add up exactly:** they sum to **5,141**, against the stated 5,362 (−221, −4.1%). The gap comes from the rounded percentages and is within their combined range (4,763–5,887). So use the per-state totals only as approximations; the 5,362 total is the exact figure.
- **What "without fibre" means:** the Hansard says these 1,180 schools have **wireless broadband or satellite** instead of fibre, so they are not offline. The 4,182 with fibre get 300–800 Mbps.

## Raw: MOE school list (`moe/senarai_sekolah_rendah_menengah_jun2022.xlsx`)

| | |
|---|---|
| Source | Ministry of Education (KPM), *Senarai Sekolah Rendah dan Menengah Jun 2022*: government (`BANTUAN = SK`) and government-aided (`SBK`) primary and secondary schools. **Data as at 30 Jun 2022** (stated in row 1). |
| Where | MOE download area https://www.moe.gov.my/muatturun → folder `laporan_dan_statistik/senarai_sekolah`. The direct link is in `download_raw.py`; it goes through the site's file-browser connector. |
| Why this file | It's the **newest complete list MOE publishes.** Searches of moe.gov.my, data.gov.my and the data.gov.my archive found nothing newer; the archive has only partial or state-level lists. |
| Downloaded | 2026-11-19 |
| Licence | Not stated on the MOE download page. It's a public government publication; cite KPM. |
| Contents | 10,230 schools (7,778 primary, 2,452 secondary), one sheet. A title row comes first, so the header is row 2. Columns include NEGERI, PPD, PERINGKAT, JENIS/LABEL, KODSEKOLAH, NAMASEKOLAH, address, LOKASI (Bandar/Luar Bandar), BANTUAN, MURID, GURU, and **KOORDINATXX (longitude) / KOORDINATYY (latitude)**. It also has school phone numbers and @moe.edu.my emails, which are institutional, not personal; we don't use them. |

**Coordinates are included, so no geocoding was done.** Part 3 of the plan (Nominatim/OSM geocoding) was skipped.

**Sanity check against Parliament**

| | Count |
|---|---|
| Schools in the 6 Hansard states (MOE list, Jun 2022) | **5,349** |
| Parliament (Hansard 11.11.2026) | 5,362 |
| Difference | **−13 (−0.2%)** |

| State | MOE Jun 2022 | Hansard-derived total (range) |
|---|---|---|
| Sarawak | 1,458 | 1,460 (1,446–1,473) |
| Sabah | 1,296 | 1,264 (1,221–1,311) |
| Pahang | 741 | 754 (739–770) |
| Kelantan | 596 | 563 (530–600) |
| Kedah | 752 | 700 (560–933) |
| Terengganu | 506 | 400 (267–800) |

Every state's MOE count falls inside the range implied by the Hansard's rounded percentages.

**Caveats**
- **The list is 4 years older than the Hansard figures,** so schools opened or closed since mid-2022 are missing or still listed.
- **Coordinate problems in the 6 states (5,349 schools):**
  - 4 schools have no coordinates.
  - 61 fall outside every district polygon, mostly on islands and the coast, which the simplified polygons cut off.
  - 7 fall inside a polygon of a different state. Six of those are near the Kedah–Penang and Pahang–Johor borders; one Pahang school (SJK(C) Poay Chai) plots in Kedah, which is probably a coordinate error.
  - `build_schools.py` flags all of these rather than dropping them.

## Raw: district boundaries (`data/raw/boundaries/`)

Downloaded 2026-11-19 by `download_raw.py`.

| File | Source | Licence | Data date | Notes |
|---|---|---|---|---|
| `dosm_administrative_2_district.geojson` | DOSM, [github.com/dosm-malaysia/data-open](https://github.com/dosm-malaysia/data-open/blob/main/datasets/geodata/administrative_2_district.geojson) | DOSM Open Data Licence (repo `LICENSE.md`: copying, adaptation and commercial use allowed) | last commit 2022-06-22 | 160 polygons, EPSG:4326, simplified for web maps. 7 polygons are invalid as published (repaired in processing). It predates 6 newer districts (see below). |
| `dosm_state_district.csv` | same repo | same | 2022 | State/district codes for the polygons above. |
| `osm_sarawak_admin6.json` | OpenStreetMap via the Overpass API (relations with `admin_level=6` in Sarawak, with geometry) | **ODbL 1.0**, © OpenStreetMap contributors | live OSM snapshot, 2026-11-19 | 44 Sarawak districts, including the newer Gedong, Lingga, Pantu and Sebuyau. Community-maintained, not official; only Gedong cites a source (Samarahan Division website). |
| `osm_new_district_towns.json` | OpenStreetMap via Overpass (`place=town` nodes named Siburan, Membakut) | ODbL 1.0 | 2026-11-19 | Town points only, used to record which polygon contains each of the two districts that have no boundary. |

**Why these sources.** Candidates were compared against the 165 DOSM Table 3 districts and territories:

| Candidate | Licence | Year | Polygons | Exact name matches |
|---|---|---|---|---|
| DOSM data-open (chosen) | DOSM Open Data Licence | 2022 | 160 | 156 |
| geoBoundaries gbOpen ADM2 | CC BY 3.0 | 2020 | 159 | 149 (no state field) |
| GADM 4.1 | non-commercial only, no redistribution | 2022 | 144 | 91 |
| HDX COD-AB Malaysia (UNHCR) | CC BY-IGO | 2021 (reviewed 2025) | 144 | derived from GADM, so not used |

The site-wide catalogue pages of OpenDOSM and data.gov.my list no boundary dataset. The DOSM GitHub repo above is the official source.

## Raw: Ookla performance tiles (`data/raw/ookla/`, gitignored)

| | |
|---|---|
| Source | Ookla for Good Open Data, *Speedtest by Ookla Global Fixed and Mobile Network Performance Maps*, public AWS bucket `s3://ookla-open-data` (read over HTTPS, no credentials) |
| Files | `2026-07-01_performance_fixed_tiles.parquet` (365 MB), `2026-07-01_performance_mobile_tiles.parquet` (190 MB), global |
| URLs | https://ookla-open-data.s3.amazonaws.com/parquet/performance/type={fixed,mobile}/year=2026/quarter=3/2026-07-01_performance_{fixed,mobile}_tiles.parquet |
| Quarter | **2026 Q3** (Jul–Sep 2026), the latest available for both types, published 2026-10-09 |
| Downloaded | 2026-11-19 by `scripts/download_ookla.py` (rerun it to fetch again; the files are too big for git) |
| Licence | **CC BY-NC-SA 4.0**: attribution required, **non-commercial use only**, and derived data must be shared under the same licence |
| Units | `avg_d_kbps`, `avg_u_kbps` in kilobits per second; `avg_lat_ms` in milliseconds; `tests` and `devices` are counts per tile |

## Processed: Ookla (from `download_ookla.py` and `build_ookla.py`), CC BY-NC-SA 4.0

**`ookla_my_{fixed,mobile}_2026q3.parquet`**: the global tiles clipped to a Malaysia bounding box.
- **Box:** taken from the DOSM boundary file, plus 0.1°.
- **Size:** 55,381 fixed and 70,503 mobile tiles.
- **Columns:** the same as Ookla's.
- **Coverage:** the box also covers parts of Brunei, Singapore, southern Thailand and Kalimantan.

**`ookla_district_2026q3.csv`**: 328 rows (164 polygons × fixed/mobile). Columns:

| Column | Meaning |
|---|---|
| year, quarter, type | |
| state, district, dosm_district, boundary_source, contains_unmapped | from `districts.geojson` |
| n_tiles | number of tiles |
| tests | total tests |
| devices | total devices; an **upper bound**, since a device testing in several tiles is counted in each |
| dl_mbps, ul_mbps | test-weighted mean of tile download/upload speeds, in Mbps (kbps ÷ 1000) |
| latency_median_ms | test-weighted median of tile average latency (each test takes its tile's average, the finest detail Ookla publishes) |
| low_sample | tests < 50 |

**Method and caveats**
- **Assignment:** a tile (zoom 16, ~600 m) is assigned to the district polygon that contains its centre.
- **Tiles dropped:** 19,129 fixed and 15,870 mobile tiles in the box fall outside every polygon, almost all in neighbouring countries or at sea. Only 15 fixed and 30 mobile tiles (37 and 115 tests) fall inside DOSM's Malaysia outline but in the gap between the OSM and DOSM edges in Sarawak.
- **Edge overlaps:** the simplified DOSM 2022 polygons overlap by slivers along shared edges (mostly under 1 km²). A tile centre inside two polygons goes to the one it lies deepest inside; that affected 3 fixed and 4 mobile tiles this quarter.
- **Low samples:** 4 fixed districts have `low_sample`: Lingga (13 tests), Pantu (15), Pakan (29) and Tebedu (36), all in Sarawak. Every polygon has at least one tile of each type.
- **Spot-check:** three districts were recomputed independently from the raw global files, using tile WKT centres. Tiles, tests and download speed matched exactly: Bukit Mabong fixed 85.09 Mbps from 222 tests; Subis mobile 53.48 Mbps from 1,035 tests; Kanowit fixed 205.97 Mbps from 106 tests.
- **Selection bias:** Speedtest data comes from user-run tests. Fixed results describe **households that already have fixed broadband**, so a high fixed speed doesn't mean good coverage. For example, Kanowit has the lowest household internet access in Sarawak (DOSM) but 206 Mbps fixed from just 106 tests. Read speed together with access, and treat test counts as a rough measure of reach, not of population.
- **Siburan and Membakut:** their tiles are counted under Kuching and Beaufort (see `contains_unmapped`).

## Processed: schools (from `scripts/build_schools.py`), an ESTIMATE

**`schools_connectivity.csv`**: 5,349 schools in Kelantan, Terengganu, Pahang, Kedah, Sabah and Sarawak (MOE list, Jun 2022), compared against Ookla 2026 Q3 tiles. Inherits CC BY-NC-SA 4.0 from Ookla.

| Column | Meaning |
|---|---|
| school_code … lon, lat | from the MOE list (`aid_status`: SK = government, SBK = government-aided) |
| district | polygon of the school's **own state** that contains it. If none does, the nearest own-state polygon within 5 km. |
| district_method | `within` (5,277), `nearest (x km)` (65), or blank (7) |
| coord_flag | `ok` 5,277 · `outside_polygons` 60 (mostly islands and coast) · `other_state` 5 (border slivers) · `missing` 4 · `suspect` 3 (no own-state polygon within 5 km: SK Bandar Baru Beris Jaya, Kedah; SJK(C) Poay Chai, Pahang, which plots in Kedah; SK Pulau Tigabu, Sabah) |
| fixed_tiles_1km / _2km, fixed_tests_1km / _2km | Ookla fixed tiles, and their tests, whose centre lies within 1 / 2 km of the school |
| nearest_fixed_tile_km | distance to the nearest fixed tile centre |
| mobile_tests_2km, mobile_dl_mbps_2km | mobile tests within 2 km, and their test-weighted mean download speed |
| likely_no_fibre | **True if no fixed tile within 2 km** (`likely_no_fibre_1km`: within 1 km). Blank for the 4 schools without coordinates. |
| confidence | from mobile tests within 2 km: **high ≥ 100, medium 20–99, low < 20**. Set in advance and not tuned. |

- **Distances** are measured in metres in each state's UTM zone, from the school to each tile's centre.
- **Spot-check:** three schools (YBB8311 Sarawak, KBA0006 Kedah, XBA6015 Sabah) were recomputed independently with haversine distances. Tile and test counts and mobile speed matched exactly; nearest distances agreed within 0.3% (UTM vs sphere).

**Validation against Parliament (Hansard 11 Nov 2026).** The thresholds were not tuned to match.

| State | MOE schools | Hansard: no fibre | Ours, 2 km | Diff | % diff | Ours, 1 km | Diff | % diff |
|---|---|---|---|---|---|---|---|---|
| Kelantan | 596 | 45 | 32 | −13 | −28.9% | 63 | +18 | +40.0% |
| Terengganu | 506 | 4 | 52 | +48 | +1200% | 83 | +79 | +1975% |
| Pahang | 741 | 181 | 116 | −65 | −35.9% | 172 | −9 | −5.0% |
| Kedah | 752 | 14 | 21 | +7 | +50.0% | 58 | +44 | +314% |
| Sabah | 1,296 | 177 | 122 | −55 | −31.1% | 195 | +18 | +10.2% |
| Sarawak | 1,458 | 759 | 443 | −316 | −41.6% | 587 | −172 | −22.7% |
| **Total** | **5,349** | **1,180** | **786** | **−394** | **−33.4%** | **1,158** | **−22** | **−1.9%** |

**How to read it**
- **2 km rule: misses about a third of Parliament's 1,180** overall, and under-counts in 4 of the 6 states. Sarawak, the deep-dive state, is short by 42%.
- **1 km rule: the near-match on the total (−1.9%) is a coincidence of offsetting errors,** not accuracy. It over-counts heavily where Parliament's numbers are tiny (Terengganu: 83 against 4; Kedah: 58 against 14) and still under-counts Sarawak by 23%.
- **Neither rule gets the states right.** Use the flags as a **screening list with low confidence**, not as a count. Report the state-level error alongside any map of flagged schools.
- **Confidence is mostly low:** of the 786 schools flagged at 2 km, 686 are low, 93 medium and 7 high. Places with no fixed tiles also have very few mobile tests, so the flag mostly rests on sparse data.

**Why the estimate is off (caveats)**
- **Ookla "fixed" tiles are home broadband tests by the public,** not school connections. A home with fibre near a school doesn't mean the school has fibre, so we under-count in rural Sarawak, Sabah and Pahang.
- **Fixed wireless and satellite home connections also appear as "fixed" tiles,** which pushes towards under-counting.
- **Dense areas over-count:** a school with fibre in a place where few people run home broadband tests gets flagged, which is likely why Terengganu and Kedah come out too high.
- **Dates differ:** the MOE list is from Jun 2022, Ookla from Jul–Sep 2026, and Hansard from Nov 2026.

## Processed: Connectivity Gap Index (from `scripts/build_index.py`)

Weights are in `config/weights.yaml`: access_gap 0.4, mobile_speed 0.2, fixed_reach 0.2, low_income 0.2, each with a one-line reason.

**`gap_index_districts.csv`**: 164 districts and territories, one row each.

| Indicator | Definition | Source and year | Direction |
|---|---|---|---|
| access_gap | 100 − household internet access % | ICTHS Table 3, **2025** | higher = worse |
| mobile_speed | Ookla mobile test-weighted download (Mbps) | Ookla **2026 Q3** | inverted |
| fixed_reach | Ookla fixed tests per 1,000 residents, a **PROXY** for fixed-broadband take-up, not coverage | Ookla 2026 Q3 ÷ population 2026 | inverted |
| low_income | median gross monthly household income (RM) | OpenDOSM HIES, **2024** (2022 for Perlis and the 3 territories, which have no 2024 district row) | inverted |

**How it's built**
- **Normalisation and score:** each indicator is min-max normalised across all 164 districts, so 1 = worst and 0 = best. `cgi = Σ weight × normalised indicator`.
- **Ranks:** `rank_national` and `rank_sarawak`, where 1 = worst. `rank_*_p05/_p95` give the 5th–95th percentile rank over the Dirichlet runs.
- **Years:** each row records the year used per source (`access_year`, `ookla_quarter`, `population_year`, `income_year`).
- **Not indexed:** **Siburan** and **Membakut** have no boundary, so no Ookla data. Their area and tests are counted under Kuching and Beaufort.
- **Perlis:** indexed as one district, using DOSM's Perlis state row for access.

**Beneficiaries (ESTIMATES)**
- **`people_without_home_internet`** = population (thousands × 1,000) × access_gap / 100. It **assumes individuals follow the household rate.**
- **`students`** = pupils (`MURID`) of MOE schools located in the district, from the **MOE school list of 30 Jun 2022**, not the latest year.
  - **Why not the enrolment file:** OpenDOSM/MOE `enrolment_school_district` (2025) is organised by education office (PPD). PPD areas don't match administrative districts: some are merged (Kulim/Bandar Baharu, Tatau/Sebauh), split (Kinta Utara/Selatan) or different (Padawan, Baram), so it can't be assigned to districts without merging or splitting.
  - **State-level cross-check:** the school list is within −5.7% to +3.2% of 2025 enrolment for every state except Labuan (−8.1%) and Putrajaya (−13.9%).
  - **Missing schools:** 18 schools with missing or suspect coordinates are not placed in any district.

## Processed: costing (from `scripts/build_costing.py`), ESTIMATES

The method, sources, sensitivity results and unsourced assumptions are in [`docs/costing_method.md`](../docs/costing_method.md). Costs come from `config/costs.yaml`.

| File | Rows | Content |
|---|---|---|
| `costing_clusters.csv` | 4,322 | One row per **rural MOE school** (settlement anchor): households, unconnected households and people, `hh_source`, fixed tiles within 2 km, `fixed_nearby`, and category (`takeup_gap` / `tower` / `satellite`) and five-year cost under main / lite / cost_minus30 / cost_plus30, plus `cost_upper_bound` |
| `costing_districts.csv` | 150 | Per district: settlements; take-up group (`n_takeup_gap`, `share_settlements_takeup_gap`, `takeup_gap_people_without_internet`); planned settlements (`n_tower`, `n_satellite`, `planned_people_without_internet`, `planned_students`); `main_fix` (and `_lite`); cost per case incl. `cost_upper_bound_rm`; **main value `people_per_rm_m_*` (rural people in planned settlements)**, secondary `people_per_rm_m_district_*`, `students_per_rm_m_*`; value ranks; need rank and CGI from the index |

**Raw input added:** `data/raw/census/census_district.csv`, the DOSM Population and Housing Census by district (1970–2020) from [github.com/dosm-malaysia/data-open](https://github.com/dosm-malaysia/data-open/blob/main/datasets/census/census_district.csv). DOSM Open Data Licence; downloaded 2026-11-19.
- **Columns used (2020):** `household_size_avg`, `density_rural` (rural population, not a density), `population_total`.
- **Coverage:** 160 districts. Gedong, Lingga, Pantu and Sebuyau post-date it. "Larut dan Matang" is aliased.

**Caveats**
- **Take-up group (proxy):** settlements with an Ookla fixed tile within 2 km are labelled **"fixed network likely nearby: take-up gap"**. They're **excluded from infrastructure cost**: 3,456 of 4,322 settlements (80%), holding ~468k rural people without home internet, against ~120k in planned settlements. They're costed as fibre PoPs only in the upper-bound case.
- **Totals (five-year):** main RM1.73bn (Sarawak RM0.82bn); Lite RM1.26bn (Sarawak RM0.44bn); upper bound RM6.81bn (Sarawak RM1.96bn). Uniform ±30% doesn't change any category.
- **No value rank:** 14 urban districts have no rural school, and 24 districts (none in Sarawak) have only take-up-gap settlements, so they have no infrastructure cost.

**`gap_index_sensitivity.csv`**: for each district, the baseline ranks plus three sensitivity checks:
- **Equal weights:** `cgi_equal`, `rank_*_equal`.
- **Random weights:** **1,000 Dirichlet(1,1,1,1) weight sets** (seed 42): `rank_*_dirichlet_median/_p05/_p95`.
- **Margin of error:** for the 25 small-sample districts, access is set to p − MOE and p + MOE (clipped to 0–100) with everything else unchanged. `rank_*_moe_min/_max` give the resulting range.

**Results to keep in mind**
- **Sarawak's top 3 are robust.** Kanowit, Song and Tebedu stay in Sarawak's top 10 in 98–100% of runs. But all three are **small-sample districts:** their access-margin-of-error ranks span 1–5, 1–7 and 1–8.
- **The rest of the top 10 is not stable.** In a typical run only 7 of the baseline top 10 remain (national and Sarawak). Serian (37%), Subis (37%) and Dalat (48%) are in Sarawak's top 10 in fewer than half of runs. **Present ranks with their p05–p95 range, not as a precise order.**
- **Kuching and Beaufort** include Siburan's and Membakut's Ookla tests but not their population, so their fixed_reach is slightly overstated (better than reality).

---

## Processed (from `scripts/build_boundaries.py`)

**`districts.geojson`**: 164 polygons, EPSG:4326, **ODbL 1.0** because it includes OSM data.

| Column | Meaning |
|---|---|
| state, district | Table 3 (2025) spelling, after `district_aliases.csv` |
| boundary_source | `DOSM 2022` (120 polygons, every state except Sarawak) or `OpenStreetMap` (44, Sarawak) |
| source_id | `dosm:<code_state_district>` or `osm:relation/<id>` |
| boundary_district | name as written in the source |
| dosm_level, dosm_district | join keys into the Table 3 CSVs |
| dosm_match | True for all 164 |
| contains_unmapped | DOSM districts with no polygon whose town lies inside this one |

**Caveats**
- **Mixed sources:** Sarawak uses OSM because the 2022 DOSM file predates Gedong, Lingga, Pantu and Sebuyau, all of which OSM has. OSM polygons are trimmed to the DOSM Sarawak outline so the coast and state borders match the rest of the map. They cover **99.44%** of that outline; a 708 km² gap (0.56%) along the edges belongs to no district. No polygons overlap.
- **Perlis:** it's a single-district state, and DOSM publishes only its state row. The Perlis polygon links to that row (`dosm_level = state`, `dosm_district = All Districts`).
- **No boundary in any source:**
  - **Siburan** (Sarawak): its town lies inside the **Kuching** polygon.
  - **Membakut** (Sabah): its town lies inside the **Beaufort** polygon.
  - Both appear only in tables. The Kuching and Beaufort polygons still cover their area, so any area-based value for Kuching or Beaufort (e.g. Ookla speeds) includes them. Their DOSM survey values are Kuching's and Beaufort's own, without Siburan and Membakut. Siburan's or Membakut's part of the parent polygon is unknown.
- **Edges differ between OSM and DOSM:** e.g. OSM Serian is 1,853 km² against 1,490 km² in DOSM 2022. Use the polygons for maps and spatial joins, not as official areas.

---

## Processed (from `scripts/extract_t3.py`)

Sources: `icths_{2024,2025}_table3.xlsx`, sheets 3.1 and 3.2.

| File | Rows | Columns |
|---|---|---|
| `dosm_hh_ict_district_{2024,2025}.csv` | 178 (162 districts + 13 states + 3 territories) | year, level, state, district, internet_pct, computer_pct, mobile_phone_pct, pay_tv_channel_pct, television_pct, radio_pct, fixed_line_telephone_pct, implied_sample_n, small_sample_flag, internet_moe95_pp |
| `dosm_ind_ict_district_{2024,2025}.csv` | 172 | year, level, state, district, internet_pct, computer_pct, mobile_phone_pct, implied_sample_n, small_sample_flag, internet_moe95_pp |
| `dosm_hh_internet_district_2024_2025.csv` | 165 (162 districts + 3 territories), all `matched = True` | level, state, district, internet_2024, internet_2025, internet_change_pp, small_sample_flag_2024, internet_moe95_pp_2024, small_sample_flag_2025, internet_moe95_pp_2025, change_beyond_noise, matched |
| `district_aliases.csv` | 14 | state, alias, canonical, alias_found_in, canonical_source |

**Parsing rules**
- **Repeated page headers:** each printed page repeats the title, "(%)" and header rows. They are skipped.
- **States:** an uppercase name is a state, with level `state` and district `All Districts`. State names are title-cased to match OpenDOSM ("NEGERI SEMBILAN" becomes "Negeri Sembilan").
- **Territories:** rows under "WILAYAH PERSEKUTUAN" are federal territories (level `territory`), named the OpenDOSM way, e.g. `W.P. Kuala Lumpur` in both state and district. They are not districts of Sarawak, the state listed just above them.
- **Districts:** names keep DOSM spelling with stray whitespace removed (e.g. "Kulai " becomes "Kulai").
- **Guards:** the script stops if it finds a value outside the indicator columns, a non-numeric cell, or a duplicate state+district.

**Caveats**
- **Districts missing from 3.2:** sheet 3.2 (individuals) has no rows for Membakut (Sabah) or Gedong, Lingga, Pantu, Sebuyau and Siburan (Sarawak), in either year. Those districts appear only in the household file.
- **Alias table (`district_aliases.csv`):** maps other spellings of the same district to the spelling in DOSM Table 3 (2025). It covers spelling only, never merges or splits. It's written by `extract_t3.py`, which checks that every standard spelling exists in Table 3 (2025).

  | Alias | Standard spelling | Where the alias appears |
  |---|---|---|
  | Seberang Prai Utara / Tengah / Selatan | Seberang Perai … | Table 3 (2024) |
  | Ulu Langat, Ulu Selangor | Hulu Langat, Hulu Selangor | DOSM boundaries; OpenDOSM population, income and schools |
  | Kecil Lojing | Lojing | DOSM boundaries; OpenDOSM population, income and schools |
  | Meradong | Maradong | OpenStreetMap boundaries; GADM; MOE enrolment |
  | Larut & Matang | Larut Dan Matang | OpenDOSM income (2024) |
  | S.P. Selatan, S.P.Tengah, S.P.Utara | Seberang Perai Selatan / Tengah / Utara | OpenDOSM income (2024) |
  | Lubok antu | Lubok Antu | OpenDOSM income (2024) |
  | Hulu | Hulu Terengganu | OpenDOSM income (2024), Terengganu |
  | Larut dan Matang | Larut Dan Matang | DOSM Census 2020 |

  The 2024→2025 combined file and `build_boundaries.py` apply it. The per-year CSVs keep each year's DOSM spelling, so apply the table before joining them to anything else.
- **Another Penang spelling in the income file:** `hh_income_district.parquet` contains both "Seberang Perai …" and abbreviated "S.P. Selatan", "S.P.Tengah", "S.P.Utara" rows. Those abbreviations are **not** in the alias table yet; deal with them when cleaning the income file.
- **`change_beyond_noise`** (combined file, an estimate):
  - **True** when |internet_change_pp| is larger than **every available** 95% MOE (the larger one when both years have one). **False** otherwise.
  - **Blank** when neither year has an MOE (i.e. neither year was small-sample flagged).
  - **Current result:** 0 True, 31 False, 134 blank. No flagged district's change exceeds its sampling noise, even if you compare against the smaller of the two MOEs. The largest change, Sebuyau at +5.83 pp, sits against MOEs of 12.6–16.2 pp.
  - **Blank does not mean the change is real.** Unflagged districts have no published or inferred MOE at all.
- **Ranking:** state-level rows are DOSM's published state estimates, not averages of the district rows.

### Small-sample flag (our estimate, not a DOSM figure)

DOSM does not publish district sample sizes or district-level standard errors (Table 7 is national and urban/rural only). We infer a small sample from the published percentages themselves:

- **Rule:** take every indicator of a district or territory that is strictly between 0 and 100. If all of them lie within **0.02 percentage points** of a multiple of 100/n for some **n ≤ 60**, the estimate most likely rests on about n sampled units: households in 3.1, individuals in 3.2.
- **Minimum:** the rule needs **at least 3** such indicators, otherwise the district is not flagged.
- **`implied_sample_n`:** the smallest such n.
- **`small_sample_flag`:** True when such an n exists.
- **`internet_moe95_pp`:** `1.96 × √(p(1−p)/n) × 100` with p = internet_pct/100. This is a simple-random-sampling approximation that ignores weighting and clustering, so it probably **understates** the true margin. Label it as an estimate.
- **Not flagged does not mean precise.** The method only detects samples small enough (n ≤ 60) to leave a visible pattern. Districts with larger but still modest samples get no MOE (blank), not a small one.
- **Results:**
  - Households 2024: 31 flagged (Sarawak 22, Sabah 7, Kelantan 1, Perak 1).
  - Households 2025: 25 flagged.
  - Individuals: 0 flagged in either year, as expected since individual samples are larger.
- **Use in the app:** flagged districts must be shown as low confidence with their MOE, never ranked as precise (see CLAUDE.md).
- **Check values (2024):**
  - Kanowit: 60.71%, n = 56, MOE 12.79 pp.
  - Song: 64.81%, n = 54.
  - Tebedu: 66.67%, n = 57.
  - Simunjan: 65.22%, not flagged.
