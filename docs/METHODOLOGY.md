# Methodology

The model asks one question. If a social planner could place each of today's heavy-industry plants anywhere in the EU27, powering each from the least-cost clean mix its region allows, where would the plants go? And how much do real-world constraints cost? It runs in four steps:

| Step | Code | Output |
|---|---|---|
| A · Data preparation | `src/data_prep/run_data_prep.py` (steps 1–9 in `steps.py`) | `data/processed/data.json`, `regions.csv`, `plants.csv`, `outputs/qa_report.md` |
| B · Model runs | `src/run/run_scenarios.js` using `src/model/mix.js` and `plan.js` | `outputs/results/*.csv` |
| C · Solver check | `src/validation/validate_lp.py` | `outputs/validation/lp_check.csv` |
| D · Web page | `src/site/build_site.py` | `site/index.html` |

All parameters live in `config/model_config.json`; parameter names below match its keys. Monetary values are in euros; energy demand is in TWh a year.

---

## 1. Spatial unit and data preparation

The spatial unit is the NUTS-2 region (2024 version): 234 regions across the EU27, excluding the outermost regions, Ceuta and Melilla. Data preparation builds one record per region:

1. **Regions.** Polygons and label points from Eurostat GISCO; area from the label-point file; coordinates projected to ETRS89-LAEA (EPSG:3035).
2. **Population.** Each GeoNames town above 15,000 people is assigned to the region it falls in, giving town population $T_r$. With national population $P_c$ and national town total $T_c$, the residual $\text{Res}_c = \max(P_c - T_c,\; 0.15\,P_c)$ is spread by area:

   $$\text{pop}_r = s_c T_r + \text{Res}_c \frac{A_r}{A_c},\qquad s_c=\frac{P_c-\text{Res}_c}{T_c},\qquad \text{urb}_r=\frac{s_c T_r}{\text{pop}_r}.$$

3. **Weather (annual averages).** Solar yield and onshore wind capacity factor at each region's label point come from inverse-distance weighting over the 5 nearest of 157 anchor points, with weights $w_k=\max(d_k,15\text{ km})^{-2}$. The solar capacity factor is yield ÷ 8,760. *The anchors are author estimates and should be replaced with EMHIRES or Renewables.ninja NUTS-2 averages* (see ASSUMPTIONS 4.1).
4. **Coast and sea basin.** Coastline length is the sum of coastal NUTS-3 boundary segments (1:20M) belonging to the region. Each segment's midpoint is assigned to a basin (North Sea, Baltic, Atlantic, Mediterranean, Black Sea) by fixed latitude/longitude rules. The region takes the basin with the longest coastline, and with it the offshore capacity factor $\text{coff}_r$ and capex $\text{kxoff}_r$ for that basin.
5. **Grid.** AC substations in service are counted per region, split into ≥330 kV ($n^{380}_r$) and 220–300 kV ($n^{220}_r$), snapping up to 5 km to the nearest region.
6. **Existing renewables.** Installed solar, onshore wind, offshore wind (snapped up to 150 km), reservoir and run-of-river hydro, commissioned by 2025 and still running. Annual output:

   $$G_r = 8760\,\big(\text{MW}^{pv}\text{CF}^{pv}_r + \text{MW}^{on}\text{CF}^{on}_r + \text{MW}^{off}\text{coff}_r + 0.30\,\text{MW}^{res} + 0.45\,\text{MW}^{ror}\big)/10^6 \text{ TWh}.$$

7. **Plants.**
   - Steelworks, smelters and crackers come from the hand-compiled lists.
   - Cement kilns are taken from EU ETS records, with capacity = 2014 (else 2013) verified emissions ÷ 0.83 t CO₂ per t clinker, plus hand-compiled additions.
   - Ammonia plants come from the PyPSA-Eur list, with gaps filled.
   - Chlor-alkali sites mark chemical clusters only.
   - Sites are snapped up to 25 km and must fall in their own country.
8. **Policy layers.**
   - Grid congestion score (longest matching NUTS prefix wins; 0 if unlisted).
   - Salt-cavern flag.
   - National bar on new reactors.
9. **Export.** Writes the processed files and simplifies the map geometry.

## 2. Demand

For industry $i$ with output $Q_i$ (Mt) and route intensity $e_i$ (MWh/t), demand is $D_i = Q_i e_i$ TWh. Each of today's plants $p$ in industry $i$ with capacity $K_p$ carries

$$E_p = \frac{K_p}{\sum_{q\in i} K_q}\,D_i \;\text{TWh/yr},\qquad L_p = \frac{E_p \cdot 10^6}{8760}\;\text{MW of average load}.$$

$E_p$ is the same wherever the plant goes: plants move whole. Each route has a **flexible share** $h_i$, the part of the load that runs through electrolysers and can follow the weather if hydrogen can be stored. The rest, $1-h_i$, is steady.

| Industry | $Q_i$ default | Route | $e_i$ (MWh/t) | $h_i$ | $D_i$ (TWh) |
|---|---|---|---|---|---|
| Steel | 70 Mt | Hydrogen DRI + electric arc furnace | 3.5 | 0.75 | 245 |
| Cement | 118 Mt clinker | Electrified kiln + carbon capture | 1.3 | 0 | 153 |
| Ammonia | 13 Mt | Electrolytic hydrogen + Haber-Bosch | 10.5 | 0.9 | 137 |
| Chemicals | 30 Mt HVC | Electric crackers (heat only) | 2.2 | 0 | 66 |
| Aluminium | 1.0 Mt | Inert anodes + electrified alumina | 16.5 | 0 | 17 |

## 3. The local power mix (`src/model/mix.js`)

For each flexible share $h$ and region $r$, a linear programme finds the least-cost way to serve **1 MW of average load** (8,760 MWh/yr). The objective is therefore in €/MWh of plant demand.

### 3.1 Eight slices from annual averages

The year is split into eight equal slices, $s \in \{\text{winter},\text{summer}\}\times\{\text{windy},\text{calm}\}\times\{\text{day},\text{night}\}$, each with weight 1/8 (1,095 hours). With latitude $\phi_r$:

$$a_r=\text{clip}\big(0.26+0.0175(\phi_r-37),\,0.2,\,0.8\big),\qquad b_r=\text{clip}\big(0.15+0.004(\phi_r-37),\,0.1,\,0.3\big)$$

$$\text{pv}_s = \min\!\big(0.95,\; 2\,\text{CF}^{pv}_r(1\pm a_r)\big)\ \text{by day } (+\text{summer}, -\text{winter}),\quad 0 \text{ at night}$$

$$\text{on}_s = \min\!\big(0.95,\; \text{CF}^{on}_r(1\pm b_r)(1\pm 0.75)\big),\qquad \text{off}_s = \min\!\big(0.95,\; \text{coff}_r(1\pm b_r)(1\pm 0.6)\big)$$

where $+b_r$ applies in winter and $+0.75$ (or $+0.6$) in windy slices. Apart from the 0.95 cap, the slice values average back to the annual capacity factors. Parameters: `model.slices`.

### 3.2 Costs

Annualised fixed cost per MW of capacity, expressed per MWh of the 1 MW load:

$$\alpha = \frac{\text{capex}\cdot 1000\,\big(\text{CRF}(w,n)+\text{om}\big)}{8760},\qquad \text{CRF}(w,n)=\frac{w}{1-(1+w)^{-n}}.$$

- **SMRs:** $\alpha_{smr} = (\text{capex}\cdot1000\cdot\text{CRF}(7\%,60) + \text{FOM}\cdot1000)/8760$, plus variable cost $v_{smr}$.
- **Gas with capture:**

  $$v_{ccs} = \frac{p_{gas}}{\eta_{ccs}} + \frac{0.202}{\eta_{ccs}}\big(\kappa\,\text{TS} + (1-\kappa)\,p_{CO_2}\big) + 4,$$

  with capture rate $\kappa$ and transport-and-storage cost TS.
- **Unabated gas:**

  $$v_{gas} = \frac{p_{gas}}{\eta_{gas}} + \frac{0.202}{\eta_{gas}}\,p_{CO_2} + 3.$$

- **Batteries:** priced per MW of a 4-hour system (capex per kWh × 4).

### 3.3 Variables (all ≥ 0, per MW of average load)

- **Capacities:**
  - $x^{pv}, x^{on}, x^{off}$: solar, onshore and offshore wind.
  - $x^{bat}$: 4-hour battery.
  - $x^{el}$: electrolyser capacity *above* flat running. Electrolysers needed anyway cost the same everywhere and are left out.
  - $x^{smr}, x^{ccs}, x^{gas}$: dispatchable plant.
- **Dispatch in each slice $s$:**
  - $n_s, g_s, u_s$: SMR, gas with capture, unabated gas.
  - $m_s$: grid import (off by default).
  - $e_s$: electrolyser consumption.
  - $c_s, d_s$: hydrogen into and out of storage.
- **Batteries:** charge $bc_k$ by day and discharge $bd_k$ the following night, for each season–wind pair $k$.
- **Seasonal hydrogen transfers:** $q_{SW}, q_{WS}$.

### 3.4 Programme

$$\min\; \sum_t \alpha_t x^t + \tfrac18\sum_s\big(v_{smr}n_s+v_{ccs}g_s+v_{gas}u_s+p_{imp}m_s+0.7\,c^{short}d_s\big) + \tfrac18\,0.7\,c^{seas}(q_{SW}+q_{WS})$$

subject to, for every slice $s$:

1. **Energy balance** (curtailment is free):

   $$x^{pv}\text{pv}_s + x^{on}\text{on}_s + x^{off}\text{off}_s + n_s+g_s+u_s+m_s+bd_s-bc_s-e_s \;\ge\; 1-h.$$

2. **Batteries:** $bd_k = 0.88\,bc_k$ and $bd_k \le \tfrac{4}{12}x^{bat}$. A battery moves day-time energy into the following night. It cannot bridge a calm spell.
3. **Dispatchable plant:**
   - $n_s \le 0.92\,x^{smr}$; $g_s \le 0.9\,x^{ccs}$; $u_s\le x^{gas}$.
   - Unabated gas is capped at a share of annual energy: $\tfrac18\sum_s u_s \le 0.10$.
4. **Electrolysers and hydrogen** (only if $h>0$):
   - $e_s \le h + x^{el}$ and $e_s - c_s + d_s = h$, so downstream hydrogen use is flat.
   - For each season $\sigma$: $\sum_{s\in\sigma}(0.97\,c_s - d_s) + 0.97\,q_{\text{in},\sigma} - q_{\text{out},\sigma} = 0$.
   - Without hydrogen storage, $e_s = h$.
   - Storage costs $c^{short}, c^{seas}$ are per MWh of hydrogen shifted; the factor 0.7 converts MWh of electricity into MWh of hydrogen. Regions with salt caverns use the cavern costs, the rest the tank costs.
5. **Availability:** SMRs only where allowed (the technology switch and, if ticked, national policy); offshore wind only in coastal regions; each technology only if its switch is on.

The **no-new-renewables fallback** is the same programme with $x^{pv}=x^{on}=x^{off}=x^{bat}=x^{el}=0$. It prices any part of a plant's load that its region cannot cover with new wind and solar.

### 3.5 Reported quantities

- **Cost** $c_{hr}$ (€/MWh).
- **Capacities** per MW of load.
- **Energy shares by source.** Renewable output net of curtailment: in each slice, the energy not met by dispatchable plant or batteries is drawn from solar and wind in proportion to their availability. Shares are normalised to sum to one.
- **Storage throughput:** battery discharge and hydrogen withdrawn, per MWh of demand.
- **Renewable energy available per MW of load,** used for the existing-renewables cap.

## 4. Regional resources (`regionResources` in `plan.js`)

**Free land.** $A^{free}_r = A_r\big(1-\min(0.95,\ \text{pop}_r\,\text{urb}_r/3000/A_r)\big)$.

**Potentials.**

$$\overline{PV}_r = 0.015\cdot 50\cdot A^{free}_r,\qquad \overline{ON}_r = 0.02\cdot 20\cdot A^{free}_r,\qquad \overline{OFF}_r = 10\cdot\text{coast}_r \text{ (MW)}.$$

**Reserve for local demand.** Each region first powers its own households and services at 7 MWh per head. All three potentials are scaled by

$$\max\!\Big(0,\ 1 - \frac{\text{pop}_r \cdot 7}{8.76\cdot10^{-3}\,(\overline{PV}_r\text{CF}^{pv}_r+\overline{ON}_r\text{CF}^{on}_r+\overline{OFF}_r\text{coff}_r)\cdot 10^6}\Big).$$

**Second-best caps.**
- New wind and solar for industry may not exceed $k\,G_r$ TWh, with $k=1.5$.
- Relocated load may not exceed

  $$H_r = 8.76\cdot10^{-3}\,(500\,n^{380}_r + 150\,n^{220}_r)\,\max(0,1-\text{cong}_r) \text{ TWh}.$$

## 5. The relocation planner (`plan` in `plan.js`)

**Problem.** Choose a region $j(p)$ for every plant $p$ to minimise

$$\sum_p E_p\Big[f_p\,c^{A}_{h_p,j(p)} + (1-f_p)\,c^{B}_{h_p,j(p)}\Big] + \rho\,E_p\,\mathbf 1[j(p)\neq \text{home}_p]$$

where:
- $c^A$ is the local-mix cost and $c^B$ the no-new-renewables cost;
- $\rho$ is the relocation premium (default 0);
- $f_p$ is the share of plant $p$'s local-mix needs that its region can still supply.

**Packing within a region.** Plants are served in order of their gain from local renewables, $c^B - c^A$ (largest first, ties broken by size). Each takes
$$f_p=\min_k\big(1,\ \text{remaining}_k/\text{need}_{p,k}\big)$$
over $k \in$ {solar MW, onshore MW, offshore MW, existing-renewables allowance TWh}, with needs equal to the local-mix capacities × $L_p$.

**Scenarios.**

| | Stay put | First best | Second best |
|---|---|---|---|
| Allowed sites | home only | any region | home, or any region passing the ticked constraints |
| Grid | — | — | relocated load ≤ $H_j$; plants above 300 MW average need $n^{380}_j \ge 1$ |
| Existing renewables | — | — | new wind/solar ≤ $k\,G_j$ at every site, home included |
| Ecosystem | — | — | destination already hosts the same industry (chemicals: also chlor-alkali), or any cluster; per industry, moved capacity ≤ $(1-\alpha)\sum K$, and the planner picks which plants move |

**Algorithm.** A heuristic, run twice from different starts; the cheaper result is kept.

1. *Start 1:* all plants at home.
2. *Start 2:* greedy construction. Plants in decreasing size, each placed where it raises total cost least.
3. *Local search* from each start. For each plant, largest first, evaluate a move to every allowed region, re-packing both regions exactly, and take the best improving move. Repeat up to 12 passes, or until nothing improves.

At default settings the three scenarios solve in under a second. The result is a good feasible solution but **not a proven optimum**: there are no swaps or multi-plant moves. The local-mix LPs, by contrast, are solved exactly.

## 6. Validation

- **Solver check.** `validate_lp.py` re-solves 72 local-mix programmes (12 regions × 3 flexible shares × with/without new renewables) with HiGHS. The pipeline fails if any optimum differs by more than €0.01/MWh. Current worst difference: 0.00000.
- **Data checks.** `outputs/qa_report.md` lists counts and totals from every data-preparation step (regions, towns placed, substations, installed renewables, plant capacity by industry, unplaced sites).
- **Reproducibility.**
  - Raw files carry SHA-256 checksums; the workflow verifies them before each build.
  - The refactored data pipeline reproduces, field for field, the dataset behind the map first published on 22 October 2026.

## 7. Outputs (`outputs/results/`)

| File | One row per | Main columns |
|---|---|---|
| `scenario_summary.csv` | scenario | €/MWh, €bn/yr, plants moved, share of load moved, regions used, generation shares, storage throughput |
| `plant_allocation.csv` | plant × scenario | home and site region, moved, demand (TWh), €/MWh there and if it stays, share served by the local renewables mix, generation shares |
| `local_mix_by_region.csv` | region × industry | best local-mix cost, no-renewables cost, generation shares, capacities per MW of load, storage throughput |
| `region_load.csv` | region | load placed in each scenario, renewable potential left after local demand |
| `sensitivities.csv` | case × scenario | constraints one at a time; technology and price variations |
