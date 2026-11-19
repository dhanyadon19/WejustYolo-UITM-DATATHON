# Costing method

Status: **built** in `scripts/build_costing.py`, 19 Nov 2026. Outputs are `data/processed/costing_clusters.csv` and `costing_districts.csv`. Every cost is an **estimate** from `config/costs.yaml` (public statements and news reports, not engineering quotes) and must be labelled as such in the app.

Per district:
- **(a)** a recommended fix per settlement cluster: tower, fibre PoP or satellite
- **(b)** a five-year cost
- **(c)** a value ranking: beneficiaries per RM1m

## 1. The break-even is per settlement, not per district

`costs.yaml` gives the break-even as **households within reach of one tower**. It's one tower's five-year cost, RM1,557,143 + 5 × RM115,000 = **RM2,132,143**, divided by one Starlink terminal's five-year cost:
- RM14,800 (Residential), giving **144.1 households**;
- RM9,340 (Lite), giving **228.3 households**.

A whole district is far too large to compare with that number. So the decision is made **per settlement cluster**, and a district's cost is the sum over its clusters. A district can get a **mix** of fixes.

## 2. Settlement clusters

| Step | Rule | Source |
|---|---|---|
| Anchors | **One cluster per rural school** (`LOKASI = Luar Bandar`) in the MOE list, all states, placed in `districts.geojson` by its coordinates. The `likely_no_fibre` flag is **not** used: it failed validation against Hansard. | MOE *Senarai Sekolah*, 30 Jun 2022 |
| District rural households | Census 2020 rural population ÷ Census 2020 average household size | DOSM Population and Housing Census 2020, `census_district.csv` (DOSM data-open; official, all 160 districts of 2020). The column `density_rural` holds rural **population**; blank = 0. |
| Households per cluster | district rural households ÷ number of rural schools in the district | assumption: households are spread evenly across rural schools |
| Unconnected households | households × access_gap / 100 (district rate) | DOSM ICTHS 2025, Table 3.1 |

**New districts.** Gedong, Lingga, Pantu and Sebuyau are not in the 2020 Census. Each takes its **parent** district's household size and rural share. The parent is the 2022 DOSM polygon the new district overlaps most: Gedong and Sebuyau → Simunjan; Lingga and Pantu → Sri Aman.

To avoid counting anyone twice, the parent's 2020 rural households are split between the parent and its new districts by their 2026 population (OpenDOSM). Flagged in `hh_source`.

Siburan and Membakut have no polygon. Their schools fall inside Kuching and Beaufort, which keep their full 2020 figures; Siburan and Membakut get no clusters of their own.

## 3. (a) Fix per cluster

Applied in order:
1. **Fibre PoP**, if **any Ookla fixed tile lies within 2 km of the school**. This is a **proxy for "fibre route nearby"**: there is no fibre-route data. It follows `costs.yaml`'s note that a PoP is preferred where a fibre route already passes nearby.
2. **Tower**, if households in the cluster ≥ the break-even (144.1 Residential; 228.3 Lite).
3. **Satellite** otherwise: one terminal per unconnected household, plus one Business terminal for the school.

The tower test uses **all households** in the cluster, as the break-even does. But satellite cost counts only **unconnected** households, because connected ones need no terminal.

The district's `fix_*` column is the fix serving the most unconnected households. The counts of each fix are in `n_fibre_pop`, `n_tower` and `n_satellite`.

## 4. (b) Cost: five-year cost to provide service

Users' mobile plans are excluded. Main case: **Residential plan, central costs.**

| Fix | Five-year cost | Value (main) |
|---|---|---|
| Tower | capex (central) + 5 × opex | 1,557,143 + 575,000 = **RM2,132,143** |
| Satellite, household | kit + 60 × monthly | 1,600 + 60 × 220 = **RM14,800** (Lite: RM9,340) |
| Satellite, school | kit + 60 × Business "from" price | 1,600 + 60 × 318 = **RM20,680** (derived) |
| Fibre PoP | **capex only**; running cost **UNSOURCED** | **RM1,468,429** (Sarawak central). Flagged in `fibre_pop_opex_unsourced`. |

**Sensitivity (main results, 19 Nov 2026)**

| Case | Districts whose fix changes | Clusters that change | Total cost |
|---|---|---|---|
| Main (Residential) | – | – | RM6.81bn |
| All costs −30% | **0** | 0 | RM4.77bn |
| All costs +30% | **0** | 0 | RM8.85bn |
| Lite plan | **8**, all Sarawak, tower → satellite: Kanowit, Kapit, Pakan, Lubok Antu, Kabong, Saratok, Julau, Sibu | 253 | RM6.33bn |

Scaling every cost by the same factor **can't change any decision**, because the break-even is a ratio of two costs. Only totals and value ratios move. The decisions depend on the **relative** price of tower and satellite, which the Lite case tests.

## 5. (c) Value ranking

- `people_per_rm_m` = people_without_home_internet ÷ (cost / RM1m). This is the **value rank**, nationally and within Sarawak.
- `students_per_rm_m` = pupils in the district's rural schools ÷ (cost / RM1m).

The two are reported **separately and never added**: students live in the households already counted.

- **Scope mismatch:** `people_without_home_internet` covers the **whole district**, urban areas included, while cost covers rural clusters only. `rural_people_without_internet_est` (unconnected rural households × household size) is provided as a cross-check.
- **Not ranked:** 14 districts have no rural school, so they have no cost and no value rank (e.g. Kota Bharu, Petaling, W.P. Kuala Lumpur).

## 6. Findings to state in the app

- **JENDELA towers sit far below the break-even.** JENDELA 2 targets ~**80 residents per site** (2,700 sites for 217,000 residents; `costs.yaml`). That's about **17–29 households** at Sarawak's 2020 household sizes (2.8–4.7), **well below the 144–228 break-even**. Government towers are evidently justified by more than household cost: mobile coverage on roads, safety, and future demand. So our rule is a **cost screen, not a verdict**.
- **Fibre PoP dominates:** 3,456 of 4,322 clusters (80%) get a PoP because a fixed tile lies within 2 km. A nearby fixed tile can also mean the area **already has** fibre, in which case a new PoP isn't needed. The PoP share and cost are probably **overstated**.
- **The cost bases differ:** satellite cost includes the service subscription for 5 years; tower and PoP costs don't include what users later pay for mobile or fibre plans. This favours towers and PoPs over satellite.

## 7. Unsourced assumptions (label in the app)

1. **Fibre PoP running cost:** missing from `costs.yaml`; PoP cost is capex only.
2. **"Fibre route nearby" = any Ookla fixed tile within 2 km:** a proxy; there is no route data.
3. **Household size and rural share of the 4 post-2020 districts:** taken from the parent district (Census 2020), with households split by 2026 population.
4. **Households spread evenly across a district's rural schools:** each rural school stands for one settlement of equal size.
5. **Satellite plan for schools** (Business "from RM318") and **government or bulk satellite prices** (retail prices used).
6. **Mobile user subscription price:** excluded from the cost basis, so tower costs omit users' payments.
