"""Optional: re-download every raw file from its pinned source and check it against the stored SHA-256.

The raw files are already in data/raw/, so this is only needed to audit provenance or to rebuild data/raw
from scratch. URLs point at fixed commits, so the files cannot drift.

Usage:  python src/data_prep/fetch_raw.py [--dest data/raw] [--check-only]
"""
import argparse
import csv
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = json.loads((ROOT / "data" / "raw" / "sources.json").read_text(encoding="utf-8"))
EU = {"AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "GR", "ES", "FI", "FR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
      "NL", "PL", "PT", "RO", "SE", "SI", "SK"}


def geonames_subset(path):
    import geonamescache  # pip install geonamescache==3.0.2
    rows = [c for c in geonamescache.GeonamesCache().get_cities().values() if c["countrycode"] in EU]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["geonameid", "name", "countrycode", "latitude", "longitude", "population"])
        for c in sorted(rows, key=lambda c: int(c["geonameid"])):
            w.writerow([c["geonameid"], c["name"], c["countrycode"], c["latitude"], c["longitude"], c["population"]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=str(ROOT / "data" / "raw"))
    ap.add_argument("--check-only", action="store_true", help="only verify the files already in --dest")
    a = ap.parse_args()
    dest, bad = Path(a.dest), 0
    for s in SOURCES:
        p = dest / s["file"]
        if not a.check_only:
            p.parent.mkdir(parents=True, exist_ok=True)
            if s["url"].startswith("http"):
                urllib.request.urlretrieve(s["url"], p)
            else:
                geonames_subset(p)
        ok = p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() == s["sha256"]
        bad += not ok
        print(f"{'OK  ' if ok else 'FAIL'} {s['file']}")
    if bad:
        raise SystemExit(f"{bad} file(s) do not match the recorded SHA-256")


if __name__ == "__main__":
    main()
