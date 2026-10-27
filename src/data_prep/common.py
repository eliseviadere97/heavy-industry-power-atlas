"""Shared paths, configuration, projections and the region locator used by every data-prep step."""
import json
from pathlib import Path

import pandas as pd
from pyproj import Transformer
from shapely.geometry import Point
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
MANUAL = ROOT / "data" / "manual"
PROCESSED = ROOT / "data" / "processed"
CONFIG = json.loads((ROOT / "config" / "model_config.json").read_text(encoding="utf-8"))
CFG = CONFIG["data_prep"]
EU27 = CFG["eu27"]

# WGS84 lon/lat <-> ETRS89-LAEA (EPSG:3035, metres). All areas, lengths and the map use EPSG:3035.
T = Transformer.from_crs(4326, CFG["projected_crs"], always_xy=True)
TI = Transformer.from_crs(CFG["projected_crs"], 4326, always_xy=True)


def proj(lon, lat):
    return T.transform(lon, lat)


# Country names used by powerplantmatching and the PyPSA-Eur ammonia list -> Eurostat codes
COUNTRY_CODES = {
    "Austria": "AT", "Belgium": "BE", "Bulgaria": "BG", "Croatia": "HR", "Czechia": "CZ", "Denmark": "DK",
    "Estonia": "EE", "Finland": "FI", "France": "FR", "Germany": "DE", "Greece": "EL", "Hungary": "HU",
    "Ireland": "IE", "Italy": "IT", "Latvia": "LV", "Lithuania": "LT", "Luxembourg": "LU", "Netherlands": "NL",
    "Poland": "PL", "Portugal": "PT", "Romania": "RO", "Slovakia": "SK", "Slovenia": "SI", "Spain": "ES",
    "Sweden": "SE", "Cyprus": "CY", "Malta": "MT",
}


def read_manual(name):
    """Hand-compiled inputs live in data/manual/*.csv, each row with its source and verification status."""
    return pd.read_csv(MANUAL / name, encoding="utf-8")


class Locator:
    """Point-in-polygon lookup of NUTS-2 regions, with an optional snap distance for points just offshore
    or on a border (coastal plants, offshore wind farms, substations on the boundary)."""

    def __init__(self, ids, geoms):
        self.ids, self.geoms = ids, geoms
        self.tree = STRtree(geoms)

    def __call__(self, lon, lat, max_km=0):
        x, y = proj(lon, lat)
        p = Point(x, y)
        for i in self.tree.query(p, predicate="within"):
            return self.ids[i]
        if max_km:
            i = self.tree.nearest(p)
            if self.geoms[i].distance(p) < max_km * 1000:
                return self.ids[i]
        return None
