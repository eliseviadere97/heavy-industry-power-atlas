# Heavy Industry Power Atlas

**Where clean power would put Europe's heavy industry.** Decarbonising the EU's steel, cement, ammonia, chemicals and aluminium plants needs about 617 TWh of clean electricity a year, roughly a quarter of what the EU uses today. This repository holds the data, code and interactive map behind one question: if a social planner could move whole plants, where would it put them, and what do today's grid, renewables and industrial clusters cost us in forgone savings?

The map opens on three scenarios:

| Scenario (default settings) | Cost of power | A year | Plants that move | Regions used |
|---|---|---|---|---|
| **Stay put**: every plant at home, each with its best local power mix | €96/MWh | €59.1bn | 0 of 230 | 129 |
| **Second best**: planner bound by grid, existing-renewables and cluster constraints | €87/MWh | €53.6bn | 77 (50% of load) | 102 |
| **First best**: planner with a free hand, bound only by land and weather | €73/MWh | €44.8bn | 216 (96% of load) | 28 |

The first best moves most plants to Spain and Greece and runs them on solar and onshore wind, with batteries and hydrogen storage. Staying put leans on small modular reactors (SMRs) and gas with carbon capture. Of the three constraints, sticking to today's clusters does almost all the damage; grid headroom barely binds. Full tables are in [`outputs/results/`](outputs/results/).

> **Status.** A screening model for policy analysis, not an investment tool. Several inputs are the author's own estimates and are flagged as such: the weather anchors, the hand-compiled plant lists, congestion scores and salt-cavern regions. See [`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md) before quoting any number.

---

## What the model does

1. **Sizes demand.** Output × electricity intensity of the net-zero route, per industry (`config/model_config.json` → `model.industries`). Output is shared across today's 230 plants in proportion to capacity. A plant keeps its size and demand wherever it goes.
2. **Optimises a local power mix for every industry in every region.** A small linear programme chooses solar, onshore and offshore wind, 4-hour batteries, extra electrolysers with hydrogen storage, SMRs, gas with carbon capture and capped unabated gas, to serve the plant's load at least cost. Weather enters only as **annual averages**: the year is cut into eight slices (winter/summer × windy/calm × day/night), whose output is derived from the averages with fixed shape rules.
3. **Places whole plants.** A planner assigns each plant to a NUTS-2 region to minimise the total cost of power. Plants in the same region share its land for wind and solar.
4. **Adds constraints for the second best**, each of which can be switched on or off: stay near strong substations (grid), build where renewables already are, stick to today's clusters.
5. **Publishes everything as one interactive page.** Every default can be changed in the browser, and the page re-solves about 700 local mixes and three plans in under a second.

The method is written out in full in [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## Repository layout

```
heavy-industry-power-atlas/
├── run_all.py                     one command: data prep → model → solver check → web page
├── config/model_config.json       EVERY default in one place (data-prep settings and model assumptions)
├── data/
│   ├── raw/                       files exactly as downloaded, pinned to source commits (see sources.json)
│   ├── manual/                    hand-compiled inputs, one CSV each, with source and verification columns
│   ├── processed/                 data.json (read by the model and the map), regions.csv, plants.csv
│   └── DATA_MANIFEST.md           provenance, checksums, licences and field dictionary
├── src/
│   ├── data_prep/                 Python: raw + manual → processed (9 documented steps), fetch_raw.py
│   ├── model/                     JavaScript optimisation code shared by the page and the headless runner
│   │   ├── mix.js                 least-cost local power mix (linear programme per industry × region)
│   │   └── plan.js                relocation planner (stay put / second best / first best)
│   ├── run/run_scenarios.js       headless runs → outputs/results/*.csv, including sensitivities
│   ├── validation/validate_lp.py  re-solves a sample of the LPs with HiGHS and checks the optimum
│   └── site/                      template.html + build_site.py → site/index.html
├── outputs/
│   ├── results/                   scenario_summary, plant_allocation, local_mix_by_region, region_load, sensitivities
│   ├── validation/                lp_check.csv (browser solver vs HiGHS)
│   └── qa_report.md               counts and totals from the data preparation
├── docs/
│   ├── METHODOLOGY.md             equations, algorithms, outputs
│   └── ASSUMPTIONS.md             every assumption, numbered, with value, basis, and verdict
└── .github/workflows/deploy.yml   rebuilds and publishes the map on every push
```

## Run it on your computer

You need Python 3.12+ and Node.js 18+.

```bash
pip install -r requirements.txt
npm ci
python run_all.py
```

The run takes about 20 seconds. Then open `site/index.html` in a browser. To check the raw files against their recorded checksums, run `python src/data_prep/fetch_raw.py --check-only`. To re-download them from their pinned sources, drop `--check-only`.

## Publish the map from GitHub

The workflow in `.github/workflows/deploy.yml` rebuilds everything from the raw data and publishes the map with GitHub Pages each time you push to `main`.

1. On github.com, create a new **empty** repository, e.g. `heavy-industry-power-atlas`. Don't add a README, `.gitignore` or licence.
2. From this folder:
   ```bash
   git init
   git add .
   git commit -m "Heavy Industry Power Atlas: data, code and map"
   git branch -M main
   git remote add origin https://github.com/<your-username>/heavy-industry-power-atlas.git
   git push -u origin main
   ```
   (or GitHub Desktop: *Add local repository* → *Publish repository*).
3. In the repository: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
4. Open the **Actions** tab, then **Build and publish the atlas → Run workflow**. Pushes after this one trigger it automatically.
5. The map appears at `https://<your-username>.github.io/heavy-industry-power-atlas/`. It links back to the repository automatically. Each run also stores the result tables as a downloadable *results* artifact.

The largest file, `data/raw/powerplantmatching/powerplants.csv` (38 MB), is under GitHub's 100 MB limit, so Git LFS isn't needed.

## Change an assumption

- **Model assumptions** (costs, land shares, constraint settings, industry outputs and intensities): edit `config/model_config.json`, then run `python run_all.py --skip-data`.
- **Hand-compiled inputs** (plants, weather anchors, congestion scores, nuclear policy, salt caverns): edit the CSV in `data/manual/`, then run `python run_all.py`.
- **New raw data**: add the file to `data/raw/`, record it in `data/raw/sources.json`, and read it in the relevant step of `src/data_prep/steps.py`.

Each assumption carries an ID in `docs/ASSUMPTIONS.md` (for example 5.9 for the SMR cost), which names the config key or file that holds it.

## Data sources

| Data | Provider | Used for |
|---|---|---|
| NUTS 2024 regions, boundaries, countries | Eurostat GISCO via [Nuts2json](https://github.com/eurostat/Nuts2json) | regions, areas, coastlines, map |
| Power plants | [powerplantmatching](https://github.com/PyPSA/powerplantmatching) | existing wind, solar and hydro |
| Transmission grid; ammonia plants | [PyPSA-Eur](https://github.com/PyPSA/pypsa-eur) (ENTSO-E map extract) | substations, lines; ammonia sites |
| EU ETS cement kilns; chlor-alkali sites | [Tröndle et al. (2019)](https://github.com/timtroendle/possibility-for-electricity-autarky) | cement sites; chemical clusters |
| Towns above 15,000 people | GeoNames via geonamescache 3.0.2 | population and urban share |
| Steelworks, smelters, crackers, cement and ammonia gaps, national population, weather anchors, offshore basins, congestion, nuclear policy, salt caverns | author compilation, flagged per row | see `data/manual/` |

Cost assumptions draw on BNEF (batteries), the IEA (electrolysers), EWI (salt-cavern storage) and Arthur D. Little (SMRs); details and links are in `docs/ASSUMPTIONS.md`. Administrative boundaries © EuroGeographics. GeoNames data are CC BY 4.0. Other providers' terms are linked in `data/DATA_MANIFEST.md`.

## Main limitations

1. **Electricity doesn't travel between regions.** Plants run only on power from their own region; moving the plant is the only way to reach better sun and wind.
2. **Weather averages are placeholders.** They are the author's estimates calibrated to PVGIS and the Global Wind Atlas, not downloaded series. Replace them with EMHIRES or Renewables.ninja NUTS-2 averages before publication.
3. **Moving a plant is free by default.** There is no product transport or relocation cost. A €5/MWh premium cuts first-best moves from 216 to 190 plants and raises its cost to €77/MWh (see `sensitivities.csv`).
4. **The variability rules are stylised.** Eight slices built from averages size the firming; windless winter spells are long but not deep enough.
5. **Land is a flat share of non-urban area with no exclusions**, and each region must cover its own households first.
6. **The planner is a heuristic** (greedy plus local search), not a proven optimum. The local-mix LPs, by contrast, match HiGHS exactly.

## Author

Elise Viadere, Centre for European Reform. Model and code built with Claude (Anthropic), October 2026.
