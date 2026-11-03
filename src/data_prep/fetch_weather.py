"""Build the two weather tables in data/derived/ that the data preparation reads (step 3).

  pv_monthly_cf.csv    solar PV capacity factor by NUTS-2 region and month
                       = PVGIS monthly yield of a 1 kWp fixed, optimally tilted system (14% system losses,
                         PVGIS-ERA5, 2005-2023 average) / hours in the month, averaged over up to 6 points
                         spread inside the region
  wind_monthly_cf.csv  onshore wind capacity factor by NUTS-2 region, month, day (06-18 UTC) and night
                       = mean of the JRC EMHIRES hourly NUTS-2 series 1986-2015 (wind fleet of end-2015),
                         mapped from NUTS 2016 (EMHIRES June 2019 codes) to the model's regions by area overlap

Downloads go to data/cache/ (git-ignored): the EMHIRES file is 561 MB; PVGIS answers are cached per point.
Run once, or again to refresh:  python src/data_prep/fetch_weather.py [--only pv|wind]
"""
import argparse
import json
import time
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import Point, shape

from common import CACHE, CFG, DERIVED, RAW, TI
from steps import load_regions

MONTHS = [f"{m:02d}" for m in range(1, 13)]
DAYS = np.array([31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])


def regions():
    feats, pts = load_regions()
    return [(f["properties"]["id"], shape(f["geometry"]).buffer(0), pts[f["properties"]["id"]]["geometry"]["coordinates"]) for f in feats]


# ---------------------------------------------------------------------------------------------- solar
def sample_points(geom, label, n):
    """Up to n points on a regular grid inside the polygon (EPSG:3035), as lon/lat; the label point if none fit."""
    minx, miny, maxx, maxy = geom.bounds
    for k in (1.0, 0.7, 0.5, 0.35, 0.25):
        step = k * (geom.area / n) ** 0.5
        xs, ys = np.arange(minx + step / 2, maxx, step), np.arange(miny + step / 2, maxy, step)
        pts = [(x, y) for x in xs for y in ys if geom.contains(Point(x, y))]
        if len(pts) >= n:
            break
    if len(pts) > n:
        pts = [pts[int(i)] for i in np.linspace(0, len(pts) - 1, n)]
    if not pts:
        return [tuple(label)]
    return [tuple(round(v, 3) for v in TI.transform(x, y)) for x, y in pts]


def pvgis(lon, lat):
    P = CFG["pvgis"]
    f = CACHE / "pvgis" / f"{lat:.3f}_{lon:.3f}.json"
    if not f.exists():
        q = dict(lat=lat, lon=lon, peakpower=1, loss=P["system_loss_pct"], optimalangles=1, raddatabase=P["raddatabase"], outputformat="json")
        url = P["api"] + "?" + urllib.parse.urlencode(q)
        for attempt in range(5):
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    f.write_bytes(r.read())
                break
            except Exception as e:  # PVGIS rate limit (30/s) or a point over water: retry, then give up
                if attempt == 4:
                    print(f"  PVGIS failed at {lat},{lon}: {e}")
                    return None
                time.sleep(2 * (attempt + 1))
    d = json.loads(f.read_text())
    return [m["E_m"] for m in d["outputs"]["monthly"]["fixed"]]          # kWh per kWp per month


def build_pv(R):
    (CACHE / "pvgis").mkdir(parents=True, exist_ok=True)
    jobs = [(rid, p) for rid, geom, label in R for p in sample_points(geom, label, CFG["pvgis"]["points_per_region"])]
    print(f"PVGIS: {len(jobs)} points for {len(R)} regions")
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda j: pvgis(*j[1]), jobs))
    rows = {}
    for (rid, _), e in zip(jobs, res):
        if e:
            rows.setdefault(rid, []).append(e)
    out = []
    for rid, _, _ in R:
        E = np.mean(rows[rid], axis=0)
        out.append({"nuts2": rid, "points": len(rows[rid]), **{f"cf_{m}": round(e / (24 * d), 4) for m, e, d in zip(MONTHS, E, DAYS)},
                    "annual_kwh_per_kwp": round(E.sum())})
    df = pd.DataFrame(out)
    df.to_csv(DERIVED / "pv_monthly_cf.csv", index=False)
    print(f"  wrote data/derived/pv_monthly_cf.csv ({len(df)} regions, yield {df.annual_kwh_per_kwp.min()}–{df.annual_kwh_per_kwp.max()} kWh/kWp)")


# ---------------------------------------------------------------------------------------------- wind
def emhires_monthly():
    """Monthly day/night means of every EMHIRES NUTS-2 column (cached: reading the 562 MB workbook takes minutes)."""
    agg = CACHE / "emhires_monthly_daynight.csv"
    if agg.exists():
        return pd.read_csv(agg, index_col=0)
    xl = CACHE / "EMHIRES_WIND_NUTS2_June2019.xlsx"
    if not xl.exists():
        z = CACHE / "EMHIRES_WIND_ONSHORE_NUTS2.zip"
        if not z.exists():
            print("Downloading EMHIRES (561 MB)…")
            urllib.request.urlretrieve(CFG["emhires"]["url"], z)
        zipfile.ZipFile(z).extractall(CACHE)
    from python_calamine import CalamineWorkbook
    it = CalamineWorkbook.from_path(str(xl)).get_sheet_by_index(0).iter_rows()
    cols = next(it)[1:]
    h0, h1 = CFG["emhires"]["day_hours_utc"]
    keys = [f"{dn}_{m}" for dn in ("day", "night") for m in MONTHS]
    S, N = np.zeros((len(keys), len(cols))), np.zeros((len(keys), len(cols)))
    t = pd.Timestamp("1986-01-01")
    buf, idx = [], []

    def flush():
        X = pd.DataFrame(buf).apply(pd.to_numeric, errors="coerce").to_numpy(float)   # empty cells -> NaN
        ok = ~np.isnan(X)
        np.add.at(S, idx, np.where(ok, X, 0))
        np.add.at(N, idx, ok)

    for row in it:                                                    # stream one year at a time (79 M values in all)
        if not isinstance(row[0], (int, float)) or row[0] == "":
            continue
        buf.append(row[1:])
        idx.append(keys.index(f"{'day' if h0 <= t.hour < h1 else 'night'}_{t.month:02d}"))
        t += pd.Timedelta(hours=1)
        if len(buf) == 8760:
            flush()
            buf, idx = [], []
    if buf:
        flush()
    with np.errstate(invalid="ignore"):
        df = pd.DataFrame(S / N, index=keys, columns=cols).T
    df = df.dropna(how="all")
    df.to_csv(agg)
    return df


def build_wind(R):
    E = emhires_monthly().rename(index={"DECOO": "DEC0"})              # typo in the source column header
    g16 = json.loads((RAW / "nuts2json" / "nutsrg_2_2016_3035_20M.json").read_text(encoding="utf-8"))
    G = {f["properties"]["id"]: shape(f["geometry"]).buffer(0) for f in g16["features"] if f["properties"]["id"] in E.index}
    out, fallback = [], []
    for rid, geom, _ in R:
        w = {k: geom.intersection(g).area for k, g in G.items() if geom.intersects(g)}
        w = {k: v for k, v in w.items() if v > 0.01 * geom.area}
        if not w:                                                     # no overlap: nearest EMHIRES region
            c = geom.representative_point()
            k = min(G, key=lambda k: G[k].distance(c))
            w = {k: 1.0}
            fallback.append(f"{rid}<-{k}")
        tot = sum(w.values())
        row = sum(E.loc[k] * v / tot for k, v in w.items())
        out.append({"nuts2": rid, "emhires_regions": " ".join(sorted(w)), **{c: round(row[c], 4) for c in sorted(row.index)}})
    df = pd.DataFrame(out)
    df.to_csv(DERIVED / "wind_monthly_cf.csv", index=False)
    ann = df[[c for c in df.columns if c[:3] in ("day", "nig")]].mean(axis=1)
    print(f"  wrote data/derived/wind_monthly_cf.csv ({len(df)} regions, annual CF {ann.min():.1%}–{ann.max():.1%})"
          + (f"; nearest-region fallback: {', '.join(fallback)}" if fallback else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["pv", "wind"])
    a = ap.parse_args()
    DERIVED.mkdir(parents=True, exist_ok=True)
    R = regions()
    if a.only != "wind":
        build_pv(R)
    if a.only != "pv":
        build_wind(R)


if __name__ == "__main__":
    main()
