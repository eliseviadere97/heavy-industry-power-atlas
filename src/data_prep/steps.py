"""The nine data-preparation steps. Each step takes and returns the shared context dict `ctx`.

ctx["R"]       ordered dict of regions keyed by NUTS-2 id (the model's spatial unit)
ctx["locate"]  Locator for NUTS-2 polygons
ctx["plants"]  list of industrial sites (and chlor-alkali sites used only to mark chemical clusters)
ctx["qa"]      lines written to outputs/qa_report.md
"""
import json
import re

import numpy as np
import pandas as pd
from shapely import wkt
from shapely.geometry import LineString, mapping, shape
from shapely.ops import unary_union

from common import CFG, EU27, RAW, COUNTRY_CODES, Locator, TI, proj, read_manual

NUTS = RAW / "nuts2json"


# --------------------------------------------------------------------------------------------
# Step 1 · Regions: NUTS-2 (2024) polygons for the EU27, minus outermost regions, Ceuta and Melilla
# --------------------------------------------------------------------------------------------
def s1_regions(ctx):
    rg = json.loads((NUTS / "nutsrg_2_2024_3035_20M.json").read_text(encoding="utf-8"))
    excl = tuple(CFG["excluded_nuts_prefixes"])
    feats = [f for f in rg["features"] if f["properties"]["id"][:2] in EU27 and not f["properties"]["id"].startswith(excl)]
    pts = {f["properties"]["id"]: f for f in json.loads((NUTS / "nutspt_2_2024_4326.json").read_text(encoding="utf-8"))["features"]}
    ids = [f["properties"]["id"] for f in feats]
    geoms = [shape(f["geometry"]).buffer(0) for f in feats]
    R = {}
    for i, f in zip(ids, feats):
        pt = pts[i]
        lon, lat = pt["geometry"]["coordinates"]
        x, y = proj(lon, lat)
        R[i] = dict(id=i, na=f["properties"]["na"], cc=i[:2], area=pt["properties"]["ar"] / 1e6,   # km²
                    lon=lon, lat=lat, cx=x / 1000, cy=y / 1000, cities=0.0)
    ctx.update(R=R, feats=feats, geoms=geoms, ids=ids, locate=Locator(ids, geoms))
    ctx["qa"].append(f"- Regions: {len(R)} NUTS-2 regions (EU27, NUTS 2024, excluding {', '.join(excl)})")
    return ctx


# --------------------------------------------------------------------------------------------
# Step 2 · Population: towns > 15,000 (GeoNames) + national residual spread by area
# --------------------------------------------------------------------------------------------
def s2_population(ctx):
    R, locate = ctx["R"], ctx["locate"]
    cities = pd.read_csv(RAW / "geonames" / "cities15000_eu27.csv", encoding="utf-8")
    placed = 0
    for c in cities.itertuples(index=False):
        cc = "EL" if c.countrycode == "GR" else c.countrycode
        if cc not in EU27:
            continue
        r = locate(c.longitude, c.latitude)
        if r:
            R[r]["cities"] += c.population
            placed += 1
    pop = dict(read_manual("population_national_2024.csv")[["country_code", "population_million"]].itertuples(index=False))
    share = CFG["population"]["residual_min_share"]
    for cc in EU27:
        rs = [r for r in R.values() if r["cc"] == cc]
        if not rs:
            continue
        ctot = sum(r["cities"] for r in rs)
        atot = sum(r["area"] for r in rs)
        P = pop[cc] * 1e6
        resid = max(P - ctot, share * P)                         # at least 15% lives outside towns > 15k
        scale = (P - resid) / ctot if ctot > 0 else 0
        for r in rs:
            r["pop"] = r["cities"] * scale + resid * r["area"] / atot
            r["urb"] = r["cities"] * scale / r["pop"] if r["pop"] else 0   # urban share of population
    ctx["qa"].append(f"- Population: {placed} of {len(cities)} GeoNames towns placed in a region; national totals from data/manual/population_national_2024.csv")
    return ctx


# --------------------------------------------------------------------------------------------
# Step 3 · Weather: annual-average solar yield and onshore wind capacity factor (IDW of anchors)
# --------------------------------------------------------------------------------------------
def _haversine_km(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(a))


def s3_weather(ctx):
    A = read_manual("weather_anchors.csv")[["lat", "lon", "pv_yield_kwh_per_kwp", "onshore_wind_cf"]].to_numpy(float)
    k_n, pw, dmin = CFG["weather_idw"]["neighbours"], CFG["weather_idw"]["power"], CFG["weather_idw"]["min_distance_km"]
    for r in ctx["R"].values():
        d = _haversine_km(r["lat"], r["lon"], A[:, 0], A[:, 1])
        k = np.argsort(d)[:k_n]
        w = 1 / np.maximum(d[k], dmin) ** pw
        r["pv"] = float((A[k, 2] * w).sum() / w.sum()) / 8760      # solar capacity factor
        r["won"] = float((A[k, 3] * w).sum() / w.sum())            # onshore wind capacity factor
    ctx["qa"].append(f"- Weather: {len(A)} anchor points (PLACEHOLDER author estimates), IDW k={k_n}, power={pw}")
    return ctx


# --------------------------------------------------------------------------------------------
# Step 4 · Coastline and sea basin per region (from coastal NUTS-3 boundaries)
# --------------------------------------------------------------------------------------------
def _basin(lon, lat):
    if lon < -3:
        return "Atlantic"
    if lat < 38.2 and lon < -5.4:
        return "Atlantic"
    if lon > 27 and 41 < lat < 46.5:
        return "Black Sea"
    if lat > 53.5:
        if lon < 9.3 or (lon < 12.6 and 55.4 < lat < 59.3):
            return "North Sea"
        return "Baltic"
    if lat > 50.4 and lon > 1.4:
        return "North Sea"
    if lon < -1.5 or (lat > 43.6 and lon < 0.5) or lat > 46:
        return "Atlantic"
    return "Mediterranean"


def s4_coast(ctx):
    R = ctx["R"]
    off = {b.basin: (b.capacity_factor, b.overnight_capex_eur_per_kw) for b in read_manual("offshore_basins.csv").itertuples(index=False)}
    bn = json.loads((NUTS / "nutsbn_3_2024_3035_20M.json").read_text(encoding="utf-8"))
    for r in R.values():
        r["coast"], r["_b"] = 0.0, {}
    for f in bn["features"]:
        p = f["properties"]
        if p.get("co") != "T":
            continue
        n3 = p.get("left") or p.get("right")
        if not n3 or n3[:4] not in R:
            continue
        g = shape(f["geometry"])
        L = g.length / 1000                                         # km of coastline
        c = g.interpolate(0.5, normalized=True)
        lon, lat = TI.transform(c.x, c.y)
        r = R[n3[:4]]
        r["coast"] += L
        b = _basin(lon, lat)
        r["_b"][b] = r["_b"].get(b, 0) + L
    for r in R.values():
        r["basin"] = max(r["_b"], key=r["_b"].get) if r["_b"] else None
        del r["_b"]
        r["coff"], r["kxoff"] = off[r["basin"]] if r["basin"] else (0, 0)
    n = sum(1 for r in R.values() if r["basin"])
    ctx["qa"].append(f"- Coast: {n} coastal regions, {sum(r['coast'] for r in R.values()):,.0f} km of coastline at 1:20M")
    return ctx


# --------------------------------------------------------------------------------------------
# Step 5 · Transmission grid: count >=220 kV substations per region; keep lines for display
# --------------------------------------------------------------------------------------------
def s5_grid(ctx):
    R, locate, G = ctx["R"], ctx["locate"], CFG["grid"]
    bus = pd.read_csv(RAW / "pypsa_eur" / "entsoegridkit_buses.csv", quotechar="'")
    bus = bus[(bus.voltage >= G["min_voltage_kv"]) & (bus.dc == "f") & (bus.under_construction == "f")]
    for r in R.values():
        r["n380"], r["n220"] = 0, 0
    subs = []
    for b in bus.itertuples(index=False):
        rid = locate(b.x, b.y, CFG["snap_km"]["substation"])
        if not rid:
            continue
        hv = b.voltage >= G["high_voltage_kv"]
        R[rid]["n380" if hv else "n220"] += 1
        x, y = proj(b.x, b.y)
        subs.append([round(x / 1000, 1), round(y / 1000, 1), 1 if hv else 0])
    lines = pd.read_csv(RAW / "pypsa_eur" / "entsoegridkit_lines.csv", quotechar="'")
    lines = lines[(lines.voltage >= G["min_voltage_kv"]) & (lines.under_construction == False)]  # noqa: E712
    eu = unary_union(ctx["geoms"]).buffer(20000)
    L = []
    for l in lines.itertuples(index=False):
        g = wkt.loads(l.geometry)
        xs, ys = zip(*g.coords)
        X, Y = proj(xs, ys)
        g2 = LineString(list(zip(X, Y)))
        if not g2.intersects(eu):
            continue
        g2 = g2.simplify(G["line_simplify_m"])
        L.append([1 if l.voltage >= G["high_voltage_kv"] else 0, [[round(x / 1000, 1), round(y / 1000, 1)] for x, y in g2.coords]])
    ctx.update(subs=subs, lines=L)
    ctx["qa"].append(f"- Grid: {sum(r['n380'] for r in R.values())} substations >=330 kV and {sum(r['n220'] for r in R.values())} at 220-300 kV in EU27 regions; {len(L)} line segments kept for display")
    return ctx


# --------------------------------------------------------------------------------------------
# Step 6 · Existing renewables (utility scale) from powerplantmatching
# --------------------------------------------------------------------------------------------
def s6_renewables(ctx):
    R, locate, E = ctx["R"], ctx["locate"], CFG["existing_renewables"]
    ppm = pd.read_csv(RAW / "powerplantmatching" / "powerplants.csv",
                      usecols=["Fueltype", "Technology", "Country", "Capacity", "DateIn", "DateOut", "lat", "lon"])
    ppm = ppm[ppm.DateIn.isna() | (ppm.DateIn <= E["commissioned_by"])]
    ppm["Capacity"] = ppm.Capacity.fillna(0)
    ppm = ppm[ppm.Country.isin(list(COUNTRY_CODES)) & (ppm.DateOut.isna() | (ppm.DateOut >= E["still_operating_in"])) & ppm.lat.notna()]
    for r in R.values():
        r.update(e_pv=0.0, e_won=0.0, e_woff=0.0, e_hres=0.0, e_hror=0.0)

    def key(f, t):
        if f == "Solar":
            return "e_pv"
        if f == "Wind":
            return "e_woff" if t == "Offshore" else "e_won"
        if f == "Hydro":
            return {"Reservoir": "e_hres", "Run-Of-River": "e_hror"}.get(t)
        return None

    miss = 0.0
    for f, t, cty, cap, lat, lon in ppm[["Fueltype", "Technology", "Country", "Capacity", "lat", "lon"]].itertuples(index=False):
        k = key(f, t)
        if not k:
            continue
        snap = CFG["snap_km"]["offshore_plant"] if k == "e_woff" else CFG["snap_km"]["onshore_plant"]
        rid = locate(lon, lat, snap)
        if not rid or rid[:2] != COUNTRY_CODES[cty]:
            miss += cap
            continue
        R[rid][k] += cap
    tot = {k: sum(r[k] for r in R.values()) for k in ["e_pv", "e_won", "e_woff", "e_hres", "e_hror"]}
    ctx["qa"].append("- Existing renewables (MW): " + ", ".join(f"{k[2:]} {v:,.0f}" for k, v in tot.items()) + f"; {miss:,.0f} MW not placed (outside EU27 regions or country mismatch)")
    return ctx


# --------------------------------------------------------------------------------------------
# Step 7 · Industrial sites: steel, cement, ammonia, chemicals, aluminium (+ chlor-alkali clusters)
# --------------------------------------------------------------------------------------------
def _dms(s):
    """Parse the free-text coordinates in the Tröndle et al. workbook (DMS, decimal, mixed) -> (lat, lon)."""
    if not isinstance(s, str):
        return None
    s = s.replace("O", "E").replace("’", "′").replace("'", "′").replace('"', "″").replace(",", " ")
    out = []
    for m in re.finditer(r"(-?\d+(?:\.\d+)?)\s*°?\s*(?:(\d+(?:\.\d+)?)\s*′)?\s*(?:(\d+(?:\.\d+)?)\s*″)?\s*([NSEW])?", s):
        if not m.group(0).strip() or m.group(1) is None:
            continue
        v = float(m.group(1)) + float(m.group(2) or 0) / 60 + float(m.group(3) or 0) / 3600
        h = m.group(4)
        if h in ("S", "W"):
            v = -v
        out.append((v, h))
        if len(out) == 2:
            break
    if len(out) < 2:
        return None
    (a, ha), (b, hb) = out
    if ha in ("E", "W") or hb in ("N", "S"):
        a, b = b, a
    return a, b


def _named(df, cap_col):
    disp = lambda row: row["name"] + (" (idle)" if row.get("status") == "idle" else "")
    return [(disp(r), r["country_code"], r["lat"], r["lon"], r[cap_col]) for _, r in df.iterrows()]


def s7_plants(ctx):
    R, locate = ctx["R"], ctx["locate"]
    x = pd.read_excel(RAW / "troendle_2019" / "energy-intensive-industries.xlsx", sheet_name=None)
    plants = {k: [] for k in ["steel", "cement", "ammonia", "chemicals", "aluminium"]}
    # steel (capacity kt crude steel), aluminium (kt), crackers (kt ethylene): hand-compiled
    for n, cc, lat, lon, c in _named(read_manual("steel_plants.csv"), "crude_steel_capacity_mt"):
        plants["steel"].append((n, cc, lat, lon, c * 1000))
    plants["aluminium"] += _named(read_manual("aluminium_smelters.csv"), "primary_al_capacity_kt")
    plants["chemicals"] += _named(read_manual("steam_crackers.csv"), "ethylene_capacity_kt")
    # cement: EU ETS 2013/14 verified emissions / t CO2 per t clinker -> kt clinker; then additions
    drop = list(read_manual("cement_exclusions.csv").name_contains)
    ef = CFG["cement"]["t_co2_per_t_clinker"]
    for _, row in x["Act 29 (cement clinker)"].iterrows():
        cc = {"GR": "EL"}.get(row.REGISTRY_CODE, row.REGISTRY_CODE)
        if cc not in EU27 or not isinstance(row.Coordinates, str):
            continue
        if any(d in str(row.INSTALLATION_NAME) for d in drop):
            continue
        ll = _dms(row.Coordinates)
        em = row.VERIFIED_EMISSIONS_2014 if row.VERIFIED_EMISSIONS_2014 > 0 else row.VERIFIED_EMISSIONS_2013
        if not ll or not em or em <= 0:
            continue
        plants["cement"].append((str(row.INSTALLATION_NAME).strip().title()[:40], cc, ll[0], ll[1], em / (ef * 1000)))
    plants["cement"] += _named(read_manual("cement_additions.csv"), "clinker_capacity_kt")
    # ammonia: PyPSA-Eur list, capacity gaps filled, sites added
    fills = dict(read_manual("ammonia_capacity_fills.csv")[["plant", "ammonia_capacity_kt"]].itertuples(index=False))
    am = pd.read_csv(RAW / "pypsa_eur" / "ammonia_plants.csv")
    for _, a in am.iterrows():
        cc = COUNTRY_CODES.get(a.Country)
        if not cc:
            continue
        cap = a["Ammonia [kt/a]"] if not np.isnan(a["Ammonia [kt/a]"]) else fills.get(a.Plant, 0)
        if cap <= 0:
            continue
        plants["ammonia"].append((a.Plant, cc, a.Latitude, a.Longitude, cap))
    plants["ammonia"] += _named(read_manual("ammonia_additions.csv"), "ammonia_capacity_kt")
    # chlor-alkali sites: mark chemical clusters (eligibility of destinations only, no load)
    fixes = {r.city: (r.lat, r.lon) for r in read_manual("chloralkali_coordinate_fixes.csv").itertuples(index=False)}
    chlor = []
    for _, row in x["Total chloralkali"].iterrows():
        cc = {"GR": "EL", "UK": "GB"}.get(row.Country, row.Country)
        if cc not in EU27:
            continue
        ll = fixes.get(str(row.City).strip()) or _dms(row.Coordinates)
        if not ll:
            continue
        chlor.append((f"{row.Company} {row.City}".strip(), cc, ll[0], ll[1], float(row["Capacity (kt Cl/a)"])))

    P, unplaced = [], []
    for ind, lst in plants.items():
        for r in R.values():
            r.setdefault("cap", {})[ind] = 0.0
        for n, cc, lat, lon, c in lst:
            rid = locate(lon, lat, CFG["snap_km"]["industrial_site"])
            if not rid or rid[:2] != cc:
                unplaced.append(f"{ind}: {n} ({cc})")
                continue
            R[rid]["cap"][ind] += c
            xx, yy = proj(lon, lat)
            P.append(dict(i=ind, n=n, r=rid, c=round(c), x=round(xx / 1000, 1), y=round(yy / 1000, 1)))
    for r in R.values():
        r["chlor"] = 0
    for n, cc, lat, lon, c in chlor:
        rid = locate(lon, lat, CFG["snap_km"]["industrial_site"])
        if rid and rid[:2] == cc:
            R[rid]["chlor"] += c
            xx, yy = proj(lon, lat)
            P.append(dict(i="chlor", n=n, r=rid, c=round(c), x=round(xx / 1000, 1), y=round(yy / 1000, 1)))
    ctx["plants"] = P
    units = {"steel": "kt crude steel", "cement": "kt clinker", "ammonia": "kt NH3", "chemicals": "kt ethylene", "aluminium": "kt primary Al"}
    for ind in plants:
        n = sum(1 for p in P if p["i"] == ind)
        cap = sum(r["cap"][ind] for r in R.values())
        ctx["qa"].append(f"- {ind.capitalize()}: {n} sites, {cap:,.0f} {units[ind]}")
    ctx["qa"].append(f"- Chlor-alkali cluster markers: {sum(1 for p in P if p['i'] == 'chlor')}")
    ctx["qa"].append(f"- Unplaced sites: {len(unplaced)}" + ("" if not unplaced else " (" + "; ".join(unplaced) + ")"))
    return ctx


# --------------------------------------------------------------------------------------------
# Step 8 · Policy and geology layers: congestion scores, salt caverns, national nuclear policy
# --------------------------------------------------------------------------------------------
def s8_policy(ctx):
    R = ctx["R"]
    cong = dict(read_manual("grid_congestion_scores.csv")[["nuts_prefix", "score"]].itertuples(index=False))
    cav = list(read_manual("salt_caverns.csv").nuts_prefix)
    nuc = read_manual("nuclear_policy.csv")
    banned = set(nuc.loc[nuc.new_reactors_allowed == 0, "country_code"])
    for r in R.values():
        s, best = 0.0, 0
        for pre, v in cong.items():                                   # longest matching prefix wins
            if r["id"].startswith(pre) and len(pre) > best:
                s, best = v, len(pre)
        r["cong"] = s
        r["cav"] = 1 if any(r["id"].startswith(p) for p in cav) else 0
        r["nban"] = 1 if r["cc"] in banned else 0
    ctx["qa"].append(f"- Congestion: {sum(1 for r in R.values() if r['cong'] != 0)} regions with a non-zero score")
    ctx["qa"].append(f"- Salt caverns: {sum(r['cav'] for r in R.values())} regions; nuclear new build barred in: {', '.join(sorted(banned))}")
    return ctx


# --------------------------------------------------------------------------------------------
# Step 9 · Export: data/processed/data.json (read by the model and the map) + flat CSVs
# --------------------------------------------------------------------------------------------
def _rnd(c, nd):
    if isinstance(c[0], (float, int)):
        return [round(c[0] / 1000, nd), round(c[1] / 1000, nd)] if nd else [round(c[0] / 1000), round(c[1] / 1000)]
    return [_rnd(cc, nd) for cc in c]


def s9_export(ctx, out_dir):
    R, S = ctx["R"], CFG["geometry_simplify_m"]
    geo = []
    for i, f in zip(ctx["ids"], ctx["feats"]):
        m = mapping(shape(f["geometry"]).simplify(S["regions"]))
        geo.append(dict(type="Feature", id=i, geometry=dict(type=m["type"], coordinates=_rnd(m["coordinates"], 1))))
    cnt = json.loads((NUTS / "cntrg_2024_3035_20M.json").read_text(encoding="utf-8"))
    bg = []
    for f in cnt["features"]:
        if f["properties"]["id"] in EU27:
            continue
        g = shape(f["geometry"]).buffer(0).simplify(S["countries"])
        if g.is_empty:
            continue
        m = mapping(g)
        bg.append(dict(type="Feature", id=f["properties"]["id"], geometry=dict(type=m["type"], coordinates=_rnd(m["coordinates"], 0))))
    regions = []
    for r in R.values():
        regions.append(dict(
            id=r["id"], na=r["na"], cc=r["cc"], lat=round(r["lat"], 2), lon=round(r["lon"], 2),
            cx=round(r["cx"], 1), cy=round(r["cy"], 1), area=round(r["area"]), pop=round(r["pop"]),
            urb=round(r["urb"], 3), pv=round(r["pv"], 4), won=round(r["won"], 3), coast=round(r["coast"]),
            basin=r["basin"], coff=r["coff"], kxoff=r["kxoff"], n380=r["n380"], n220=r["n220"], cong=r["cong"],
            e=dict(pv=round(r["e_pv"]), won=round(r["e_won"]), woff=round(r["e_woff"]), hres=round(r["e_hres"]), hror=round(r["e_hror"])),
            cap={k: round(v, 1) for k, v in r["cap"].items()}, chlor=round(r["chlor"]), cav=r["cav"], nban=r["nban"]))
    data = dict(regions=regions, geo=geo, bg=bg, plants=ctx["plants"], subs=ctx["subs"], lines=ctx["lines"])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "data.json").write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    flat = pd.json_normalize(regions, sep="_")
    flat.columns = [c.replace("e_", "existing_mw_", 1) if c.startswith("e_") else c.replace("cap_", "capacity_kt_", 1) if c.startswith("cap_") else c for c in flat.columns]
    flat.to_csv(out_dir / "regions.csv", index=False, encoding="utf-8")
    pd.DataFrame(ctx["plants"]).rename(columns={"i": "industry", "n": "name", "r": "nuts2", "c": "capacity_kt", "x": "x_km_epsg3035", "y": "y_km_epsg3035"}) \
        .to_csv(out_dir / "plants.csv", index=False, encoding="utf-8")
    ctx["qa"].append(f"- Export: data.json {len(json.dumps(data, separators=(',', ':'))):,} bytes; regions.csv; plants.csv")
    return ctx
