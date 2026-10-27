# Data manifest

Every input the pipeline reads, where it came from, and what it becomes. Three folders:

- `data/raw/`: files exactly as downloaded. Each is pinned to a fixed commit, so the URL always returns the same bytes. Retrieved 21 October 2026; checksums re-verified 27 October 2026. Run `python src/data_prep/fetch_raw.py --check-only` to verify them, or drop `--check-only` to re-download.
- `data/manual/`: inputs compiled by the author where no open dataset was reachable or complete. Every row carries its source and a verification status.
- `data/processed/`: written by `src/data_prep/run_data_prep.py`. Don't edit by hand.

## 1. Raw files (`data/raw/`)

### `nuts2json/nutsrg_2_2024_3035_20M.json`

- **Provider:** Eurostat GISCO via Nuts2json
- **Content:** NUTS 2024 level-2 region polygons, EPSG:3035, 1:20M
- **Used in:** Step 1 regions; map geometry
- **Source (pinned):** <https://raw.githubusercontent.com/eurostat/Nuts2json/8186be451525164ea24b43560cb943fda7c5520c/pub/v2/2024/3035/20M/nutsrg_2.json>
- **Retrieved:** 2026-10-21 · **Size:** 294,392 bytes · **SHA-256:** `b360d89dfb5f9927efd91347a7c7c2285342a5127005f8c0b1e19a59865c8c47`
- **Terms:** © EuroGeographics for the administrative boundaries (GISCO terms of use)

### `nuts2json/nutspt_2_2024_4326.json`

- **Provider:** Eurostat GISCO via Nuts2json
- **Content:** NUTS 2024 level-2 label points (WGS84) with region area (m²)
- **Used in:** Step 1 centroids and areas
- **Source (pinned):** <https://raw.githubusercontent.com/eurostat/Nuts2json/8186be451525164ea24b43560cb943fda7c5520c/pub/v2/2024/4326/nutspt_2.json>
- **Retrieved:** 2026-10-21 · **Size:** 47,381 bytes · **SHA-256:** `be0480610ebaf823ecaf3365e434821548a9a2328d3932922509c0c19a5fbbf6`
- **Terms:** © EuroGeographics for the administrative boundaries (GISCO terms of use)

### `nuts2json/nutsbn_3_2024_3035_20M.json`

- **Provider:** Eurostat GISCO via Nuts2json
- **Content:** NUTS 2024 level-3 boundaries with coastal flag
- **Used in:** Step 4 coastline length and sea basin
- **Source (pinned):** <https://raw.githubusercontent.com/eurostat/Nuts2json/8186be451525164ea24b43560cb943fda7c5520c/pub/v2/2024/3035/20M/nutsbn_3.json>
- **Retrieved:** 2026-10-21 · **Size:** 1,147,481 bytes · **SHA-256:** `a19538e4c05c58f2a01ca89432ffb99b21cb4a02af3516e6cc214cedb80f2f4a`
- **Terms:** © EuroGeographics for the administrative boundaries (GISCO terms of use)

### `nuts2json/cntrg_2024_3035_20M.json`

- **Provider:** Eurostat GISCO via Nuts2json
- **Content:** Country polygons, EPSG:3035, 1:20M
- **Used in:** Step 9 grey background countries on the map
- **Source (pinned):** <https://raw.githubusercontent.com/eurostat/Nuts2json/8186be451525164ea24b43560cb943fda7c5520c/pub/v2/2024/3035/20M/cntrg.json>
- **Retrieved:** 2026-10-21 · **Size:** 209,073 bytes · **SHA-256:** `0a17ee94d6648a1486ec0bdcc1aa963ff27e4b7f21663ae87ede150072e1ac74`
- **Terms:** © EuroGeographics for the administrative boundaries (GISCO terms of use)

### `powerplantmatching/powerplants.csv`

- **Provider:** powerplantmatching (PyPSA)
- **Content:** Matched European power plant database: fuel, technology, capacity, dates, coordinates
- **Used in:** Step 6 existing wind, solar and hydro by region
- **Source (pinned):** <https://raw.githubusercontent.com/PyPSA/powerplantmatching/2889ad9d1754a7ee4368b9282d7af835bf572ca2/powerplants.csv>
- **Retrieved:** 2026-10-21 · **Size:** 39,779,419 bytes · **SHA-256:** `ceccce02edd33813216a264fe6c8e3281ce2249435a259c1b1a1b729ce4f3d78`
- **Terms:** See provider repository for licence terms

### `pypsa_eur/ammonia_plants.csv`

- **Provider:** PyPSA-Eur
- **Content:** European ammonia plants with capacities and coordinates (sources cited per row)
- **Used in:** Step 7 ammonia sites
- **Source (pinned):** <https://raw.githubusercontent.com/PyPSA/pypsa-eur/0989251c65c81c7515100fdae7056240a3a9086d/data/ammonia_plants.csv>
- **Retrieved:** 2026-10-21 · **Size:** 7,952 bytes · **SHA-256:** `1c60c531339cca5ce92b0df220392943d6da1e2f6848536ff5db835d53cba5d5`
- **Terms:** See provider repository for licence terms

### `pypsa_eur/entsoegridkit_buses.csv`

- **Provider:** PyPSA-Eur (GridKit extract of the ENTSO-E interactive map)
- **Content:** Transmission substations with voltage and coordinates
- **Used in:** Step 5 substations per region
- **Source (pinned):** <https://raw.githubusercontent.com/PyPSA/pypsa-eur/0989251c65c81c7515100fdae7056240a3a9086d/data/entsoegridkit/buses.csv>
- **Retrieved:** 2026-10-21 · **Size:** 1,466,411 bytes · **SHA-256:** `c52bab913d17585908798e28b02924e17cf05ed03ffb699d3cd24dcf025ecfb0`
- **Terms:** See provider repository for licence terms

### `pypsa_eur/entsoegridkit_lines.csv`

- **Provider:** PyPSA-Eur (GridKit extract of the ENTSO-E interactive map)
- **Content:** Transmission lines with voltage and geometry
- **Used in:** Step 5 lines drawn on the map
- **Source (pinned):** <https://raw.githubusercontent.com/PyPSA/pypsa-eur/0989251c65c81c7515100fdae7056240a3a9086d/data/entsoegridkit/lines.csv>
- **Retrieved:** 2026-10-21 · **Size:** 3,952,327 bytes · **SHA-256:** `ad46bd0093a0fdffdd11b721f510929d2f6f98c1b48a19ccb0ac9162245eda9a`
- **Terms:** See provider repository for licence terms

### `troendle_2019/energy-intensive-industries.xlsx`

- **Provider:** Tröndle et al. (2019), 'Home-made or imported: on the possibility for renewable electricity autarky on all scales in Europe'
- **Content:** EU ETS installations (2013-14 verified emissions) for cement, steel, aluminium; chlor-alkali sites (Euro Chlor), with coordinates
- **Used in:** Step 7 cement kilns and chlor-alkali clusters
- **Source (pinned):** <https://raw.githubusercontent.com/timtroendle/possibility-for-electricity-autarky/a3d3c99ef90bbccd7232e2170317a259a77661d3/data/electricity-intensive-industry/energy-intensive-industries.xlsx>
- **Retrieved:** 2026-10-21 · **Size:** 167,521 bytes · **SHA-256:** `1b03271493e3d80ae70ef68f16c8b308595672ecb04eada48f6c5e0b8316c6ba`
- **Terms:** See provider repository for licence terms

### `geonames/cities15000_eu27.csv`

- **Provider:** GeoNames, packaged by geonamescache 3.0.2
- **Content:** Towns above 15,000 inhabitants in EU27 countries: name, coordinates, population
- **Used in:** Step 2 population and urban share by region
- **Source (pinned):** geonamescache 3.0.2 (Python package) -> GeoNames cities15000
- **Retrieved:** 2026-10-21 · **Size:** 243,185 bytes · **SHA-256:** `9ff89bc69c4d4e0d30b67d47d891124a34a85ea74f50a4191d5e5f2cd31e7f8f`
- **Terms:** GeoNames data, CC BY 4.0

Repositories at the pinned commits: Nuts2json `8186be4`, powerplantmatching `2889ad9`, PyPSA-Eur `0989251`, Tröndle et al. `a3d3c99`. The GeoNames subset is regenerated from the `geonamescache` 3.0.2 Python package by `fetch_raw.py`.

Fields read from each raw file:

| File | Fields used | Filters applied |
|---|---|---|
| nutsrg_2 | `id`, `na`, geometry | EU27 codes; outermost regions, Ceuta and Melilla dropped (`data_prep.excluded_nuts_prefixes`) |
| nutspt_2 | label point lon/lat, `ar` (area, m²) | — |
| nutsbn_3 | geometry, `co` (coastal), `left`/`right` (NUTS-3 ids) | coastal boundaries only |
| cntrg | geometry, `id` | non-EU27 countries (map background) |
| powerplants.csv | `Fueltype`, `Technology`, `Country`, `Capacity` (MW), `DateIn`, `DateOut`, `lat`, `lon` | solar, wind, reservoir and run-of-river hydro; commissioned by 2025; not retired before 2025 |
| ammonia_plants.csv | `Plant`, `Ammonia [kt/a]`, `Country`, `Latitude`, `Longitude` | EU27 countries; capacity > 0 after fills |
| entsoegridkit_buses.csv | `voltage`, `dc`, `under_construction`, `x` (lon), `y` (lat) | AC, ≥220 kV, built |
| entsoegridkit_lines.csv | `voltage`, `under_construction`, `geometry` (WKT) | ≥220 kV, built; display only |
| energy-intensive-industries.xlsx | sheet *Act 29 (cement clinker)*: `REGISTRY_CODE`, `INSTALLATION_NAME`, `VERIFIED_EMISSIONS_2014/2013`, `Coordinates`; sheet *Total chloralkali*: `Company`, `Country`, `City`, `Coordinates`, `Capacity (kt Cl/a)` | EU27; rows with parseable coordinates and positive emissions |
| cities15000_eu27.csv | `countrycode`, `latitude`, `longitude`, `population` | EU27 (GR mapped to EL) |

## 2. Hand-compiled files (`data/manual/`)

| File | Rows | Content | Basis | Status |
|---|---|---|---|---|
| `steel_plants.csv` | 23 | Integrated (blast furnace / basic oxygen) steelworks: name, country, lat/lon, crude steel capacity (Mt), status | Operator public information | Not individually verified. Existing electric-arc plants not included |
| `aluminium_smelters.csv` | 14 | Primary smelters: capacity (kt), status (operating/idle) | Operator public information | Not individually verified |
| `steam_crackers.csv` | 28 | Steam crackers: ethylene capacity (kt) | Operator public information | Not individually verified |
| `cement_additions.csv` | 63 | Clinker kilns missing from the ETS-derived list: capacity (kt clinker) | Operator public information | Not individually verified |
| `cement_exclusions.csv` | 1 | Kilns dropped from the ETS list | Operator announcements | Closed sites |
| `ammonia_capacity_fills.csv` | 6 | Capacities for PyPSA-Eur rows with none; zero excludes the row | Operator public information | Not individually verified |
| `ammonia_additions.csv` | 3 | Ammonia sites missing from PyPSA-Eur | Operator public information | Not individually verified |
| `chloralkali_coordinate_fixes.csv` | 2 | Corrected coordinates for two chlor-alkali rows | Site locations | Corrections of source errors |
| `population_national_2024.csv` | 27 | National population on 1 January 2024 (million); FR, ES, PT exclude outermost regions | Eurostat tps00001, entered by the author | Check against Eurostat |
| `weather_anchors.csv` | 157 | 157 reference points: PV yield (kWh/kWp/yr incl. losses) and onshore wind capacity factor | Author estimates calibrated to PVGIS and the Global Wind Atlas | **Placeholder: replace with EMHIRES or Renewables.ninja NUTS-2 averages** |
| `offshore_basins.csv` | 5 | Offshore wind capacity factor and capex by sea basin | Author estimates | Judgement |
| `grid_congestion_scores.csv` | 55 | Score from −0.5 (surplus) to +0.8 (saturated) by NUTS prefix; longest prefix wins | Stylised from TSO/DSO publications 2023–25 | Judgement |
| `nuclear_policy.csv` | 9 | Whether new reactors are allowed, by country, with the legal basis | Public law and policy as of October 2026 | Spain's is a phase-out, not a ban |
| `salt_caverns.csv` | 30 | NUTS prefixes with salt formations suitable for hydrogen caverns | Known salt basins and storage sites | Stylised; replace with Caglayan et al. (2020) |

## 3. Processed outputs (`data/processed/`)

`data.json` holds `regions` (one record per NUTS-2 region), `geo` (simplified region polygons, km in EPSG:3035), `bg` (neighbouring countries), `plants` (industrial sites and chlor-alkali markers), `subs` (substations) and `lines` (transmission lines). `regions.csv` and `plants.csv` hold the same records as flat tables.

Region fields:

| Field | Meaning | Unit | Step |
|---|---|---|---|
| `id, na, cc` | NUTS-2 code, name, country code | — | 1 |
| `lat, lon` | label point | degrees | 1 |
| `cx, cy` | label point in EPSG:3035 | km | 1 |
| `area` | region area | km² | 1 |
| `pop` | population (towns + residual) | people | 2 |
| `urb` | share living in towns > 15,000 | 0–1 | 2 |
| `pv` | solar capacity factor (annual average) | 0–1 | 3 |
| `won` | onshore wind capacity factor (annual average) | 0–1 | 3 |
| `coast` | coastline length at 1:20M | km | 4 |
| `basin` | dominant sea basin | — | 4 |
| `coff, kxoff` | offshore capacity factor and capex for that basin | 0–1, €/kW | 4 |
| `n380, n220` | substations ≥330 kV and 220–300 kV | count | 5 |
| `e.pv, e.won, e.woff, e.hres, e.hror` | installed solar, onshore, offshore, reservoir hydro, run-of-river | MW | 6 |
| `cap.steel … cap.aluminium` | capacity of today's plants in the region | kt/yr (steel crude, cement clinker, NH₃, ethylene, Al) | 7 |
| `chlor` | chlor-alkali capacity (marks chemical clusters) | kt Cl/yr | 7 |
| `cong` | grid congestion score | −0.5 to +0.8 | 8 |
| `cav` | salt caverns available for hydrogen | 0/1 | 8 |
| `nban` | national policy bars new reactors | 0/1 | 8 |

Plant fields: `i` industry (`steel`, `cement`, `ammonia`, `chemicals`, `aluminium`, or `chlor` for markers), `n` name, `r` NUTS-2 region, `c` capacity (kt/yr, units as above), `x`/`y` location (km, EPSG:3035).

