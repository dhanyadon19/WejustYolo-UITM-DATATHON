# Costing method

Status: **built** in `scripts/build_costing.py`, 19 Nov 2026. Outputs are `data/processed/costing_clusters.csv` and `costing_districts.csv`. Every cost is an **estimate** from `config/costs.yaml` (public statements and news reports, not engineering quotes) and must be labelled as such in the app.

Per district:
- **(a)** each rural settlement is either a **take-up gap** or gets an **infrastructure fix** (tower or satellite)
- **(b)** a five-year infrastructure cost
- **(c)** a ranking by **estimated beneficiaries per RM1m**

Nothing here recommends solar-hybrid power or fibre extension; fibre PoPs appear only as an upper-bound cost sensitivity.

## 1. The break-even is per settlement, not per district

`costs.yaml` gives the break-even as **households within reach of one tower**. It's one tower's five-year cost, RM1,557,143 + 5 × RM115,000 = **RM2,132,143**, divided by one Starlink terminal's five-year cost:
- RM14,800 (Residential), giving **144.1 households**;
- RM9,340 (Lite), giving **228.3 households**.

A whole district is far too large to compare with that number. So decisions are made **per settlement**, and a district's cost is the sum over its settlements.

## 2. Settlements

| Step | Rule | Source |
|---|---|---|
| Anchors | **One settlement per rural school** (`LOKASI = Luar Bandar`) in the MOE list, all states, placed in `districts.geojson` by its coordinates. The `likely_no_fibre` flag is **not** used: it failed validation against Hansard. | MOE *Senarai Sekolah*, 30 Jun 2022 |
| District rural households | Census 2020 rural population ÷ Census 2020 average household size | DOSM Population and Housing Census 2020, `census_district.csv` (DOSM data-open; official, all 160 districts of 2020). The column `density_rural` holds rural **population**; blank = 0. |
| Households per settlement | district rural households ÷ number of rural schools in the district | assumption: households are spread evenly across rural schools |
| Unconnected households and people | households × access_gap / 100; people = that × household size | DOSM ICTHS 2025, Table 3.1; Census 2020 household size |

**New districts.** Gedong, Lingga, Pantu and Sebuyau are not in the 2020 Census. Each takes its **parent** district's household size and rural share. The parent is the 2022 DOSM polygon the new district overlaps most: Gedong and Sebuyau → Simunjan; Lingga and Pantu → Sri Aman.

To avoid counting anyone twice, the parent's 2020 rural households are split between the parent and its new districts by their 2026 population (OpenDOSM). Flagged in `hh_source`.

Siburan and Membakut have no polygon. Their schools fall inside Kuching and Beaufort, which keep their full 2020 figures.

## 3. (a) Category per settlement

Applied in order:

1. **"Fixed network likely nearby: take-up gap"** (`takeup_gap`), if **any Ookla fixed tile lies within 2 km of the school**.
   - **Why:** an Ookla fixed tile means someone nearby ran a speed test on a home fixed connection, so a fixed network probably reaches the area. Our proxy suggests many rural settlements already have a fixed network nearby, so take-up support may matter as much as new infrastructure. Households there that still lack home internet may be held back by price, awareness, digital skills or the last-metre connection.
   - **This is a PROXY.** A fixed tile doesn't prove that fibre, rather than fixed wireless or satellite, is available to every household in the settlement.
   - These settlements are **excluded from the infrastructure cost**. For each district we report how many there are (`n_takeup_gap`, `share_settlements_takeup_gap`) and how many people without home internet they hold (`takeup_gap_people_without_internet`).
2. **Tower**, if households in the settlement ≥ the break-even (144.1 Residential; 228.3 Lite).
3. **Satellite** otherwise: one terminal per unconnected household, plus one Business terminal for the school.

The tower test uses **all households** in the settlement, as the break-even does. But satellite cost counts only **unconnected** households, because connected ones need no terminal.

**Caveat:** this is a cost screen, not a full cost-benefit comparison. Households are assumed equal across a district's rural schools, and towers and satellite are different services (a tower also serves mobile users and roads; satellite serves single homes).

A district's `main_fix` is tower or satellite, whichever serves more unconnected households among its **planned** (tower or satellite) settlements. It's "none (take-up gap only)" when every settlement is in the take-up group: 24 districts, none of them in Sarawak.

## 4. (b) Cost: five-year cost to provide service

Users' mobile plans are excluded.

| Item | Five-year cost | Value |
|---|---|---|
| Tower | capex (central) + 5 × opex | 1,557,143 + 575,000 = **RM2,132,143** |
| Satellite, household | kit + 60 × monthly | 1,600 + 60 × 220 = **RM14,800** (Lite: RM9,340) |
| Satellite, school | kit + 60 × Business "from" price | 1,600 + 60 × 318 = **RM20,680** (derived) |
| Take-up-gap settlement | **0** (no infrastructure) | upper bound only: one fibre PoP, **RM1,468,429**, capex only; running cost **UNSOURCED** |

**Results (19 Nov 2026)**

| Case | Malaysia | Sarawak | Notes |
|---|---|---|---|
| **Main** (Residential, central) | **RM1.73bn** | **RM0.82bn** | 866 planned settlements (804 tower, 62 satellite). 3,456 settlements are in the take-up group. |
| **Lite plan** | **RM1.26bn** | **RM0.44bn** | 253 settlements switch from tower to satellite; the main fix changes in 24 districts |
| **Upper bound** (cost sensitivity: +1 fibre PoP per take-up settlement; not a recommendation) | **RM6.81bn** | **RM1.96bn** | PoP running cost unsourced |
| All costs −30% / +30% | RM1.21bn / RM2.25bn | RM0.57bn / RM1.06bn | **no category changes**: the break-even is a ratio of two costs, so scaling every cost alike moves totals only |

**Take-up group:** 3,456 of 4,322 rural settlements (80%) hold an estimated **467,809** rural people without home internet, against an estimated **120,493** in planned settlements. Our proxy suggests many rural settlements already have a fixed network nearby, so take-up support may matter as much as new infrastructure. In Sarawak, 778 of 1,214 settlements are in the take-up group.

## 5. (c) Estimated beneficiaries per RM1m

The main metric covers the same people the cost pays for:

| Column | Definition | Role |
|---|---|---|
| `people_per_rm_m_main` | **rural people without home internet in planned settlements ÷ (cost / RM1m)** | **MAIN metric: estimated beneficiaries per RM1m**; ranks in `value_rank_national`, `value_rank_sarawak` (column names kept for compatibility) |
| `people_per_rm_m_district_main` | whole-district people without home internet (urban included) ÷ (cost / RM1m) | secondary; overstates beneficiaries because the plan doesn't reach urban or take-up-gap areas |
| `students_per_rm_m_main` | pupils of planned settlements' schools ÷ (cost / RM1m) | reported separately, never added to people |
| `people_per_rm_m_upper_bound` | all rural people without home internet ÷ upper-bound cost | sensitivity |

Districts with no planned settlements (cost 0) have **no estimated-beneficiaries-per-RM1m rank**. Ranks are also given per case (`value_rank_national_lite`, `_upper_bound`, `_cost_minus30`, `_cost_plus30`).

**Caveat:** this is a cost screen, not a full cost-benefit comparison. Households are assumed equal across a district's rural schools, and towers and satellite are different services (a tower also serves mobile users and roads; satellite serves single homes).

## 6. Findings to state in the app

- **JENDELA towers sit far below the break-even.** JENDELA 2 targets ~**80 residents per site** (2,700 sites for 217,000 residents; `costs.yaml`). That's about **17–29 households** at Sarawak's 2020 household sizes (2.8–4.7), **well below the 144–228 break-even**. Government towers are evidently justified by more than household cost: mobile coverage on roads, safety, and future demand. So our rule is a **cost screen, not a verdict**.
- **Take-up (proxy):** Our proxy suggests many rural settlements already have a fixed network nearby, so take-up support may matter as much as new infrastructure. Affordability, devices and skills programmes are a different policy lever, which this costing doesn't price.
- **The cost bases differ:** satellite cost includes the service subscription for 5 years; tower cost doesn't include what users later pay for mobile plans. This favours towers over satellite.

## 7. Unsourced assumptions (label in the app)

1. **Fibre PoP running cost:** missing from `costs.yaml`. PoPs appear only in the upper bound, as capex.
2. **"Fixed network likely nearby" = any Ookla fixed tile within 2 km:** a proxy. There's no fibre-route or coverage data, and fixed tiles also include fixed wireless and satellite home connections.
3. **Household size and rural share of the 4 post-2020 districts:** taken from the parent district (Census 2020), with households split by 2026 population.
4. **Equal households per rural school:** each rural school stands for one settlement, and a district's rural households are split equally across them.
5. **Satellite plan for schools** (Business "from RM318") and **government or bulk satellite prices** (retail prices used).
6. **Mobile user subscription price:** excluded from the cost basis, so tower costs omit users' payments.
