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

---

## Processed (from `scripts/extract_t3.py`)

Sources: `icths_{2024,2025}_table3.xlsx`, sheets 3.1 and 3.2.

| File | Rows | Columns |
|---|---|---|
| `dosm_hh_ict_district_{2024,2025}.csv` | 178 (162 districts + 13 states + 3 territories) | year, level, state, district, internet_pct, computer_pct, mobile_phone_pct, pay_tv_channel_pct, television_pct, radio_pct, fixed_line_telephone_pct, implied_sample_n, small_sample_flag, internet_moe95_pp |
| `dosm_ind_ict_district_{2024,2025}.csv` | 172 | year, level, state, district, internet_pct, computer_pct, mobile_phone_pct, implied_sample_n, small_sample_flag, internet_moe95_pp |
| `dosm_hh_internet_district_2024_2025.csv` | 165 (162 districts + 3 territories), all `matched = True` | level, state, district, internet_2024, internet_2025, internet_change_pp, small_sample_flag_2024, internet_moe95_pp_2024, small_sample_flag_2025, internet_moe95_pp_2025, change_beyond_noise, matched |
| `district_aliases.csv` | 3 | state, alias, canonical, alias_used_in, canonical_used_in, source |

**Parsing rules**
- **Repeated page headers:** each printed page repeats the title, "(%)" and header rows. They are skipped.
- **States:** an uppercase name is a state, with level `state` and district `All Districts`. State names are title-cased to match OpenDOSM ("NEGERI SEMBILAN" becomes "Negeri Sembilan").
- **Territories:** rows under "WILAYAH PERSEKUTUAN" are federal territories (level `territory`), named the OpenDOSM way, e.g. `W.P. Kuala Lumpur` in both state and district. They are not districts of Sarawak, the state listed just above them.
- **Districts:** names keep DOSM spelling with stray whitespace removed (e.g. "Kulai " becomes "Kulai").
- **Guards:** the script stops if it finds a value outside the indicator columns, a non-numeric cell, or a duplicate state+district.

**Caveats**
- **Districts missing from 3.2:** sheet 3.2 (individuals) has no rows for Membakut (Sabah) or Gedong, Lingga, Pantu, Sebuyau and Siburan (Sarawak), in either year. Those districts appear only in the household file.
- **Penang spelling change:** DOSM spells the three Penang districts "Seberang **Prai** Utara/Tengah/Selatan" in 2024 and "Seberang **Perai** …" in 2025.
  - `district_aliases.csv` maps each Prai name to its Perai name. "Perai" is the standard spelling here because OpenDOSM's population, income, amenities and schools files also use it.
  - The table is written by `extract_t3.py`, which first checks that both spellings actually appear in the data.
  - Aliases are applied **only in the combined file**. The per-year CSVs keep that year's DOSM spelling, so apply the alias table before joining them to anything else.
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
