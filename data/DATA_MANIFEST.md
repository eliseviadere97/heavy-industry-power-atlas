# Data manifest

Every input the pipeline reads, where it came from, and what it becomes. Four folders:

- `data/raw/`: files exactly as downloaded. GitHub sources are pinned to fixed commits; Eurostat tables come from its API on the date shown. Run `python src/data_prep/fetch_raw.py --check-only` to verify checksums, or drop `--check-only` to re-download.
- `data/derived/`: the two weather tables, built from large external datasets by `python src/data_prep/fetch_weather.py` (downloads cached in the git-ignored `data/cache/`).
- `data/manual/`: inputs compiled by hand. Every row carries its source and a verification status.
- `data/processed/`: written by `src/data_prep/run_data_prep.py`. Don't edit by hand.

## 1. Raw files (`data/raw/`)

### `nuts2json/nutsrg_2_2024_3035_20M.json`

- **Provider:** Eurostat GISCO via Nuts2json
- **Content:** NUTS 2024 level-2 region polygons, EPSG:3035, 1:20M
- **Used in:** Step 1 regions; map geometry
- **Source:** <https://raw.githubusercontent.com/eurostat/Nuts2json/8186be451525164ea24b43560cb943fda7c5520c/pub/v2/2024/3035/20M/nutsrg_2.json>
- **Retrieved:** 2026-10-21 · **Size:** 294,392 bytes · **SHA-256:** `b360d89dfb5f9927efd91347a7c7c2285342a5127005f8c0b1e19a59865c8c47`
- **Terms:** © EuroGeographics for the administrative boundaries (GISCO terms of use)

### `nuts2json/nutspt_2_2024_4326.json`

- **Provider:** Eurostat GISCO via Nuts2json
- **Content:** NUTS 2024 level-2 label points (WGS84) with region area (m²)
- **Used in:** Step 1 centroids and areas
- **Source:** <https://raw.githubusercontent.com/eurostat/Nuts2json/8186be451525164ea24b43560cb943fda7c5520c/pub/v2/2024/4326/nutspt_2.json>
- **Retrieved:** 2026-10-21 · **Size:** 47,381 bytes · **SHA-256:** `be0480610ebaf823ecaf3365e434821548a9a2328d3932922509c0c19a5fbbf6`
- **Terms:** © EuroGeographics for the administrative boundaries (GISCO terms of use)

### `nuts2json/cntrg_2024_3035_20M.json`

- **Provider:** Eurostat GISCO via Nuts2json
- **Content:** Country polygons, EPSG:3035, 1:20M
- **Used in:** Step 9 grey background countries on the map
- **Source:** <https://raw.githubusercontent.com/eurostat/Nuts2json/8186be451525164ea24b43560cb943fda7c5520c/pub/v2/2024/3035/20M/cntrg.json>
- **Retrieved:** 2026-10-21 · **Size:** 209,073 bytes · **SHA-256:** `0a17ee94d6648a1486ec0bdcc1aa963ff27e4b7f21663ae87ede150072e1ac74`
- **Terms:** © EuroGeographics for the administrative boundaries (GISCO terms of use)

### `pypsa_eur/ammonia_plants.csv`

- **Provider:** PyPSA-Eur
- **Content:** European ammonia plants with capacities and coordinates (sources cited per row)
- **Used in:** Step 5 ammonia sites
- **Source:** <https://raw.githubusercontent.com/PyPSA/pypsa-eur/0989251c65c81c7515100fdae7056240a3a9086d/data/ammonia_plants.csv>
- **Retrieved:** 2026-10-21 · **Size:** 7,952 bytes · **SHA-256:** `1c60c531339cca5ce92b0df220392943d6da1e2f6848536ff5db835d53cba5d5`
- **Terms:** See provider repository for licence terms

### `pypsa_eur/entsoegridkit_buses.csv`

- **Provider:** PyPSA-Eur (GridKit extract of the ENTSO-E interactive map)
- **Content:** Transmission substations with voltage and coordinates
- **Used in:** Step 4 substations >=330 kV per region
- **Source:** <https://raw.githubusercontent.com/PyPSA/pypsa-eur/0989251c65c81c7515100fdae7056240a3a9086d/data/entsoegridkit/buses.csv>
- **Retrieved:** 2026-10-21 · **Size:** 1,466,411 bytes · **SHA-256:** `c52bab913d17585908798e28b02924e17cf05ed03ffb699d3cd24dcf025ecfb0`
- **Terms:** See provider repository for licence terms

### `pypsa_eur/entsoegridkit_lines.csv`

- **Provider:** PyPSA-Eur (GridKit extract of the ENTSO-E interactive map)
- **Content:** Transmission lines with voltage and geometry
- **Used in:** Step 4 lines drawn on the map
- **Source:** <https://raw.githubusercontent.com/PyPSA/pypsa-eur/0989251c65c81c7515100fdae7056240a3a9086d/data/entsoegridkit/lines.csv>
- **Retrieved:** 2026-10-21 · **Size:** 3,952,327 bytes · **SHA-256:** `ad46bd0093a0fdffdd11b721f510929d2f6f98c1b48a19ccb0ac9162245eda9a`
- **Terms:** See provider repository for licence terms

### `troendle_2019/energy-intensive-industries.xlsx`

- **Provider:** Tröndle et al. (2019), 'Home-made or imported: on the possibility for renewable electricity autarky on all scales in Europe'
- **Content:** EU ETS installations (2013-14 verified emissions) for cement, steel, aluminium; chlor-alkali sites (Euro Chlor), with coordinates
- **Used in:** Step 5 cement kilns (EU ETS 2013-14)
- **Source:** <https://raw.githubusercontent.com/timtroendle/possibility-for-electricity-autarky/a3d3c99ef90bbccd7232e2170317a259a77661d3/data/electricity-intensive-industry/energy-intensive-industries.xlsx>
- **Retrieved:** 2026-10-21 · **Size:** 167,521 bytes · **SHA-256:** `1b03271493e3d80ae70ef68f16c8b308595672ecb04eada48f6c5e0b8316c6ba`
- **Terms:** See provider repository for licence terms

### `nuts2json/nutsrg_2_2016_3035_20M.json`

- **Provider:** Eurostat GISCO via Nuts2json
- **Content:** NUTS 2016 level-2 region polygons, EPSG:3035, 1:20M (used for the UK only)
- **Used in:** Step 1 regions; map geometry
- **Source:** <https://raw.githubusercontent.com/eurostat/Nuts2json/8186be451525164ea24b43560cb943fda7c5520c/pub/v2/2016/3035/20M/nutsrg_2.json>
- **Retrieved:** 2026-11-03 · **Size:** 316,119 bytes · **SHA-256:** `35bb5565a46ae4ec50da191792e26b3801a43e6e2bc428d7d26200639f05235a`
- **Terms:** © EuroGeographics for the administrative boundaries (GISCO terms of use)

### `nuts2json/nutspt_2_2016_4326.json`

- **Provider:** Eurostat GISCO via Nuts2json
- **Content:** NUTS 2016 level-2 label points (WGS84) with region area (m²) (used for the UK only)
- **Used in:** Step 1 centroids and areas
- **Source:** <https://raw.githubusercontent.com/eurostat/Nuts2json/8186be451525164ea24b43560cb943fda7c5520c/pub/v2/2016/4326/nutspt_2.json>
- **Retrieved:** 2026-11-03 · **Size:** 52,016 bytes · **SHA-256:** `26f0b36a6e08a5aa42118ef14f5854517fc3c46d539fee0ecac00e43166d852d`
- **Terms:** © EuroGeographics for the administrative boundaries (GISCO terms of use)

### `eurostat/demo_r_d2jan_nuts2_2024.json`

- **Provider:** Eurostat
- **Content:** Population on 1 January 2024 by NUTS-2 region (demo_r_d2jan)
- **Used in:** Step 2 population
- **Source:** <https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/demo_r_d2jan?format=JSON&lang=EN&sex=T&age=TOTAL&geoLevel=nuts2&time=2024>
- **Retrieved:** 2026-11-03 · **Size:** 20,789 bytes · **SHA-256:** `47717976e8042a16634c9d9c4156c0866c122d8b9cbba4ef4325d2ce4497dc30`
- **Terms:** Eurostat copyright notice (free reuse with acknowledgement)

### `eurostat/demo_r_d2jan_nuts2_2019.json`

- **Provider:** Eurostat
- **Content:** Population on 1 January 2019 by NUTS-2 region (demo_r_d2jan); last year with UK data
- **Used in:** Step 2 population (UK)
- **Source:** <https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/demo_r_d2jan?format=JSON&lang=EN&sex=T&age=TOTAL&geoLevel=nuts2&time=2019>
- **Retrieved:** 2026-11-03 · **Size:** 20,859 bytes · **SHA-256:** `00c1f6ce53ed3b493e786bc38263502371d4a3c6fc295832bd30bf31b65dcc58`
- **Terms:** Eurostat copyright notice (free reuse with acknowledgement)

## 2. Derived weather tables (`data/derived/`)

| File | Content | Source | Method |
|---|---|---|---|
| `pv_monthly_cf.csv` | Solar PV capacity factor by region and month; points sampled; annual yield | [PVGIS 5.3](https://re.jrc.ec.europa.eu/pvg_tools/en/) API (`PVcalc`, PVGIS-ERA5, 2005–2023), © European Union, JRC | Fixed, optimally tilted 1 kWp, 14% losses; mean of up to 6 grid points inside each region; yield ÷ hours in the month |
| `wind_monthly_cf.csv` | Onshore wind capacity factor by region, month, day and night; contributing EMHIRES regions | [JRC EMHIRES wind, NUTS-2](https://zenodo.org/records/8340501) (June 2019 release, CC BY 4.0), hourly 1986–2015, fleet of end-2015 | Day = 06–18 UTC; area-weighted over overlapping NUTS 2016 regions; Malta takes Sicily (no data); source column `DECOO` read as `DEC0` |

Built on 3 November 2026.

## 3. Hand-compiled files (`data/manual/`)

| File | Rows | Content | Status |
|---|---|---|---|
| `steel_plants.csv` | 25 | Integrated (blast furnace) steelworks: capacity (Mt), status | EU rows not individually verified; UK rows NOT VERIFIED |
| `aluminium_smelters.csv` | 22 | Primary smelters: capacity (kt), status | EU rows not individually verified; NO/UK rows NOT VERIFIED |
| `steam_crackers.csv` | 32 | Steam crackers: ethylene capacity (kt), status | EU rows not individually verified; NO/UK rows NOT VERIFIED |
| `cement_additions.csv` | 81 | Clinker kilns missing from the ETS-derived list: capacity (kt) | Not individually verified; UK/NO/CH rows NOT VERIFIED |
| `cement_exclusions.csv` | 3 | Kilns dropped from the ETS list (closed, or wrong coordinates) | Sourced |
| `ammonia_capacity_fills.csv` | 7 | Capacities for PyPSA-Eur rows with none; zero excludes the row | Not individually verified |
| `ammonia_additions.csv` | 3 | Ammonia sites missing from PyPSA-Eur | Not individually verified |
| `nuclear_policy.csv` | 12 | Whether new reactors are allowed, by country | Policy as of November 2026; NO and CH to check |
| `population_overrides.csv` | 1 | Population where Eurostat has no value for the chosen year (Northern Ireland, 2018) | Eurostat |

All plant rows are collected for review in `outputs/review/plant_lists_for_review.xlsx`.

## 4. Processed outputs (`data/processed/`)

`data.json` holds `regions` (one record per NUTS-2 region), `geo` (simplified region polygons, km in EPSG:3035), `bg` (neighbouring countries), `plants` (sites with output) and `lines` (transmission lines for display). `regions.csv` and `plants.csv` hold the same records as flat tables.

| Region field | Meaning | Unit |
|---|---|---|
| `id, na, cc` | NUTS-2 code, name, country code | — |
| `lat, lon`, `cx, cy` | label point (degrees; km in EPSG:3035) | — |
| `area`, `pop` | region area; population | km²; people |
| `pv[12]` | solar capacity factor by month | 0–1 |
| `wd[12]`, `wn[12]` | onshore wind capacity factor by month, day and night | 0–1 |
| `n330` | substations ≥330 kV | count |
| `cap.steel … cap.aluminium` | capacity of producing plants in the region | kt/yr |
| `nban` | national policy bars new reactors | 0/1 |

Plant fields: `i` sector, `n` name (status appended if not operating), `r` NUTS-2 region, `c` capacity (kt/yr), `o` output used by the model (kt/yr), `x`/`y` location (km, EPSG:3035).
