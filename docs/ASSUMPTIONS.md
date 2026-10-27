# Assumptions register

Every assumption in the model, numbered and grouped in pipeline order. Each entry gives its default value, where it is set, its basis, and a verdict:

- **Keep:** defensible as is.
- **Revise:** change the value or method.
- **Replace:** swap in a proper dataset.
- **Decide:** a framing choice for the author.

Config keys refer to `config/model_config.json`; files to `data/manual/`.

## The six assumptions that drive the results

1. **The model moves plants, not electrons (0.3).** Each plant runs only on power from its own region; there is no transmission between regions and no hydrogen pipelines. This is the main reason the planner relocates.
2. **Weather averages are the author's estimates (4.1),** not downloaded data.
3. **Moving is free (8.2):** no relocation premium, no product transport cost.
4. **Variability comes from stylised shape rules (4.4–4.7).** They size the firming, and so the choice between batteries, hydrogen, SMRs and gas.
5. **Land is a flat share of non-urban area, and regions power their own households first (7.1–7.5).** This empties dense regions.
6. **No cost year is fixed (0.4).**

---

## Step 0 · Scope and framing

| # | Assumption | Default | Where | Verdict |
|---|---|---|---|---|
| 0.1 | Geography | EU27, 234 NUTS-2 regions (2024). Excludes outermost regions, Ceuta and Melilla. No UK, Norway or Switzerland | `data_prep.eu27`, `data_prep.excluded_nuts_prefixes` | Decide: Norway matters for aluminium and hydro |
| 0.2 | Objective | Minimise the annual cost of clean power for the plants. Excludes process kit, labour, land and product transport | `src/model/plan.js` | Keep; stated |
| 0.3 | Energy transport | None between regions; grid import switched off | `model.mix.impOn` | **Decide** |
| 0.4 | Cost year | Not fixed: 2024–26 market data alongside forward-looking SMR costs | `model.mix` | **Decide** (suggest 2035) |
| 0.5 | Weather | Long-term annual averages; no year-to-year variation | design | Keep (author's choice) |
| 0.6 | Demand metric | Total clean power the decarbonised process needs, not the increase on today | design | Keep; stated |

## Step 1 · Demand

| # | Industry | Default | Where | Basis | Verdict |
|---|---|---|---|---|---|
| 1.1 | Steel | 70 Mt primary output; hydrogen DRI + electric arc furnace, 3.5 MWh/t, 75% flexible | `model.industries[steel]` | ~55% of 126 Mt crude steel (2023); Vogl et al. (2018): 3.48 MWh/t, of which 2.63 is electrolysis | Keep |
| 1.2 | Steel, alternative | Scrap-based arc furnace, 0.65 MWh/t | same | — | **Known issue K1** |
| 1.3 | Cement | 118 Mt clinker; electrified kiln + carbon capture, 1.3 MWh/t, steady | `model.industries[cement]` | ≈160 Mt cement × 0.74 clinker ratio; intensity is an author estimate | Revise with literature |
| 1.4 | Ammonia | 13 Mt; electrolytic hydrogen + Haber-Bosch, 10.5 MWh/t, 90% flexible | `model.industries[ammonia]` | 0.178 t H₂/t × 53 kWh/kg + ~1 MWh for air separation and the ammonia loop | Keep |
| 1.5 | Chemicals | 30 Mt HVC; electric crackers 2.2 MWh/t (steady), or + e-methanol feedstock 25 MWh/t (90% flexible) | `model.industries[chemicals]` | Author estimates | Revise with literature |
| 1.6 | Aluminium | 1.0 Mt primary; inert anodes + electrified alumina, 16.5 MWh/t, steady | `model.industries[aluminium]` | ~14 MWh/t smelting + ~2.5 MWh/t alumina | Keep |
| 1.7 | Load shape | Flat all year. Hydrogen use downstream is steady; potline flexibility (±20–30%) is ignored | `mix.js` | Conservative | Keep |

## Step 2 · Plants and capacities (230 plants)

| # | Assumption | Default | Where | Verdict |
|---|---|---|---|---|
| 2.1 | Steel sites | 23 blast-furnace works, 98 Mt, including idle Ostrava and Dunaújváros; existing arc-furnace plants left out | `steel_plants.csv` | Revise |
| 2.2 | Cement sites | 138 kilns: 75 from 2014 EU ETS records (capacity = emissions ÷ 0.83 t CO₂/t clinker) plus 63 added; Maastricht dropped | raw workbook + `cement_additions.csv`, `data_prep.cement` | **Replace** (Global Energy Monitor cement tracker) |
| 2.3 | Ammonia sites | 27 sites, 17.2 Mt: PyPSA-Eur list, gaps filled, 3 Polish sites added | raw + `ammonia_*.csv` | Keep |
| 2.4 | Chemicals sites | 28 steam crackers, 20.8 Mt ethylene | `steam_crackers.csv` | Keep; verify |
| 2.5 | Aluminium sites | 14 primary smelters, 2.4 Mt, including idle ones | `aluminium_smelters.csv` | Decide |
| 2.6 | Output allocation | Split by capacity, so every plant in an industry runs at the same rate (steel 71%, ammonia 75%, aluminium 42%) and idle plants get output | `plan.js` | **Known issue K3 / Decide** |
| 2.7 | Locations | Town-level coordinates, snapped to a region within 25 km | `data_prep.snap_km` | Keep |
| 2.8 | Chlor-alkali | 67 sites mark chemical clusters (no load) | raw workbook | Keep |

## Step 3 · Regional geography

| # | Assumption | Default | Where | Verdict |
|---|---|---|---|---|
| 3.1 | Population | GeoNames towns above 15,000, scaled to Eurostat 2024 national totals; the residual (≥15%) spread by area | `data_prep.population`, `population_national_2024.csv` | Replace with Eurostat NUTS-2 population (demo_r_pjangrp3) |
| 3.2 | Urban land | Urban population ÷ 3,000 people per km² | `model.plan.urbanDensity` | Replace with land-cover data |

## Step 4 · Weather (averages only)

| # | Assumption | Default | Where | Verdict |
|---|---|---|---|---|
| 4.1 | Solar and onshore wind capacity factors | 157 anchor points set by the author; inverse-distance weighting over the 5 nearest | `weather_anchors.csv`, `data_prep.weather_idw` | **Replace first** (EMHIRES or Renewables.ninja NUTS-2 averages) |
| 4.2 | Wind quality | Regional average for a modern turbine; the best sites do better | same | Note: understates the windiest regions |
| 4.3 | Offshore wind | Capacity factor by basin: North Sea 48%, Atlantic 45%, Baltic 42%, Black Sea 36%, Mediterranean 34% | `offshore_basins.csv` | Check |
| 4.4 | Year structure | 8 equal slices (winter/summer × windy/calm × day/night); 12-hour days everywhere | `mix.js` | Revise: northern winter nights are longer |
| 4.5 | Solar seasonality | Winter-half share of output: 37% at 37°N, 25% at 51°N, 12.5% at 65°N | `model.slices.solar_*` | Calibrate |
| 4.6 | Wind seasonality | Winter half gets 57–63% of output | `model.slices.wind_*` | Calibrate |
| 4.7 | Calm and windy spells | Calm = 25% of seasonal average onshore (40% offshore); windy = 175% (160%). Equally likely; unrelated to sunshine | `model.slices.*_calm_contrast` | **Discuss** |

On 4.7: the calm winter-night slice lasts 1,095 hours a year. That is pessimistic on duration but optimistic on depth, since real windless winter spells run near 5% of average wind. The best fix is to calibrate these rules once against hourly data and keep the averages-only model.

## Step 5 · Technology costs

| # | Technology | Default | Resulting cost | Where | Basis |
|---|---|---|---|---|---|
| 5.1 | Cost of capital | 6% (SMRs 7%) | — | `wacc`, `smrWacc` | Judgement |
| 5.2 | Solar | €500/kW, 2% O&M, 25 years | €29/MWh in Andalucía, €51 in Belgium | `pv*` | Market |
| 5.3 | Onshore wind | €1,400/kW, 2.5% O&M, 25 years | €45/MWh at 37% capacity factor, €55 at 30% | `w*` | Market |
| 5.4 | Offshore wind | €2,600–3,600/kW by basin, 3% O&M | Not chosen at these costs | `offshore_basins.csv`, `off*` | Judgement |
| 5.5 | Batteries | €200/kWh, 4 hours, 15 years, 88% round trip | ~€67/MWh shifted when cycled daily | `bat*` | [BNEF](https://www.energy-storage.news/behind-the-numbers-bnef-finds-40-year-on-year-drop-in-bess-costs/): European turnkey systems $275/kWh in 2024; [stationary packs $70/kWh in 2025](https://www.solarserver.de/2025/12/10/bnef-studie-lithium-ionen-batteriespeicher-so-billig-wie-nie/) |
| 5.6 | Electrolysers | €1,800/kW, 3% O&M, 20 years; only capacity above flat running is costed | — | `el*` | [IEA 2026](https://www.argusmedia.com/en/news-and-insights/latest-market-news/2841836-green-h2-electrolyser-sector-enters-consolidation-iea): $1,900–2,500/kW outside China |
| 5.7 | Hydrogen storage, salt caverns | €35/MWh H₂ seasonal (≈€1.2/kg), €10 short-cycle; 3% loss per cycle | — | `cav*`, `h2StoreEff` | [EWI](https://ewi.uni-koeln.de/en/?p=17110): €0.66–1.75/kg |
| 5.8 | Hydrogen storage, tanks | €250/MWh seasonal, €30 short-cycle | — | `tank*` | Judgement |
| 5.9 | SMRs | €8,000/kW, 60 years, €110/kW-yr fixed, €12/MWh variable, 92% availability | €96/MWh baseload | `smr*` | [Arthur D. Little](https://www.nucnet.org/news/analysis-shows-competitive-lcoe-target-for-small-modular-reactors-7-3-2025): €52–119/MWh |
| 5.10 | Gas with carbon capture | €2,000/kW, 50% efficiency, 90% capture, €40/t CO₂ transport and storage, 90% availability | €127/MWh baseload at €40 gas | `ccs*` | Judgement |
| 5.11 | Unabated gas backup | €900/kW, 58% efficiency, ≤10% of each plant's energy | ~€107/MWh when running | `gas*`, `fossilCap` | Judgement |
| 5.12 | Fuel and carbon | Gas €40/MWh; CO₂ €100/t; 0.202 t CO₂/MWh of gas; methane leakage ignored | — | `gasPrice`, `co2`, `gasEf` | Planning choice; [TTF spot ~€88/MWh, 19 Oct 2026](https://www.soldionline.it/notizie/forex-commodities/gas-vicino-a-90-euro-cosa-sta-succedendo-al-ttf-095) |
| 5.13 | Grid import | €130/MWh flat; off | — | `impOn`, `impPrice` | — |
| 5.14 | Unserved load | €300/MWh, only if a site has no feasible mix | — | `model.plan.unserved` | — |

On 5.6: the €/MWh results for hydrogen-based industries are power-plus-flexibility costs, not full hydrogen costs.

## Step 6 · How each site's mix is optimised

| # | Assumption | Where | Verdict |
|---|---|---|---|
| 6.1 | The steady load is met in every slice; the electrolyser share over the year, with storage bridging the gaps | `mix.js` | Keep |
| 6.2 | SMRs and gas with capture run anywhere between zero and availability, with no minimum load or ramp limits. This flatters SMRs | `mix.js` | Revise: add a minimum load |
| 6.3 | Batteries move day-time energy into the following night only | `mix.js` | Keep |
| 6.4 | Surplus power is curtailed for free and earns nothing | `mix.js` | Decide |
| 6.5 | Up to 10% unabated gas still counts as decarbonised | `fossilCap` | **Decide**: 0% or 10% |
| 6.6 | Gas with carbon capture counts as clean | `ccsOn` | Decide |
| 6.7 | Solver check: 72 LPs match HiGHS exactly | `outputs/validation/lp_check.csv` | Done |

## Step 7 · Regional land and resources

| # | Assumption | Default | Where | Verdict |
|---|---|---|---|---|
| 7.1 | Land open to solar | 1.5% of non-urban land at 50 MW/km² = 0.75 MW/km² | `pvLand`, `pvDens` | Revise |
| 7.2 | Land open to wind | 2% at 20 MW/km² = 0.4 MW/km² | `wLand`, `wDens` | Revise |
| 7.3 | Exclusions | None: no protected areas, forest, slope, water or mountains | — | **Replace** (JRC ENSPRESO NUTS-2 potentials) |
| 7.4 | Offshore wind potential | 10 MW per km of coastline | `offDens` | Check |
| 7.5 | Reserve for local demand | 7 MWh per head from the region's own potential, before industry | `reserve` | **Decide** |
| 7.6 | When land runs out | The rest of the load uses the region's no-renewables mix | `plan.js` | Keep |

## Step 8 · The planner

| # | Assumption | Where | Verdict |
|---|---|---|---|
| 8.1 | Plants are indivisible and keep their size and demand | `plan.js` | Keep (design rule) |
| 8.2 | No relocation cost, product transport cost or cluster benefits. A €5/MWh premium cuts first-best moves from 216 to 190 plants | `relocPrem` | **Decide** a default |
| 8.3 | No cap on plants per region other than land (and the grid in second best) | `plan.js` | Keep |
| 8.4 | Plants in a region share its land; those that gain most from it are served first | `plan.js` | Keep |
| 8.5 | Greedy placement plus single-plant moves from two starts; not a proven optimum | `plan.js` | Check against an exact solver |
| 8.6 | Stay put: every plant at home with its best local mix | `plan.js` | Keep |

## Step 9 · Second-best constraints and policy inputs

| # | Assumption | Default | Where | Verdict |
|---|---|---|---|---|
| 9.1 | Substations | ENTSO-E map extract in PyPSA-Eur (several years old); ≥220 kV, counted per region | raw | Update |
| 9.2 | Grid headroom | 500 MW of new load per ≥330 kV node, 150 MW per 220 kV node, × (1 − congestion score) | `h380`, `h220`, `cCong` | Judgement |
| 9.3 | Big plants | A relocated plant above 300 MW average needs a ≥330 kV node | `bigMW` | Keep |
| 9.4 | Today's sites | Exempt from the grid constraint, even when electrification multiplies their load (Duisburg ≈3.3 GW) | `plan.js` | **Known issue K2** |
| 9.5 | Congestion scores | Author's stylised scores for 55 NUTS prefixes | `grid_congestion_scores.csv` | Replace with TSO maps where available |
| 9.6 | Existing renewables | Utility-scale only (powerplantmatching), built by 2025; output = MW × regional capacity factor (reservoir hydro 30%, run-of-river 45%); rooftop solar missing | raw, `model.existing_re_cf` | Revise |
| 9.7 | Renewables cap | New wind and solar ≤ 1.5 × existing output, at every site including home | `cRE`, `reK` | Keep |
| 9.8 | Ecosystem | 50% of each industry's capacity must stay; the planner picks movers; destinations must host the same industry (or any cluster) | `cEco`, `alpha`, `ecoMode` | Keep |
| 9.9 | Nuclear policy | New reactors barred in AT, DE, DK, ES, IE, LU, PT. Italy allowed since September 2026 ([BGEN](https://balkangreenenergynews.com/italy-allows-nuclear-power-four-decades-after-first-ban/)); Belgium repealed its phase-out in 2025 | `nuclear_policy.csv`, `smrBans` | Decide on Spain (a phase-out, not a ban) |
| 9.10 | Salt caverns | 30 NUTS prefixes (32 regions), stylised | `salt_caverns.csv` | Replace with Caglayan et al. (2020) |

---

## Known issues

These are kept as published so that the repository reproduces the live map.

- **K1 · Scrap steel route.** Choosing the scrap-based arc-furnace route applies its intensity to blast-furnace sites, because today's arc-furnace plants are not in the data.
- **K2 · Grid exemption at home.** Today's sites are exempt from the grid constraint although their load rises several-fold (9.4).
- **K3 · Idle plants.** Idle plants receive output (2.6).
- **K4 · Hydrogen storage cost.** Hydrogen carried between seasons is also charged the short-cycle withdrawal cost. The double count is small.
- **K5 · Placeholder inputs.** Weather (4.1), rooftop solar (9.6) and cement capacities (2.2) rest on the author's values or partial data.

## Open decisions (recommended defaults in brackets)

1. **Energy transport (0.3):** keep "move plants, not electrons", but add an optional transmission cost per MWh per 100 km so staying put can draw on neighbouring regions.
2. **Cost year (0.4):** [2035], with all costs aligned to it.
3. **Unabated gas (6.5):** [0% by default], 10% as a sensitivity.
4. **Relocation premium (8.2):** [€5/MWh], with a higher, separate one for cement to stand in for transport.
5. **Idle plants (2.6):** [exclude by default].
6. **Replace placeholder data (4.1, 7.3, 2.2):** EMHIRES or Renewables.ninja averages, JRC ENSPRESO potentials, a current cement plant list.
