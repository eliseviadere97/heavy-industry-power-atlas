# Methodology

The model asks one question. If a social planner could place each of today's heavy-industry plants anywhere in the EU27, Norway, Switzerland or the UK, powering each from the least-cost clean mix its region allows, where would the plants go? And how much do real-world constraints cost? It runs in two optimisation steps, inside a four-stage pipeline:

| Stage | Code | Output |
|---|---|---|
| A · Data preparation | `src/data_prep/run_data_prep.py` (steps 1–7 in `steps.py`); weather tables built once by `fetch_weather.py` | `data/processed/`, `outputs/qa_report.md`, `outputs/review/plant_lists_for_review.xlsx` |
| B · Model runs | `src/run/run_scenarios.js` using `src/model/mix.js` (step 1) and `plan.js` (step 2) | `outputs/results/*.csv` |
| C · Checks | `src/validation/validate_lp.py` (step 1), `validate_plan.py` (step 2) | `outputs/validation/` |
| D · Web page | `src/site/build_site.py` | `site/index.html`, `outputs/artifact.html` |

All parameters live in `config/model_config.json`; names below match its keys. The basis for each value is in `docs/ASSUMPTIONS.md`.

---

## 1. Data preparation

1. **Regions.** NUTS-2 polygons and label points from Eurostat GISCO (Nuts2json): NUTS 2024 for the EU27, Norway and Switzerland; NUTS 2016 for the UK. 288 regions; outermost regions, Ceuta, Melilla and Svalbard dropped.
2. **Population.** Eurostat demo_r_d2jan (1 January 2024; UK 2019; Northern Ireland 2018). Density $= \text{pop}_r / A_r$.
3. **Weather.** Monthly solar capacity factors $\text{pv}_{r,m}$ from PVGIS and monthly day/night onshore wind capacity factors $\text{wd}_{r,m}, \text{wn}_{r,m}$ from EMHIRES (`data/derived/`, see §1.1).
4. **Grid.** AC substations ≥330 kV in service, counted per region ($n^{330}_r$), snapping up to 5 km. Lines ≥220 kV kept for display.
5. **Plants.** Steelworks, smelters and crackers from hand-compiled lists; cement kilns from EU ETS records (output = verified emissions ÷ 0.83 t CO₂/t clinker) plus additions; ammonia plants from PyPSA-Eur with gaps filled. Sites snap up to 25 km and must fall in their own country. Output: $o_p = K_p \cdot u_i$ for nameplate capacity $K_p$ and sector utilisation $u_i$; ETS cement values are output already; idle and closed plants produce nothing.
6. **Policy.** National bar on new reactors.
7. **Export.** Processed files, simplified map geometry, and the plant review spreadsheet.

### 1.1 Weather tables

- **Solar.** For each region, up to six points on a regular grid inside the polygon. PVGIS 5.3 (`PVcalc`, PVGIS-ERA5, 2005–2023) returns the monthly yield $E_m$ (kWh/kWp) of a fixed, optimally tilted system with 14% losses. $\text{pv}_{r,m} = \overline{E_m} / (24\, d_m)$.
- **Wind.** EMHIRES (JRC, June 2019 release, NUTS 2016 codes) gives hourly capacity factors per region for 1986–2015, for the wind fleet installed at the end of 2015. Hours 06–18 UTC count as day. Each model region takes the area-weighted mean of the EMHIRES regions it overlaps.

## 2. Demand

For plant $p$ in sector $i$ with output $o_p$ (kt) and intensity $e_i$ (MWh/t):

$$E_p = o_p\, e_i / 1000 \;\text{TWh/yr},\qquad L_p = E_p\cdot 10^6 / 8760 \;\text{MW of average load}.$$

$E_p$ is the same wherever the plant goes. A share $h_i$ of the load runs through electrolysers ($h$ = 0.75 steel, 0.9 ammonia, 0 otherwise) and can follow the weather if hydrogen can be stored.

## 3. Step 1: the local power mix (`src/model/mix.js`)

For each flexible share $h$ and region $r$, a linear programme finds the least-cost way to serve **1 MW of average load** from the plant's own assets. The objective is therefore in €/MWh of plant demand.

### 3.1 Slices

Twenty-four slices $s = (m, \text{day/night})$, each lasting $H_s = 12\, d_m$ hours ($d_m$ = days in month $m$; February 28.25), with weight $w_s = H_s / \sum H$:

$$\text{pv}_s = \min(1,\ 2\,\text{pv}_{r,m}) \text{ by day},\ 0 \text{ at night};\qquad \text{on}_s = \text{wd}_{r,m} \text{ or } \text{wn}_{r,m}.$$

### 3.2 Costs

With one cost of capital $w$ for all technologies, the annualised fixed cost per MW, per MWh of the 1 MW load, is

$$\alpha = \frac{\text{capex}\cdot 1000\,\big(\text{CRF}(w,n)+\text{om}\big)}{8760},\qquad \text{CRF}(w,n)=\frac{w}{1-(1+w)^{-n}}.$$

SMRs and gas with capture carry fixed O&M in €/kW-yr and a variable cost:

$$v_{ccs} = \frac{p_{gas}}{\eta_{ccs}} + \frac{0.202}{\eta_{ccs}}\big(\kappa\,\text{TS} + (1-\kappa)\,p_{CO_2}\big) + \text{VOM}.$$

Hydrogen storage is costed per unit of volume (€/kWh H₂, converted with 0.63 MWh H₂ per MWh electricity).

### 3.3 Programme

Variables (all ≥ 0, per MW of load): capacities $x^{pv}, x^{on}, x^{bat}, x^{el}$ (electrolyser above flat running), $V$ (hydrogen storage, days of 1 MW), $x^{smr}, x^{ccs}$; dispatch $n_s, g_s$; battery charge $bc_m$ by day and discharge $bd_m$ by night; electrolyser draw $e_s$; hydrogen into and out of storage $c_s, d_s$; storage level $\ell_s$.

$$\min\ \sum_t \alpha_t x^t + \alpha_V V + \sum_s w_s\,(v_{smr} n_s + v_{ccs} g_s)$$

subject to, for each slice $s$:

1. **Energy balance** (curtailment free): $x^{pv}\text{pv}_s + x^{on}\text{on}_s + n_s + g_s + bd_s - bc_s - e_s \ge 1-h$.
2. **Batteries:** $bd_m = 0.88\, bc_m$, $bd_m \le \tfrac{4}{12} x^{bat}$.
3. **Firm plant:** $n_s \le 0.92\, x^{smr}$ (only where new reactors are allowed); $g_s \le 0.9\, x^{ccs}$.
4. **Hydrogen** (if $h>0$ and storage is allowed): $e_s - c_s + d_s = h$ (flat downstream use); $e_s \le h + x^{el}$; $\ell_s = \ell_{s-1} + \tfrac{H_s}{24}(0.97\, c_s - d_s)$ around the year; $\ell_s \le V$. Without storage, electrolysers run flat and the whole load is steady.

The **no-new-renewables fallback** is the same programme without solar, wind, batteries or flexible electrolysers.

## 4. Land

$$\text{Land}_r = A_r\,\Big(1-\min\big(0.95,\ \tfrac{\text{pop}_r}{3000\,A_r}\big)\Big)\times 0.035 \;\text{km}^2,$$

shared by solar (50 MW/km²) and wind (20 MW/km²). Plant $p$'s renewables mix in region $j$ needs $k_{pj} L_p$ km², with $k_{pj} = x^{pv}/50 + x^{on}/20$.

## 5. Step 2: plant placement (`src/model/plan.js`)

Choose a region $j(p)$ for every plant and the share $f_p$ of its load served by the renewables mix to minimise

$$\sum_p E_p\Big[f_p\, c^{A}_{h_p,j(p)} + (1-f_p)\, c^{B}_{h_p,j(p)}\Big]$$

where $c^A$ is the local-mix cost and $c^B$ the fallback cost, subject to $\sum_{p \in j} f_p\, k_{pj} L_p \le \text{Land}_j$.

**Within a region** the land goes to plants in order of saving per km², $(c^B - c^A)/k$: a fractional knapsack, which is optimal for one shared resource.

| | Stay put | First best | Second best |
|---|---|---|---|
| Allowed sites | home only | any region | home, or a region passing the ticked constraints |
| Grid | — | — | destination has ≥1 substation ≥330 kV |
| Clusters | — | — | destination hosts the same sector; moved output ≤ $(1-\alpha)$ of each sector's output |

**Heuristic.** Two starts (all plants at home; greedy placement in order of potential saving), each followed by local search: single-plant moves, then pairwise swaps between land-limited regions, repeated until nothing improves. Where part of each sector must stay, plants are ranked by saving per tonne of the moving allowance.

**Exact check.** `validate_plan.py` writes the same problem as a mixed-integer programme ($x_{pj}$ binary, $y_{pj} = f_p x_{pj}$ continuous, one land row per region, one allowance row per sector) and solves it with HiGHS for up to 120 s per scenario. It reports the heuristic's gap to the proven lower bound and fails the pipeline above 1%.

## 6. Outputs (`outputs/results/`)

| File | One row per | Main columns |
|---|---|---|
| `scenario_summary.csv` | scenario | €/MWh, €bn/yr, plants moved, share of load moved, regions used, generation shares, storage throughput |
| `plant_allocation.csv` | plant × scenario | home and site region, moved, output, demand, €/MWh there and if it stays, share on the renewables mix |
| `local_mix_by_region.csv` | region × sector | best mix cost, fallback cost, generation shares, capacities and land per MW of load |
| `region_load.csv` | region | load and land used in each scenario, land available |
| `sensitivities.csv` | case × scenario | constraints one at a time; technologies, prices and cost of capital |
