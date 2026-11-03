# Heavy Industry Power Atlas

**Where clean power would put Europe's heavy industry.** Decarbonising the steel, cement, ammonia, chemicals and aluminium plants of the EU27, Norway, Switzerland and the UK needs about 654 TWh of clean electricity a year. This repository holds the data, code and interactive map behind one question: if a social planner could move whole plants, each powered by its own least-cost clean mix, where would it put them, and what do today's grid and industrial clusters cost us in forgone savings?

The interactive map compares three scenarios. The table shows all five sectors together at the default settings (the page itself opens on steel only; switch the other sectors on with the chips above the map):

| Scenario | Cost of power | A year | Plants that move | Regions used |
|---|---|---|---|---|
| **Stay put**: every plant at home, each with its own least-cost mix | €88/MWh | €57.4bn | 0 of 259 | 147 |
| **Second best**: moves only to regions with a ≥330 kV substation that already host the sector; half of each sector stays | €73/MWh | €47.5bn | 130 (50% of load) | 72 |
| **First best**: planner with a free hand, bound only by land and weather | €62/MWh | €40.3bn | 258 (100% of load) | 17 |

The first best moves most plants to Norway and Ireland and runs them on onshore wind. Staying put leans on SMRs and gas with carbon capture where sun and wind are poor. Of the two constraints, sticking to today's clusters does almost all the damage; the grid condition barely binds. Full tables are in [`outputs/results/`](outputs/results/).

> **Status.** A screening model for policy analysis, not an investment tool. Read [`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md) before quoting any number. Three assumptions matter most: each plant is powered behind the meter, with no grid import; monthly day/night weather averages hide calm spells, which makes wind look firmer than it is; and the EMHIRES wind data reflect the 2015 turbine fleet. The plants added for Norway, Switzerland and the UK are not yet verified.

---

## What the model does

1. **Sizes demand per site.** Each plant's output today (capacity × a sector utilisation rate) × the electricity per tonne of its decarbonised process (`config/model_config.json` → `model.sectors`). A plant keeps its output and demand wherever it goes.
2. **Step 1: optimises a local power mix for every sector in every region.** A linear programme chooses solar, onshore wind, four-hour batteries, extra electrolysers with hydrogen storage, SMRs and gas with carbon capture to serve the plant's load in 24 slices (12 months × day and night), from PVGIS solar and EMHIRES wind data. Supply is behind the meter: no grid import, no unabated gas.
3. **Step 2: places whole plants.** A planner assigns each plant to a NUTS-2 region to minimise the total cost of power. Plants in a region share its land for solar and wind.
4. **Adds the second-best constraints**, each switchable: move only to regions with a ≥330 kV substation; stay within today's clusters.
5. **Checks itself.** The local-mix LPs are re-solved with HiGHS; the plant placement is checked against the exact optimum of a mixed-integer programme.
6. **Publishes one interactive page.** Sectors, cost of capital, gas and CO₂ prices, technologies and constraints can be changed in the browser, which re-solves the mixes and plans in a few seconds. Under *Model assumptions*, each sector's electricity per tonne has a **Source** button giving the citation, the phrase to search for in the source (Ctrl+F) and the conversion. A **Data** section at the bottom shows the plants or regions of the chosen scenario as a sortable table that can be copied as CSV.

The method is written out in [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## Repository layout

```
heavy-industry-power-atlas/
├── run_all.py                     one command: data prep → model → checks → web page
├── config/model_config.json       EVERY default in one place
├── data/
│   ├── raw/                       files as downloaded, with checksums (sources.json)
│   ├── derived/                   monthly solar (PVGIS) and wind (EMHIRES) capacity factors per region
│   ├── manual/                    hand-compiled inputs, one CSV each, with source and verification columns
│   ├── processed/                 data.json (read by the model and the map), regions.csv, plants.csv
│   └── DATA_MANIFEST.md           provenance, checksums, licences and field dictionary
├── src/
│   ├── data_prep/                 Python: raw + manual → processed (7 steps); fetch_raw.py; fetch_weather.py
│   ├── model/
│   │   ├── mix.js                 step 1: least-cost local mix (linear programme per sector × region)
│   │   └── plan.js                step 2: plant placement (stay put / second best / first best)
│   ├── run/run_scenarios.js       headless runs → outputs/results/*.csv, including sensitivities
│   ├── validation/                validate_lp.py (mixes vs HiGHS), validate_plan.py (placement vs exact MILP)
│   └── site/                      template.html + build_site.py → site/index.html
├── outputs/
│   ├── results/                   scenario_summary, plant_allocation, local_mix_by_region, region_load, sensitivities
│   ├── validation/                lp_check.csv, plan_check.csv
│   ├── review/                    plant_lists_for_review.xlsx (one sheet per sector, for a human check)
│   └── qa_report.md               counts and totals from the data preparation
├── docs/
│   ├── METHODOLOGY.md             equations, algorithms, outputs
│   └── ASSUMPTIONS.md             every assumption, numbered, with value, basis and status
└── .github/workflows/deploy.yml   rebuilds and publishes the map on every push
```

## Run it on your computer

You need Python 3.12+ and Node.js 18+.

```bash
pip install -r requirements.txt
npm ci
python run_all.py
```

The run takes about five minutes, most of it the exact placement check. Then open `site/index.html` in a browser. To check the raw files against their recorded checksums, run `python src/data_prep/fetch_raw.py --check-only`.

The weather tables in `data/derived/` are committed. To rebuild them, run `python src/data_prep/fetch_weather.py`: it queries the PVGIS API (about 1,700 points) and downloads the 561 MB EMHIRES file into `data/cache/`.

## Publish the map from GitHub

The workflow in `.github/workflows/deploy.yml` rebuilds everything from the raw data and publishes the map with GitHub Pages each time you push to `main`. The page links back to the repository (taken from the `origin` remote). Visitors can open that link only if the repository is public.

1. On github.com, create a new **empty** repository, e.g. `heavy-industry-power-atlas`. Don't add a README, `.gitignore` or licence.
2. From this folder:
   ```bash
   git remote add origin https://github.com/<your-username>/heavy-industry-power-atlas.git
   git push -u origin main
   ```
   (or GitHub Desktop: *Add local repository* → *Publish repository*).
3. In the repository: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
4. Open the **Actions** tab, then **Build and publish the atlas → Run workflow**. Pushes after this one trigger it automatically.
5. The map appears at `https://<your-username>.github.io/heavy-industry-power-atlas/`. Each run also stores the result tables as a downloadable *results* artifact.

## Change an assumption

- **Model assumptions** (sector intensities and utilisation, costs, land, constraint settings): edit `config/model_config.json`, then run `python run_all.py --skip-data` (utilisation needs a full `python run_all.py`).
- **Plants and policies**: edit the CSV in `data/manual/`, then run `python run_all.py`. The review spreadsheet in `outputs/review/` lists every plant with columns for corrections.
- **New raw data**: add the file to `data/raw/`, record it in `data/raw/sources.json`, and read it in the relevant step of `src/data_prep/steps.py`.

Each assumption carries an ID in `docs/ASSUMPTIONS.md` (for example 5.7 for the SMR cost), which names the config key or file that holds it.

## Data sources

| Data | Provider | Used for |
|---|---|---|
| NUTS-2 regions (2024; 2016 for the UK), countries | Eurostat GISCO via [Nuts2json](https://github.com/eurostat/Nuts2json) | regions, areas, map |
| Population (demo_r_d2jan) | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/demo_r_d2jan/default/table) | population density, settled land |
| Monthly solar yield | [PVGIS 5.3](https://re.jrc.ec.europa.eu/pvg_tools/en/), JRC | solar capacity factors |
| Hourly onshore wind, NUTS-2 | [EMHIRES](https://zenodo.org/records/8340501), JRC (CC BY 4.0) | wind capacity factors |
| Transmission grid; ammonia plants | [PyPSA-Eur](https://github.com/PyPSA/pypsa-eur) (ENTSO-E map extract) | substations ≥330 kV, lines; ammonia sites |
| EU ETS cement kilns | [Tröndle et al. (2019)](https://github.com/timtroendle/possibility-for-electricity-autarky) | cement sites and output |
| Steelworks, smelters, crackers, cement and ammonia gaps, nuclear policy | hand compilation, flagged per row | see `data/manual/` |
| Electricity per tonne by sector | Vogl et al. 2018 (steel), IRENA 2022 (ammonia), JRC 2023 and 2024 (cement, aluminium), PBL/TNO 2021 (chemicals) | demand; citations, search phrases and page numbers in `docs/ASSUMPTIONS.md` (section 1.1) |

Cost assumptions draw on BNEF (batteries), the IEA (electrolysers) and Arthur D. Little (SMRs); details in `docs/ASSUMPTIONS.md`. Administrative boundaries © EuroGeographics. Other providers' terms are linked in `data/DATA_MANIFEST.md`.

## Main limitations

1. **Behind the meter, by design.** Plants run only on their own assets in their own region; moving the plant is the only way to reach better sun and wind. Allowing some grid power would lower costs.
2. **Monthly weather hides calm spells.** Wind only varies by month and day/night, so wind-heavy mixes need little storage and look cheaper than they are.
3. **Wind data reflect the 2015 fleet.** Modern turbines would achieve higher capacity factors, especially in regions with few turbines in 2015.
4. **Output per site is capacity × one utilisation rate per sector.** Aluminium is the weak spot.
5. **Moving a plant is free.** No product transport or relocation cost.
6. **Plants added for Norway, Switzerland and the UK are unverified**, as are costs pending an update to IEA cost tables.
7. **Electricity per tonne leaves some uses out.** Aluminium counts smelting only (alumina is refined elsewhere); cement counts the electric kiln only, without grinding or CO₂-capture electricity; chemicals attributes all cracker energy to ethylene. Cement and chemicals each take one conversion from the cited figures (see `docs/ASSUMPTIONS.md`).

## Authors

[Elise Viadere](https://www.cer.eu/personnel/elise-viadere) and [Ron Stoop](https://www.cer.eu/personnel/ron-stoop), [Centre for European Reform](https://www.cer.eu). Model and code built with Claude (Anthropic), October–November 2026.
