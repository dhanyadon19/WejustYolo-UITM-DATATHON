# Costing method: proposal (not yet built)

Status: **proposal for review**, 19 Nov 2026. Nothing below is implemented yet. Every number shown in the app must come from a file in `data/` or `config/costs.yaml`. All costs are **estimates**.

Goal, per district:
- **(a)** recommend a fix: tower, fibre PoP or satellite
- **(b)** estimate the cost
- **(c)** rank districts by value: beneficiaries per RM

---

## 0. The key point: the break-even is per settlement, not per district

`config/costs.yaml` gives the break-even as **households within reach of one tower**:
- 144 households (Starlink Residential) or 228 (Residential Lite);
- derived from one tower's five-year cost of RM1,557,143 + 5 × RM115,000 = **RM2,132,143**;
- divided by one terminal's five-year cost of RM14,800 or RM9,340.

I checked the arithmetic: 2,132,143 / 14,800 = 144.1 and 2,132,143 / 9,340 = 228.3.

A district is far too big to compare against that number. Kanowit has about 6,700 households over 2,254 km²; Belaga has 6,800 over 19,050 km² (Census 2020). The comparison must be made **per settlement cluster**: the households one tower or one PoP could actually reach. A district's recommendation and cost are then **the sum over its clusters**, and a district can get a **mix** of fixes.

## 1. Inputs and their sources

| Input | Value | Source | Status |
|---|---|---|---|
| Unconnected share | access_gap = 100 − household internet % | DOSM ICTHS 2025, Table 3.1 (`gap_index_districts.csv`) | in repo. Small-sample districts carry an MOE; costs must be shown for low/central/high access. |
| Population | thousands, 2026 | OpenDOSM `population_district` | in repo |
| **Average household size** | **by district, 2020** (Sarawak ranges from 2.8 in Bukit Mabong to 4.7 in Bau) | **DOSM Population and Housing Census 2020**, `census_district.csv`, column `household_size_avg`, in [github.com/dosm-malaysia/data-open](https://github.com/dosm-malaysia/data-open/blob/main/datasets/census/census_district.csv) (DOSM Open Data Licence). It also gives `household_total` and `area_km2` for 160 districts. | **official, to download** (checked: 160/160 districts have a value). OpenDOSM's HIES files (`hies_state`, `hies_district`) have **no** household-size column. |
| Household size, 6 newer districts | Gedong, Lingga, Pantu, Sebuyau, Siburan (Sarawak); Membakut (Sabah) | **No official figure.** They post-date the 2020 Census. | **UNSOURCED.** Proposal: use the 2020 value of the parent district (Simunjan, Sri Aman, Kuching, Beaufort), labelled "parent district 2020". Siburan and Membakut are not in the index anyway (no boundary). |
| District area | km² | `districts.geojson`, computed in a metric CRS. Census `area_km2` is available as a cross-check for the 160 districts that existed in 2020. | in repo. OSM and DOSM edges differ in Sarawak (see data/README). |
| Rural share | rural population ÷ total | Census 2020 `density_rural` / `population_total`. Despite the column name, these are **population counts**, not densities. | official, to download |
| Settlement locations | where households actually are | **Needed and not in repo.** Candidates: WorldPop 100 m population grid, or Meta/CIESIN High Resolution Settlement Layer (both stated as CC BY 4.0). MOE school points (in repo) as settlement anchors. | **licence and year still to verify** before download |
| Tower capex, opex | RM1,557,143 (low) to RM2,650,000 (high) per site; RM115,000 a year | `config/costs.yaml` (JENDELA 2 Sarawak; SMART towers; Sarawak minister) | in repo, estimates |
| Tower reach | coverage radius | `costs.yaml: coverage_radius_km: null` | **UNSOURCED.** See 2.2. |
| Fibre PoP capex | RM1,468,429 (Sarawak) to RM1,572,327 (Sabah) per PoP; RM13,699 per premise; 107 premises per PoP | `costs.yaml` | in repo |
| Fibre PoP reach | 3 km radius | `costs.yaml` (minister's statement) | sourced |
| Fibre PoP opex | – | **not in costs.yaml** | **UNSOURCED.** Must be added, or tower and PoP costs aren't comparable. |
| Satellite | kit RM1,600; RM220 or RM129 a month; five-year cost RM14,800 or RM9,340 per household | `costs.yaml` (retail prices) | in repo. Bulk or government prices unknown. |
| Satellite for a school | kit + Business plan from RM318 a month = RM1,600 + 318 × 60 = **RM20,680 over 5 years** (derived) | `costs.yaml` `business_from` | derived; the plan size a school needs is unsourced |
| Fibre nearby? | is a fibre route close enough for a PoP? | **No route data.** Proxy: distance to the nearest Ookla fixed tile (`schools_connectivity.csv`). | **UNSOURCED threshold** |

## 2. (a) Recommending a fix

### 2.1 Define clusters, per district
1. **Anchors:** schools flagged `likely_no_fibre` in the 6 Hansard states. This follows MOE practice: 4,323 of 4,370 12th Malaysia Plan PoPs were sited near rural schools (`costs.yaml` notes). Outside those states, and between schools, use population-grid cells.
2. **Households within reach** of an anchor = population-grid people within radius *r*, ÷ district household size (Census 2020), × access_gap/100. That gives **unconnected households H**.
   - *Fallback until a population grid is added:* H ≈ the district's unconnected households ÷ its number of rural schools. Each school stands for one settlement. **This is a rough assumption** and must be labelled as such.
3. Merge anchors whose reach areas overlap, so the same households aren't counted twice.

### 2.2 Decision rule, per cluster
Applied in order:
1. **Fibre PoP**, if a fibre route is plausibly near (proxy: nearest Ookla fixed tile ≤ *D* km). PoP capex per premise reached (RM13,699 central) is comparable to satellite's five-year cost per household (RM9,340–14,800), so the PoP wins where a route exists. This follows `costs.yaml`'s note that "fibre PoP is preferred where a fibre route already passes nearby". **D is UNSOURCED.** Proposal: test 5 and 10 km and report both.
2. **Tower**, if **H ≥ 144** (Residential pricing) or **≥ 228** (Lite pricing), counting households within the tower's reach.
3. **Satellite** otherwise: one terminal per unconnected household, plus one Business terminal per school without fibre.

**Tower radius is UNSOURCED** (`costs.yaml` leaves it null). Proposal:
- **Do not invent a radius.** Run the rule with the PoP's 3 km as a conservative stand-in and label it so.
- Later, replace it with the line-of-sight simulator (app page 6).
- Show how many clusters change their recommendation between 3 km and a larger test radius.

**Settlement pattern and density.** The rule works on clusters, so density enters through H. For each district we also report descriptive context:
- density (population ÷ district area), rural share, and number of clusters;
- the **share of unconnected households in clusters below break-even**, which shows how much of the district is "satellite territory".

No fixed density threshold decides the technology. **Any such threshold would be unsourced,** so none is proposed.

### 2.3 What to watch for
- **JENDELA 2 cites ~80 residents per site** (`residents_per_site: 80`): roughly **17–29 households** at Sarawak's 2020 household sizes (2.8–4.7). That is far below the 144–228 break-even. Government towers are evidently justified by more than household cost (mobile coverage, roads, safety). So the rule will recommend satellite for many places that are actually getting towers. **Present it as a cost screen, not a verdict.**
- **The cost bases differ:** the Starlink five-year cost **includes the user's subscription**, while tower and PoP costs **exclude** what users later pay for mobile or fibre plans. The break-even therefore **favours towers**. Proposal: report it on two bases and say which is which.
  - **(i) Build and run cost only:** tower capex + opex; PoP capex (+ opex once sourced); satellite kit + subscription, if the government pays for the service.
  - **(ii) Including user fees.** Fibre's user price is in `costs.yaml` (RM35 a month, Sabah offer). **Mobile user price is UNSOURCED.**

## 3. (b) Cost per district

`cost_d = Σ_clusters cost(fix) + Σ_schools_without_fibre_in_satellite_clusters 20,680`

| Fix | Five-year cost used | Low / central / high |
|---|---|---|
| Tower | capex + 5 × 115,000 | 1,557,143 / 1,557,143 / 2,650,000 capex (+575,000 opex) |
| Fibre PoP | capex (+ opex when sourced) | 1,468,429 / 1,468,429 / 1,572,327 |
| Satellite (household) | 5-year terminal cost × H | 9,340 (Lite) / 14,800 (Residential) |

Report for each district:
- `cost_low`, `cost_central`, `cost_high`, combining the cost range **and** the access-MOE range for small-sample districts;
- the count of each fix;
- the share of the cost that rests on unsourced inputs (tower radius, PoP opex, *D*).

## 4. (c) Value ranking: beneficiaries per RM

- `people_per_rm_m` = people_without_home_internet ÷ (cost_central / 1,000,000)
- `students_per_rm_m` = students in schools without fibre that the plan connects ÷ (cost_central / 1,000,000)

People and students are reported **separately and never added**: students live in the households already counted. The value rank uses `people_per_rm_m`, with `students_per_rm_m` shown alongside. Each rank comes with its range under cost_low and cost_high and under the access-MOE bounds, as for the need rank. The app shows need rank (CGI) against value rank as a scatter (page 4).

## 5. Assumptions that are unsourced (must be labelled in the app)

1. **Tower coverage radius:** none. The 3 km PoP radius is used as a stand-in until the line-of-sight simulator replaces it.
2. **Fibre PoP opex:** missing from `costs.yaml`.
3. ***D*, the "fibre route nearby" distance:** proxied by the nearest Ookla fixed tile; 5 and 10 km to be tested.
4. **Household size of the 6 post-2020 districts:** parent district's 2020 value.
5. **The school-as-settlement fallback,** used until a population grid is added.
6. **Satellite plan size for schools** (Business "from RM318"), and **government or bulk satellite prices.**
7. **Mobile user subscription price,** needed for cost basis (ii).
8. **Population grid licence and year** (WorldPop or HRSL): to verify before download.

## 6. Data still to add, if approved
- **`census_district.csv` (DOSM, 2020):** household size, households, area, rural population. Goes into `data/raw/`, fetched by `download_raw.py`.
- **A population grid** for Malaysia (or Sarawak first): source and licence to confirm.
- **`costs.yaml` additions:** fibre PoP opex, plus any sourced tower radius.
