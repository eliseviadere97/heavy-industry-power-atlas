# Assumptions register

Every assumption in the simplified model, numbered and grouped in pipeline order. Each entry gives its value, where it is set, its basis, and a status:

- **Keep:** agreed and defensible as is.
- **Check:** value or data to verify before publication.
- **Open:** a known limitation, stated on purpose; revisit if it matters for a result.

Config keys refer to `config/model_config.json`; files to `data/manual/` unless a folder is given. The model was simplified on 3 November 2026; removed features are listed at the end.

## The five assumptions that drive the results

1. **Each plant is powered behind the meter (0.3).** Every hour must be covered by the plant's own solar, wind, storage, SMRs or gas with capture in its region. No grid import, no exchange between regions. This is the main reason plants move, and it makes costs conservative.
2. **Moving is free (0.5).** No relocation premium and no product transport cost.
3. **Wind data reflect the 2015 turbine fleet (4.3).** EMHIRES capacity factors are lower than a modern turbine would achieve, which favours solar and southern regions.
4. **Land is a flat share of non-settled area (6.1).** Only 3.5% of it may host solar or wind.
5. **Output per site is capacity × one utilisation rate per sector (1.2).** Real output differs by plant, most of all for aluminium.

---

## 0 · Scope and framing

| # | Assumption | Value | Where | Status |
|---|---|---|---|---|
| 0.1 | Geography | EU27 + Norway + Switzerland + UK: 288 NUTS-2 regions. NUTS 2024, but NUTS 2016 for the UK (left NUTS after Brexit). Outermost regions, Ceuta, Melilla and Svalbard excluded | `data_prep.countries`, `excluded_nuts_prefixes` | Keep |
| 0.2 | Objective | Minimise the annual cost of firm clean power for all plants: the levelised cost of each plant's own generation, storage and backup, per MWh it consumes. Process equipment, labour, land and product transport excluded | `src/model/plan.js` | Keep |
| 0.3 | Behind the meter | Each plant serves its full load in every time slice from its own assets in its region. **No grid import and no unserved load.** Rationale: simplifies the optimisation and gives a conservative cost. A plant allowed to draw a capped share from the grid, or to sell flexibility, would need less firming of its own, so its real cost would be lower | `mix.js` | Keep |
| 0.4 | Cost year | Contemporary costs (2025–26 market data) | `model.mix` | Check: re-base on IEA WEO 2025 cost tables (5.x) |
| 0.5 | Moving | Free: no relocation premium, no product transport cost | `model.plan.relocPrem` = 0 | Keep (avoids an estimation debate) |
| 0.6 | Demand | Today's output at each existing site × electricity per tonne of the decarbonised route. No growth, no new plants | §1 | Keep |
| 0.7 | Static year | One representative year; no build-out path, no lead times | design | Keep |

## 1 · Demand per site

| # | Assumption | Value | Where | Status |
|---|---|---|---|---|
| 1.1 | Electricity per tonne (each value can be found in its source with Ctrl+F) | **Steel** (H₂-DRI + EAF) 3.48 MWh/t, 75% via electrolysers: [Vogl et al. 2018](https://zenodo.org/records/2669111/files/Vogl%20et%20al.%20(2018).pdf), search "3.48 MWh" (cross-check [Bhaskar et al. 2020](https://doi.org/10.3390/en13030758): 3.72). **Ammonia** (electrolytic H₂ + Haber-Bosch) 10 MWh/t, 90% via electrolysers: [IRENA 2022](https://www.irena.org/-/media/Files/IRENA/Agency/Publication/2022/May/IRENA_Innovation_Outlook_Ammonia_2022.pdf), search "10 MWh per tonne". **Aluminium** (smelting) 13.2 MWh/t: [JRC 2024](https://publications.jrc.ec.europa.eu/repository/bitstream/JRC136525/JRC136525_01.pdf), search "13.2 MWh". **Cement** (electric kiln) 0.74 MWh/t clinker: [JRC 2023](https://publications.jrc.ec.europa.eu/repository/bitstream/JRC131246/JRC131246_01.pdf), search "2.68 GJ/t clinker" (÷ 3.6). **Chemicals** (electric cracking furnaces) 7.1 MWh/t ethylene: [PBL/TNO 2021](https://www.pbl.nl/sites/default/files/downloads/pbl-2021-decarbonisation-options-for-large-volume-organic-chemicals-production-sabic-geleen_3718.pdf), search "29.5" (PJ/yr, Table 19) and "1,150" (kt ethylene, Table 3) | `model.sectors[].mwh_per_t`, `.source` | Keep. Not included: alumina refining (separate plants), cement grinding and CO₂ capture electricity |
| 1.2 | Output per site | Capacity × sector utilisation: steel 75%, cement 75%, ammonia 75%, chemicals 80%, aluminium 85%. Idle and closed plants produce nothing | `model.sectors[].utilisation` | **Check per site** in the review spreadsheet. Aluminium is the weak spot: EU smelters ran near 50% in 2023 while Norway's run near full, so 85% overstates EU output by ~0.8 Mt (~13 TWh) |
| 1.3 | EU ETS cement kilns | Value = 2014 (else 2013) verified emissions ÷ 0.83 t CO₂/t clinker, i.e. that year's **output**; used as output directly | `data_prep.cement` | Check: 2014 data |
| 1.4 | Load shape | Flat all year. The electrolyser share can follow the weather if hydrogen storage is allowed; downstream hydrogen use stays flat | `mix.js` | Keep |

### Sources for electricity per tonne (1.1)

Each value can be checked in its source with a text search (Ctrl+F). Page numbers refer to the PDF. The same citations, search phrases and conversions are stored in `config/model_config.json` (`model.sectors[].source`) and shown on the map page under Model assumptions → Source.

| Sector | Value used | Source | Search for | Page | Quote | Conversion | Not included |
|---|---|---|---|---|---|---|---|
| Steel (H₂-DRI + electric arc furnace) | 3.48 MWh per tonne of steel | Vogl, V., Åhman, M. and Nilsson, L.J. (2018), "Assessment of hydrogen direct reduction for fossil-free steelmaking", *Journal of Cleaner Production* 203, 736–745. [Open-access PDF](https://zenodo.org/records/2669111/files/Vogl%20et%20al.%20(2018).pdf), [DOI](https://doi.org/10.1016/j.jclepro.2018.08.279) | `3.48 MWh` | 1 (abstract), 4 | "hydrogen direct reduction steelmaking needs 3.48 MWh of electricity per tonne of liquid steel" | None | Pellet making, casting and rolling. Cross-check: [Bhaskar et al. (2020)](https://doi.org/10.3390/en13030758), 3.72 MWh/t |
| Ammonia (electrolytic hydrogen + Haber-Bosch) | 10 MWh per tonne of ammonia | IRENA and Ammonia Energy Association (2022), *Innovation Outlook: Renewable Ammonia*. [PDF](https://www.irena.org/-/media/Files/IRENA/Agency/Publication/2022/May/IRENA_Innovation_Outlook_Ammonia_2022.pdf) | `10 MWh per tonne` | 46, 59 | "10 MWh per tonne for current alkaline electrolyser technologies" | None | — |
| Aluminium (primary smelting) | 13.2 MWh per tonne of aluminium | Joint Research Centre, European Commission (2024), *Decarbonisation options for the aluminium industry* (Zore, L. et al., EUR 31925). [PDF](https://publications.jrc.ec.europa.eu/repository/bitstream/JRC136525/JRC136525_01.pdf) | `13.2 MWh` | 9 | "Globally, around 13.2 MWh was used per tonne of primary aluminium in 2022" | None | Alumina refining (about 10.2 GJ per tonne of alumina, same page), which takes place at separate refineries |
| Cement (electric kiln) | 0.74 MWh per tonne of clinker | Joint Research Centre, European Commission (2023), *Decarbonisation options for the cement industry* (Marmier, A., JRC131246). [PDF](https://publications.jrc.ec.europa.eu/repository/bitstream/JRC131246/JRC131246_01.pdf) | `2.68 GJ/t clinker` | 46 | "Electric kiln is assumed to be the most energy efficient with specific energy intensity – 2.68 GJ/t clinker" | 2.68 GJ ÷ 3.6 GJ per MWh = 0.74 MWh | Raw-material and cement grinding (90–150 kWh per tonne of cement, p. 27) and electricity for CO₂ capture |
| Chemicals (electric steam-cracking furnaces) | 7.1 MWh per tonne of ethylene | PBL Netherlands Environmental Assessment Agency and TNO (2021), *Decarbonisation options for large volume organic chemicals production, SABIC Geleen* (MIDDEN series). [PDF](https://www.pbl.nl/sites/default/files/downloads/pbl-2021-decarbonisation-options-for-large-volume-organic-chemicals-production-sabic-geleen_3718.pdf) | `29.5` and `1,150` | 47 (Table 19), 13 (Table 3) | Estimated electricity demand of electric furnaces: 29.5 PJ/yr; ethylene production: 1,150 kt/yr | 29.5 PJ = 8.19 TWh; 8.19 TWh ÷ 1.15 Mt = 7.1 MWh per tonne of ethylene | Electricity already used by the rest of the cracker (about 3% of its energy, p. 25). All energy is attributed to ethylene, although the crackers also make propylene and other products |

No public agency report found states the cement or chemicals figure directly in MWh per tonne; those two values take the one conversion shown.

## 2 · Plants

| # | Assumption | Value | Where | Status |
|---|---|---|---|---|
| 2.1 | Steel | 25 blast-furnace works (22 producing); electric-arc plants excluded | `steel_plants.csv` | Check (review spreadsheet) |
| 2.2 | Cement | 156 kilns: EU ETS records + hand-compiled additions (incl. 10 UK, 2 NO, 6 CH). Two UK ETS rows dropped for wrong coordinates and re-added | raw workbook, `cement_additions.csv`, `cement_exclusions.csv` | Check |
| 2.3 | Ammonia | 29 sites: PyPSA-Eur list (incl. Billingham, Porsgrunn), gaps filled, 3 Polish sites added | raw, `ammonia_*.csv` | Check |
| 2.4 | Chemicals | 32 steam crackers (incl. Rafnes, Mossmorran, Grangemouth, Wilton) | `steam_crackers.csv` | Check: status of the three UK crackers |
| 2.5 | Aluminium | 22 primary smelters (20 producing), incl. 7 Norwegian and Lochaber | `aluminium_smelters.csv` | Check |
| 2.6 | Plants added for NO, CH, UK | Compiled from general knowledge of operator information, **not individually verified** | `data/manual/*.csv` (rows marked NOT VERIFIED) | **Check first** |
| 2.7 | Locations | Town-level coordinates, snapped to a region within 25 km, same country | `data_prep.snap_km` | Keep |
| 2.8 | Human check | `outputs/review/plant_lists_for_review.xlsx`: one sheet per sector with reviewer columns | generated by data prep | Open |

## 3 · Population

| # | Assumption | Value | Where | Status |
|---|---|---|---|---|
| 3.1 | Population density | Eurostat demo_r_d2jan, 1 January 2024; UK 2019 (last published), Northern Ireland 2018 | `data/raw/eurostat/`, `population_overrides.csv` | Keep |
| 3.2 | Settled land | Population ÷ 3,000 people per km² (max 95% of the region) | `model.plan.urbanDensity` | Keep |

## 4 · Weather

| # | Assumption | Value | Where | Status |
|---|---|---|---|---|
| 4.1 | Time slices | 24: twelve months × day and night, each 12 hours, weighted by hours | `mix.js` | Keep |
| 4.2 | Solar | PVGIS 5.3 monthly yield of a fixed, optimally tilted 1 kWp system, 14% system losses, PVGIS-ERA5 2005–23; mean of up to 6 grid points inside each region. All output falls in the day slice | `data/derived/pv_monthly_cf.csv`, `fetch_weather.py` | Keep |
| 4.3 | Onshore wind | JRC EMHIRES NUTS-2 hourly capacity factors 1986–2015 (wind fleet of end-2015), averaged by month for day (06–18 UTC) and night; mapped to the model's regions by area overlap. Malta has no data and takes Sicily's | `data/derived/wind_monthly_cf.csv` | **Open:** 2015 fleet understates modern turbines; regions with few turbines carry weak values |
| 4.4 | Within-month variability | Calm spells and day-to-day weather inside a month are not represented; only the monthly day/night means | design | Open: understates firming needs |
| 4.5 | Offshore wind | Not modelled | — | Keep (simplification) |

## 5 · Technology costs (contemporary)

One cost of capital for every technology, adjustable on the page.

| # | Technology | Value | Where | Status |
|---|---|---|---|---|
| 5.1 | Cost of capital | 6% (slider 2–12%) | `wacc` | Keep |
| 5.2 | Solar PV | €500/kW, 2% O&M, 25 years | `pv*` | Check vs IEA |
| 5.3 | Onshore wind | €1,400/kW, 2.5% O&M, 25 years | `w*` | Check vs IEA |
| 5.4 | Batteries | €200/kWh, 4 hours, 15 years, 88% round trip, 2% O&M; charged by day, discharged the same month's nights | `bat*` | Check vs IEA (BNEF: $275/kWh turnkey 2024) |
| 5.5 | Electrolysers | €1,800/kW, 3% O&M, 20 years; only capacity above flat running is costed; 0.63 MWh H₂ per MWh electricity (= 53 kWh/kg) | `el*`, `h2PerMwhEl` | Check (IEA 2026: $1,900–2,500/kW) |
| 5.6 | Hydrogen storage | One cost everywhere (no salt caverns): €15/kWh H₂ of storage volume, 30 years, 2% O&M, 3% loss | `h2Store*` | Check (tank-type cost) |
| 5.7 | SMRs | €8,000/kW, 60 years, €110/kW-yr fixed, €12/MWh variable, 92% availability; ≈ €87/MWh baseload at 6% | `smr*` | Check vs IEA |
| 5.8 | Gas with carbon capture | €2,000/kW, 50% efficiency, 90% capture, €40/t CO₂ transport and storage, 90% availability; residual 10% of CO₂ priced | `ccs*` | Check |
| 5.9 | Fuel and carbon | Gas €40/MWh, CO₂ €100/t (sliders); 0.202 t CO₂/MWh gas; methane leakage ignored | `gasPrice`, `co2`, `gasEf` | Keep |

## 6 · Local mix and land

| # | Assumption | Value | Where | Status |
|---|---|---|---|---|
| 6.1 | Land for solar and wind | 3.5% of non-settled land; solar needs 1 km² per 50 MW, wind 1 km² per 20 MW, from one shared pool | `landShare`, `pvDens`, `wDens` | Check |
| 6.2 | Technologies | Solar, onshore wind, batteries, hydrogen storage, SMRs (where not barred), gas with capture. **No unabated gas**, so every mix is decarbonised apart from CCS residuals | `mix.js` | Keep |
| 6.3 | SMR and CCS operation | Any level between zero and availability; no minimum load or ramp limits | `mix.js` | Open (flatters SMRs) |
| 6.4 | Curtailment | Surplus is curtailed for free and earns nothing | `mix.js` | Keep |
| 6.5 | When land runs out | The rest of the plant's load is costed at the region's no-new-renewables mix (SMR or CCS); the cost is a straight blend of the two mixes | `plan.js` | Open |
| 6.6 | Nuclear policy | New reactors barred in AT, CH, DE, DK, ES, IE, LU, PT (switch on the page) | `nuclear_policy.csv` | Check: Switzerland (ban repeal under debate), Norway |
| 6.7 | Infeasible load | Only possible if SMRs and CCS are both unavailable and land is short; priced at €1,000/MWh and shown as "without supply" | `model.plan.infeasible` | Keep |

## 7 · Planner

| # | Assumption | Value | Where | Status |
|---|---|---|---|---|
| 7.1 | Plants | Indivisible; keep their output and demand wherever they go | `plan.js` | Keep |
| 7.2 | Land sharing | Plants in one region share its land; those saving most per km² are served first (optimal for one shared resource) | `plan.js` | Keep |
| 7.3 | Method | Step 1: least-cost mix per region × sector (exact LPs). Step 2: plant placement by greedy construction + local search (single moves and pairwise swaps) | `plan.js` | Keep |
| 7.4 | Check | The pipeline re-solves the placement as a mixed-integer programme with HiGHS and reports the heuristic's gap | `outputs/validation/plan_check.csv` | Keep |

## 8 · Second-best constraints

| # | Assumption | Value | Where | Status |
|---|---|---|---|---|
| 8.1 | Grid | A plant may move only to a region with at least one AC substation ≥330 kV (ENTSO-E map extract in PyPSA-Eur, several years old). No headroom limit; today's sites keep their connections | `cGrid` | Keep |
| 8.2 | Clusters | Movers go only to regions that already host their sector; 50% of each sector's output must stay; the planner picks which plants move | `cEco`, `alpha` | Keep |

---

## Removed on 3 November 2026

Offshore wind and coastline; existing renewables and the renewables cap; grid headroom and congestion scores; salt caverns; unabated gas backup; grid import and unserved load; the eight stylised slices and author-estimated weather anchors; the household reserve; protected-area exclusions; the relocation-premium slider; alternative production routes; chlor-alkali cluster markers; GeoNames-based population.
