# Costing method

Status: **built** in `scripts/build_costing.py`, 19 Nov 2026; tower test changed to unconnected households on 24 Nov 2026 (see §4a). Outputs are `data/processed/costing_clusters.csv` and `costing_districts.csv`. Every cost is an **estimate** from `config/costs.yaml` (public statements and news reports, not engineering quotes) and must be labelled as such in the app.

Per district:
- **(a)** each rural settlement is either a **take-up gap** or gets an **infrastructure fix** (tower or satellite)
- **(b)** a five-year infrastructure cost
- **(c)** a ranking by **estimated beneficiaries per RM1m**

Nothing here recommends solar-hybrid power or fibre extension; fibre PoPs appear only as an upper-bound cost sensitivity.

## 1. The break-even is per settlement, not per district

`costs.yaml` gives the break-even as **households without home internet within reach of one tower**. It's one tower's five-year cost, RM1,557,143 + 5 × RM115,000 = **RM2,132,143**, divided by one Starlink terminal's five-year cost:
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
2. **Tower**, if **unconnected** households in the settlement (households × access gap) ≥ the break-even (144.1 Residential; 228.3 Lite).
3. **Satellite** otherwise: one terminal per unconnected household, plus one Business terminal for the school.

The tower test uses the **same households the costs pay for**: satellite cost counts only unconnected households (connected ones need no terminal), so the comparison does too. Until 24 Nov 2026 the test used **all** households in the settlement while satellite cost counted only unconnected ones, which compared a tower against a satellite bill for more homes than would ever get a terminal and so favoured towers. That earlier rule is kept as the sensitivity case **`rule_all_hh`** (§4a).

**Consequence:** a planned settlement has a median of about 27 unconnected households (90th percentile about 66), far below the break-even, so almost every planned settlement is now satellite: **7 towers** nationally (Bandar Baharu, Pasir Mas, and five settlements in Kinabatangan), **none in Sarawak**.

**Caveat:** this is a cost screen, not a full cost-benefit comparison. Households are assumed equal across a district's rural schools, and towers and satellite are different services (a tower also serves mobile users and roads; satellite serves single homes).

A district's `main_fix` is tower or satellite, whichever serves more unconnected households among its **planned** (tower or satellite) settlements. It's "none (take-up gap only)" when every settlement is in the take-up group: 24 districts, none of them in Sarawak. Under the main rule every Sarawak district's `main_fix` is satellite; `main_fix_rule_all_hh` gives the earlier rule's answer.

## 4. (b) Cost: five-year cost to provide service

Users' mobile plans are excluded.

| Item | Five-year cost | Value |
|---|---|---|
| Tower | capex (central) + 5 × opex | 1,557,143 + 575,000 = **RM2,132,143** |
| Satellite, household | kit + 60 × monthly | 1,600 + 60 × 220 = **RM14,800** (Lite: RM9,340) |
| Satellite, school | kit + 60 × Business "from" price | 1,600 + 60 × 318 = **RM20,680** (derived) |
| Take-up-gap settlement | **0** (no infrastructure) | upper bound only: one fibre PoP, **RM1,468,429**, capex only; running cost **UNSOURCED** |

**Results (24 Nov 2026)**

| Case | Malaysia | Sarawak | Notes |
|---|---|---|---|
| **Main** (Residential, central) | **RM0.44bn** | **RM0.26bn** | 866 planned settlements (7 tower, 859 satellite). 3,456 settlements are in the take-up group. |
| **Lite plan** | **RM0.29bn** | **RM0.17bn** | no settlement changes category (the same 7 towers clear the higher Lite break-even) |
| **Upper bound** (cost sensitivity: +1 fibre PoP per take-up settlement; not a recommendation) | **RM5.51bn** | **RM1.41bn** | PoP running cost unsourced |
| All costs −30% / +30% | RM0.31bn / RM0.57bn | RM0.18bn / RM0.34bn | **no category changes**: the break-even is a ratio of two costs, so scaling every cost alike moves totals only |
| **Rule sensitivity** `rule_all_hh` (Residential; tower test on all households, the earlier rule) | **RM1.73bn** | **RM0.82bn** | 804 tower, 62 satellite; 797 settlements and the main fix of 117 districts differ from the main case |

## 4a. Change of 24 Nov 2026: old rule vs new rule

The tower test changed from all households to unconnected households (§3). Take-up group, households, people and costs per unit are unchanged; only the tower/satellite split, and so the costs and rankings, move.

| | Old (all households) | New (unconnected households) |
|---|---|---|
| Settlements: take-up / tower / satellite | 3,456 / 804 / 62 | 3,456 / 7 / 859 |
| Sarawak: take-up / tower / satellite | 778 / 374 / 62 | 778 / 0 / 436 |
| Main, Malaysia / Sarawak | RM1.73bn / RM0.82bn | RM0.44bn / RM0.26bn |
| Lite | RM1.26bn / RM0.44bn | RM0.29bn / RM0.17bn |
| −30% / +30%, Malaysia | RM1.21bn / RM2.25bn | RM0.31bn / RM0.57bn |
| −30% / +30%, Sarawak | RM0.57bn / RM1.06bn | RM0.18bn / RM0.34bn |
| Upper bound | RM6.81bn / RM1.96bn | RM5.51bn / RM1.41bn |

**Sarawak rankings.** All 44 ranked Sarawak districts change their main fix (38, tower → satellite) or move more than 5 places in the estimated-beneficiaries-per-RM1m ranking (28). With almost every planned settlement on satellite, cost per household is nearly the same everywhere, so the ranking now mostly reflects household size and how many school terminals a district needs. The values are close together (Sarawak top 15: about 265–310 per RM1m), so **small rank differences mean little**: read the ranking with its range across cases.

**Take-up group:** 3,456 of 4,322 rural settlements (80%) hold an estimated **467,809** rural people without home internet, against an estimated **120,493** in planned settlements. Our proxy suggests many rural settlements already have a fixed network nearby, so take-up support may matter as much as new infrastructure. In Sarawak, 778 of 1,214 settlements are in the take-up group.

## 5. (c) Estimated beneficiaries per RM1m

The main metric covers the same people the cost pays for:

| Column | Definition | Role |
|---|---|---|
| `people_per_rm_m_main` | **rural people without home internet in planned settlements ÷ (cost / RM1m)** | **MAIN metric: estimated beneficiaries per RM1m**; ranks in `value_rank_national`, `value_rank_sarawak` (column names kept for compatibility) |
| `people_per_rm_m_district_main` | whole-district people without home internet (urban included) ÷ (cost / RM1m) | secondary; overstates beneficiaries because the plan doesn't reach urban or take-up-gap areas |
| `students_per_rm_m_main` | pupils of planned settlements' schools ÷ (cost / RM1m) | reported separately, never added to people |
| `people_per_rm_m_upper_bound` | all rural people without home internet ÷ upper-bound cost | sensitivity |

Districts with no planned settlements (cost 0) have **no estimated-beneficiaries-per-RM1m rank**. Ranks are also given per case (`value_rank_national_lite`, `_upper_bound`, `_cost_minus30`, `_cost_plus30`, `_rule_all_hh`).

**Caveat:** this is a cost screen, not a full cost-benefit comparison. Households are assumed equal across a district's rural schools, and towers and satellite are different services (a tower also serves mobile users and roads; satellite serves single homes).

## 6. Findings to state in the app

- **JENDELA towers sit far below the break-even.** JENDELA 2 targets ~**80 residents per site** (2,700 sites for 217,000 residents; `costs.yaml`). That's about **17–29 households** at Sarawak's 2020 household sizes (2.8–4.7), **well below the 144–228 break-even**. Government towers are evidently justified by more than household cost: mobile coverage on roads, safety, and future demand. So our rule is a **cost screen, not a verdict**.
- **Take-up (proxy):** Our proxy suggests many rural settlements already have a fixed network nearby, so take-up support may matter as much as new infrastructure. Affordability, devices and skills programmes are a different policy lever, which this costing doesn't price.
- **3D view is context only.** The 3D view shows terrain context only; it does not model line-of-sight or signal blocking (future work: add tower locations and a line-of-sight model).
- **Satellite in practice.** A terminal needs continuous power and a clear view of the sky (tall forest and hills can block it), and heavy rain can slow it. The monthly fee is a real cost to low-income households: the five-year cost includes the fee, but not who pays it once any subsidy ends. It serves a fixed location only: no mobile coverage on roads or farms. Check power, sky view, who pays the monthly fee, and repairs on the ground before choosing satellite (the District detail page lists these in its action plan box).
- **Take-up proxy may be too generous.** The same type of proxy (a fixed tile within 2 km) undercounted schools without fibre by about 33% against Hansard (786 flagged vs 1,180 in the six states; state errors vary widely), so the take-up group is likely overstated and the main cost understated; the upper bound covers this case.
- **The cost bases differ:** satellite cost includes the service subscription for 5 years; tower cost doesn't include what users later pay for mobile plans. This favours towers over satellite.

## 6a. Settlement types and technology options (added 26 Nov 2026, expert feedback)

Expert feedback from a telecom industry expert: do not frame the choice as satellite vs tower; group settlements by demand, distance to
existing networks, current service quality and terrain, then match a technology mix. `scripts/build_settlements.py` adds
mobile signal (Ookla), terrain (Terrain Tiles) and road distance (OpenStreetMap) to every settlement and assigns one type by
ordered rules (`config/settlement_types.yaml`): **A** Network nearby (fixed tile within 2 km) → **B** Larger unconnected
village (households without home internet ≥ tower break-even) → **E** Good mobile signal nearby (at least 20 Ookla mobile
tests within 2 km, combined, with mean download ≥ 35 Mbps; fewer tests are too noisy to judge) → **D** Isolated or difficult terrain (road > 5 km or mean slope ≥ 15°) → **C** Small village, reachable.

Costs per type use cited unit costs only. B (tower) and D (satellite per household + school terminal) equal the existing
`cost_main` for those settlements (tested). E uses a cited FWA retail plan: Yes 5G Advanced Home WiFi, RM99/month on a
24-month contract with the router included (yes.my, accessed 26 Nov 2026), so RM5,940 per household over five years; it
assumes the nearby mobile site has spare capacity and includes no network build cost. A (take-up support) and C (small cell
or community Wi-Fi with microwave or satellite backhaul) are **not costed (no public cost source)**: searches found no public
Malaysian unit cost for small cells, community Wi-Fi sites or microwave links. The tower-vs-satellite screen in sections 3-5
is unchanged and still drives the rankings and the budget planner; its totals are shown for comparison.

| Scope | Type | Settlements | People without home internet (est.) | Type cost, five-year (est.) | Tower-vs-satellite screen, same settlements |
|---|---|--:|--:|---|--:|
| All Malaysia | A. Network nearby | 3,456 | 467,809 | not costed (no public cost source) | RM0.0m |
| All Malaysia | B. Larger unconnected village | 7 | 10,567 | RM14.9m | RM14.9m |
| All Malaysia | E. Good mobile signal nearby | 83 | 10,906 | RM16.1m | RM41.9m |
| All Malaysia | D. Isolated or difficult terrain | 55 | 5,738 | RM21.6m | RM21.6m |
| All Malaysia | C. Small village, reachable | 721 | 93,283 | not costed (no public cost source) | RM360.5m |
| Sarawak | A. Network nearby | 778 | 114,459 | not costed (no public cost source) | RM0.0m |
| Sarawak | B. Larger unconnected village | 0 | 0 | – | RM0.0m |
| Sarawak | E. Good mobile signal nearby | 39 | 6,293 | RM9.5m | RM24.5m |
| Sarawak | D. Isolated or difficult terrain | 28 | 2,948 | RM12.4m | RM12.4m |
| Sarawak | C. Small village, reachable | 369 | 57,459 | not costed (no public cost source) | RM226.0m |

## 7. Unsourced assumptions (label in the app)

1. **Fibre PoP running cost:** missing from `costs.yaml`. PoPs appear only in the upper bound, as capex.
2. **"Fixed network likely nearby" = any Ookla fixed tile within 2 km:** a proxy. There's no fibre-route or coverage data, and fixed tiles also include fixed wireless and satellite home connections.
3. **Household size and rural share of the 4 post-2020 districts:** taken from the parent district (Census 2020), with households split by 2026 population.
4. **Equal households per rural school:** each rural school stands for one settlement, and a district's rural households are split equally across them.
5. **Tower test on unconnected households:** a tower also serves already-connected households' mobile use, which this cost screen doesn't credit; `rule_all_hh` shows the opposite extreme.
6. **Satellite plan for schools** (Business "from RM318") and **government or bulk satellite prices** (retail prices used).
7. **Mobile user subscription price:** excluded from the cost basis, so tower costs omit users' payments.
