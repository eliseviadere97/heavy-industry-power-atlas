"""The seven data-preparation steps. Each step takes and returns the shared context dict `ctx`.

ctx["R"]       ordered dict of regions keyed by NUTS-2 id (the model's spatial unit)
ctx["locate"]  Locator for NUTS-2 polygons
ctx["plants"]  list of industrial sites with today's output
ctx["qa"]      lines written to outputs/qa_report.md
"""
import json
import re

import numpy as np
import pandas as pd
from shapely import wkt
from shapely.geometry import LineString, mapping, shape
from shapely.ops import unary_union

from common import CFG, CONFIG, COUNTRIES, COUNTRY_CODES, DERIVED, RAW, Locator, proj, read_manual

NUTS = RAW / "nuts2json"
SECTORS = {s["k"]: s for s in CONFIG["model"]["sectors"]}


# --------------------------------------------------------------------------------------------
# Step 1 · Regions: NUTS-2 polygons. NUTS 2024 for the EU27, Norway and Switzerland; NUTS 2016 for
# the UK, which left the NUTS system after Brexit. Outermost regions, Ceuta, Melilla and Svalbard dropped.
# --------------------------------------------------------------------------------------------
def load_regions():
    excl = tuple(CFG["excluded_nuts_prefixes"])
    old = set(CFG["nuts2016_countries"])
    feats, pts = [], {}
    for year, keep in [("2024", lambda cc: cc not in old), ("2016", lambda cc: cc in old)]:
        rg = json.loads((NUTS / f"nutsrg_2_{year}_3035_20M.json").read_text(encoding="utf-8"))
        feats += [f for f in rg["features"] if f["properties"]["id"][:2] in COUNTRIES and keep(f["properties"]["id"][:2])
                  and not f["properties"]["id"].startswith(excl)]
        pts.update({f["properties"]["id"]: f for f in json.loads((NUTS / f"nutspt_2_{year}_4326.json").read_text(encoding="utf-8"))["features"]})
    return feats, pts


def s1_regions(ctx):
    feats, pts = load_regions()
    ids = [f["properties"]["id"] for f in feats]
    geoms = [shape(f["geometry"]).buffer(0) for f in feats]
    R = {}
    for i, f in zip(ids, feats):
        lon, lat = pts[i]["geometry"]["coordinates"]
        x, y = proj(lon, lat)
        R[i] = dict(id=i, na=f["properties"]["na"], cc=i[:2], area=pts[i]["properties"]["ar"] / 1e6,   # km²
                    lon=lon, lat=lat, cx=x / 1000, cy=y / 1000)
    ctx.update(R=R, feats=feats, geoms=geoms, ids=ids, locate=Locator(ids, geoms))
    n = {c: sum(1 for r in R.values() if r["cc"] == c) for c in COUNTRIES}
    ctx["qa"].append(f"- Regions: {len(R)} NUTS-2 regions in {len(COUNTRIES)} countries (UK on NUTS 2016: {n['UK']}; NO {n['NO']}; CH {n['CH']})")
    return ctx


# --------------------------------------------------------------------------------------------
# Step 2 · Population (Eurostat demo_r_d2jan, 1 January) and density
# --------------------------------------------------------------------------------------------
def _eurostat(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    dims, size = d["id"], d["size"]
    stride = {k: int(np.prod(size[i + 1:])) for i, k in enumerate(dims)}
    geo = d["dimension"]["geo"]["category"]["index"]
    inv = {v: k for k, v in geo.items()}
    return {inv[(int(k) // stride["geo"]) % size[dims.index("geo")]]: v for k, v in d["value"].items()}


def s2_population(ctx):
    R, Y = ctx["R"], CFG["population_year"]
    pop = {y: _eurostat(RAW / "eurostat" / f"demo_r_d2jan_nuts2_{y}.json") for y in set(Y.values())}
    over = dict(read_manual("population_overrides.csv")[["nuts2", "population"]].itertuples(index=False))
    missing = []
    for r in R.values():
        y = Y.get(r["cc"], Y["default"])
        r["pop"] = pop[y].get(r["id"], over.get(r["id"]))
        if r["pop"] is None:
            missing.append(r["id"])
            r["pop"] = 0
        r["dens"] = r["pop"] / r["area"]
    total = sum(r["pop"] for r in R.values()) / 1e6
    ctx["qa"].append(f"- Population: {total:,.1f} million (Eurostat demo_r_d2jan, {Y['default']}; UK {Y['UK']})"
                     + (f"; missing: {', '.join(missing)}" if missing else ""))
    return ctx


# --------------------------------------------------------------------------------------------
# Step 3 · Weather: monthly solar (PVGIS) and day/night onshore wind (EMHIRES) capacity factors.
# The tables in data/derived/ are built by src/data_prep/fetch_weather.py.
# --------------------------------------------------------------------------------------------
def s3_weather(ctx):
    R = ctx["R"]
    pv = pd.read_csv(DERIVED / "pv_monthly_cf.csv").set_index("nuts2")
    wd = pd.read_csv(DERIVED / "wind_monthly_cf.csv").set_index("nuts2")
    months = [f"{m:02d}" for m in range(1, 13)]
    for r in R.values():
        r["pv"] = [float(pv.loc[r["id"], f"cf_{m}"]) for m in months]
        r["wd"] = [float(wd.loc[r["id"], f"day_{m}"]) for m in months]
        r["wn"] = [float(wd.loc[r["id"], f"night_{m}"]) for m in months]
    days = np.array([31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
    pa = [np.dot(r["pv"], days) / days.sum() for r in R.values()]
    wa = [np.dot((np.array(r["wd"]) + np.array(r["wn"])) / 2, days) / days.sum() for r in R.values()]
    ctx["qa"].append(f"- Weather: solar capacity factor {min(pa):.1%}–{max(pa):.1%}, onshore wind {min(wa):.1%}–{max(wa):.1%} (annual means by region)")
    return ctx


# --------------------------------------------------------------------------------------------
# Step 4 · Transmission grid: count >=330 kV substations per region; keep >=220 kV lines for display
# --------------------------------------------------------------------------------------------
def s4_grid(ctx):
    R, locate, G = ctx["R"], ctx["locate"], CFG["grid"]
    bus = pd.read_csv(RAW / "pypsa_eur" / "entsoegridkit_buses.csv", quotechar="'")
    bus = bus[(bus.voltage >= G["high_voltage_kv"]) & (bus.dc == "f") & (bus.under_construction == "f")]
    for r in R.values():
        r["n330"] = 0
    for b in bus.itertuples(index=False):
        rid = locate(b.x, b.y, CFG["snap_km"]["substation"])
        if rid:
            R[rid]["n330"] += 1
    lines = pd.read_csv(RAW / "pypsa_eur" / "entsoegridkit_lines.csv", quotechar="'")
    lines = lines[(lines.voltage >= G["min_voltage_kv"]) & (lines.under_construction == False)]  # noqa: E712
    area = unary_union(ctx["geoms"]).buffer(20000)
    L = []
    for l in lines.itertuples(index=False):
        g = wkt.loads(l.geometry)
        xs, ys = zip(*g.coords)
        X, Y = proj(xs, ys)
        g2 = LineString(zip(X, Y))
        if not g2.intersects(area):
            continue
        g2 = g2.simplify(G["line_simplify_m"])
        L.append([1 if l.voltage >= G["high_voltage_kv"] else 0, [[round(x / 1000, 1), round(y / 1000, 1)] for x, y in g2.coords]])
    ctx["lines"] = L
    n = sum(1 for r in R.values() if r["n330"] > 0)
    ctx["qa"].append(f"- Grid: {sum(r['n330'] for r in R.values())} substations >=330 kV; {n} of {len(R)} regions have at least one")
    return ctx


# --------------------------------------------------------------------------------------------
# Step 5 · Industrial sites and today's output per site
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


MANUAL_NOTE = "hand-compiled list (data/manual)"


def _site(ind, name, cc, lat, lon, cap, status="operating", basis="capacity", source=MANUAL_NOTE, verification=""):
    return dict(ind=ind, name=name, cc=cc, lat=lat, lon=lon, cap=float(cap), status=status, basis=basis, source=source, verification=verification)


def _manual(ind, file, cap_col, scale=1):
    df = read_manual(file)
    return [_site(ind, r["name"], r["country_code"], r["lat"], r["lon"], r[cap_col] * scale, r.get("status", "operating"),
                  verification=r.get("verification", "")) for _, r in df.iterrows()]


def s5_plants(ctx):
    R, locate = ctx["R"], ctx["locate"]
    sites = []
    sites += _manual("steel", "steel_plants.csv", "crude_steel_capacity_mt", 1000)
    sites += _manual("aluminium", "aluminium_smelters.csv", "primary_al_capacity_kt")
    sites += _manual("chemicals", "steam_crackers.csv", "ethylene_capacity_kt")
    # cement: EU ETS 2014 (else 2013) verified emissions / t CO2 per t clinker = that year's clinker OUTPUT
    x = pd.read_excel(RAW / "troendle_2019" / "energy-intensive-industries.xlsx", sheet_name="Act 29 (cement clinker)")
    drop = list(read_manual("cement_exclusions.csv").name_contains)
    ef = CFG["cement"]["t_co2_per_t_clinker"]
    for _, row in x.iterrows():
        cc = {"GR": "EL", "GB": "UK"}.get(row.REGISTRY_CODE, row.REGISTRY_CODE)
        if cc not in COUNTRIES or not isinstance(row.Coordinates, str) or any(d in str(row.INSTALLATION_NAME) for d in drop):
            continue
        ll = _dms(row.Coordinates)
        em = row.VERIFIED_EMISSIONS_2014 if row.VERIFIED_EMISSIONS_2014 > 0 else row.VERIFIED_EMISSIONS_2013
        if not ll or not em or em <= 0:
            continue
        sites.append(_site("cement", str(row.INSTALLATION_NAME).strip().title()[:40], cc, ll[0], ll[1], em / (ef * 1000),
                           basis="output", source="EU ETS verified emissions 2014 (Tröndle et al. 2019)",
                           verification="clinker output = emissions / 0.83 t CO2 per t; coordinates from source"))
    sites += _manual("cement", "cement_additions.csv", "clinker_capacity_kt")
    # ammonia: PyPSA-Eur list, capacity gaps filled, sites added
    fills = dict(read_manual("ammonia_capacity_fills.csv")[["plant", "ammonia_capacity_kt"]].itertuples(index=False))
    am = pd.read_csv(RAW / "pypsa_eur" / "ammonia_plants.csv")
    for _, a in am.iterrows():
        cc = COUNTRY_CODES.get(a.Country)
        if not cc:
            continue
        given = not np.isnan(a["Ammonia [kt/a]"])
        cap = a["Ammonia [kt/a]"] if given else fills.get(a.Plant, 0)
        if cap <= 0:
            continue
        sites.append(_site("ammonia", a.Plant, cc, a.Latitude, a.Longitude, cap,
                           source="PyPSA-Eur ammonia_plants.csv" if given else "capacity from data/manual/ammonia_capacity_fills.csv",
                           verification="" if given else "capacity not individually verified"))
    sites += _manual("ammonia", "ammonia_additions.csv", "ammonia_capacity_kt")

    P, unplaced = [], []
    for s in sites:
        rid = locate(s["lon"], s["lat"], CFG["snap_km"]["industrial_site"])
        if not rid or rid[:2] != s["cc"]:
            unplaced.append(f"{s['ind']}: {s['name']} ({s['cc']})")
            continue
        sec = SECTORS[s["ind"]]
        if s["status"] != "operating":
            out = 0.0
        elif s["basis"] == "output":
            out = s["cap"]
        else:
            out = s["cap"] * sec["utilisation"]
        x, y = proj(s["lon"], s["lat"])
        P.append(dict(s, r=rid, out=out, x=x / 1000, y=y / 1000))
    for r in R.values():
        r["cap"] = {k: 0.0 for k in SECTORS}
    for p in P:
        if p["out"] > 0:
            R[p["r"]]["cap"][p["ind"]] += p["cap"]
    ctx["plants"] = P
    for k, sec in SECTORS.items():
        ps = [p for p in P if p["ind"] == k]
        live = [p for p in ps if p["out"] > 0]
        out = sum(p["out"] for p in ps)
        ctx["qa"].append(f"- {sec['name']}: {len(ps)} sites ({len(live)} producing), output {out:,.0f} {sec['unit']}, "
                         f"demand {out * sec['mwh_per_t'] / 1000:,.0f} TWh at {sec['mwh_per_t']} MWh/t")
    ctx["qa"].append(f"- Unplaced sites: {len(unplaced)}" + ("" if not unplaced else " (" + "; ".join(unplaced) + ")"))
    return ctx


# --------------------------------------------------------------------------------------------
# Step 6 · National policy on new nuclear reactors
# --------------------------------------------------------------------------------------------
def s6_policy(ctx):
    nuc = read_manual("nuclear_policy.csv")
    banned = set(nuc.loc[nuc.new_reactors_allowed == 0, "country_code"])
    for r in ctx["R"].values():
        r["nban"] = 1 if r["cc"] in banned else 0
    ctx["qa"].append(f"- Nuclear new build barred in: {', '.join(sorted(banned))}")
    return ctx


# --------------------------------------------------------------------------------------------
# Step 7 · Export: data/processed/data.json (read by the model and the map), flat CSVs, and the
# plant lists for human review (outputs/review/plant_lists_for_review.xlsx)
# --------------------------------------------------------------------------------------------
def _rnd(c, nd):
    if isinstance(c[0], (float, int)):
        return [round(c[0] / 1000, nd), round(c[1] / 1000, nd)] if nd else [round(c[0] / 1000), round(c[1] / 1000)]
    return [_rnd(cc, nd) for cc in c]


def _review_sheet(P, R, path):
    cols = {"name": "Plant", "cc": "Country", "r": "NUTS-2", "region": "Region", "lat": "Lat", "lon": "Lon", "status": "Status",
            "cap": "Capacity (kt/yr)", "basis": "Capacity basis", "out": "Output used (kt/yr)", "twh": "Power demand (TWh/yr)",
            "source": "Source", "verification": "Verification note"}
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        notes = pd.DataFrame({"How to use": [
            "One sheet per sector. Check each row: does the plant exist, is it the right technology, are location, capacity and status right?",
            "Status: operating plants carry output; idle or closed plants carry none.",
            "Capacity basis 'capacity' = nameplate, output = capacity × the sector's utilisation; 'output' = the value already is annual output (EU ETS cement rows).",
            "Fill in the last three columns. Corrections go back into data/manual/*.csv (or a new manual file for ETS cement rows).",
            "Missing plants: add a row at the bottom with name, country, coordinates, capacity and status."]})
        notes.to_excel(xw, sheet_name="Read me", index=False)
        for k, sec in SECTORS.items():
            rows = []
            for p in sorted((p for p in P if p["ind"] == k), key=lambda p: (p["cc"], p["name"])):
                rows.append({**{c: p.get(c) for c in cols}, "region": R[p["r"]]["na"], "twh": round(p["out"] * sec["mwh_per_t"] / 1000, 2),
                             "cap": round(p["cap"]), "out": round(p["out"])})
            df = pd.DataFrame(rows)[list(cols)].rename(columns=cols)
            df["Reviewer: correct? (Y/N)"] = ""
            df["Reviewer: corrected value"] = ""
            df["Reviewer: comment and source"] = ""
            df.to_excel(xw, sheet_name=sec["name"][:31], index=False)
            ws = xw.sheets[sec["name"][:31]]
            for col, w in zip("ABCDEFGHIJKLMNOP", [38, 8, 8, 28, 7, 7, 10, 10, 10, 10, 10, 34, 40, 12, 16, 40]):
                ws.column_dimensions[col].width = w
            ws.freeze_panes = "B2"


def s7_export(ctx, out_dir, review_dir):
    R, S = ctx["R"], CFG["geometry_simplify_m"]
    geo = []
    for i, f in zip(ctx["ids"], ctx["feats"]):
        m = mapping(shape(f["geometry"]).simplify(S["regions"]))
        geo.append(dict(type="Feature", id=i, geometry=dict(type=m["type"], coordinates=_rnd(m["coordinates"], 1))))
    cnt = json.loads((NUTS / "cntrg_2024_3035_20M.json").read_text(encoding="utf-8"))
    bg = []
    for f in cnt["features"]:
        if f["properties"]["id"] in COUNTRIES:
            continue
        g = shape(f["geometry"]).buffer(0).simplify(S["countries"])
        if g.is_empty:
            continue
        m = mapping(g)
        bg.append(dict(type="Feature", id=f["properties"]["id"], geometry=dict(type=m["type"], coordinates=_rnd(m["coordinates"], 0))))
    regions = []
    for r in R.values():
        regions.append(dict(
            id=r["id"], na=r["na"], cc=r["cc"], lat=round(r["lat"], 2), lon=round(r["lon"], 2), cx=round(r["cx"], 1), cy=round(r["cy"], 1),
            area=round(r["area"]), pop=round(r["pop"]), pv=[round(v, 4) for v in r["pv"]], wd=[round(v, 4) for v in r["wd"]],
            wn=[round(v, 4) for v in r["wn"]], n330=r["n330"], cap={k: round(v, 1) for k, v in r["cap"].items()}, nban=r["nban"]))
    plants = [dict(i=p["ind"], n=p["name"] + ("" if p["status"] == "operating" else f" ({p['status']})"), r=p["r"], c=round(p["cap"]),
                   o=round(p["out"], 1), x=round(p["x"], 1), y=round(p["y"], 1)) for p in ctx["plants"]]
    data = dict(regions=regions, geo=geo, bg=bg, plants=plants, lines=ctx["lines"])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "data.json").write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    flat = []
    for r in regions:
        row = {k: v for k, v in r.items() if k not in ("pv", "wd", "wn", "cap")}
        row.update({f"pv_cf_{m + 1:02d}": v for m, v in enumerate(r["pv"])})
        row.update({f"wind_cf_day_{m + 1:02d}": v for m, v in enumerate(r["wd"])})
        row.update({f"wind_cf_night_{m + 1:02d}": v for m, v in enumerate(r["wn"])})
        row.update({f"capacity_kt_{k}": v for k, v in r["cap"].items()})
        flat.append(row)
    pd.DataFrame(flat).to_csv(out_dir / "regions.csv", index=False, encoding="utf-8")
    pd.DataFrame([{k: p[k] for k in ("ind", "name", "cc", "r", "lat", "lon", "status", "cap", "basis", "out", "source")} for p in ctx["plants"]]) \
        .rename(columns={"ind": "industry", "cc": "country", "r": "nuts2", "cap": "capacity_kt", "out": "output_kt"}) \
        .to_csv(out_dir / "plants.csv", index=False, encoding="utf-8")
    review_dir.mkdir(parents=True, exist_ok=True)
    _review_sheet(ctx["plants"], R, review_dir / "plant_lists_for_review.xlsx")
    ctx["qa"].append(f"- Export: data.json {len(json.dumps(data, separators=(',', ':'))):,} bytes; regions.csv; plants.csv; review/plant_lists_for_review.xlsx")
    return ctx
