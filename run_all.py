"""Run the whole pipeline: raw data -> processed data -> model results -> solver checks -> web page.

    python run_all.py              # everything
    python run_all.py --skip-data  # reuse data/processed (e.g. after editing only config/model_config.json)

Requires Python packages in requirements.txt and Node.js 18+ with `npm ci` run once. The weather tables in
data/derived/ are built separately (once) by src/data_prep/fetch_weather.py.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def step(label, cmd):
    t = time.time()
    print(f"\n=== {label} ===", flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)
    print(f"--- {label}: {time.time() - t:.1f} s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-data", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    if not args.skip_data:
        step("A · Data preparation", [sys.executable, "src/data_prep/run_data_prep.py"])
    step("B · Model runs (local mixes, relocation planner, sensitivities)", ["node", "src/run/run_scenarios.js"])
    step("C1 · Local mixes: solver check against HiGHS", [sys.executable, "src/validation/validate_lp.py"])
    step("C2 · Plant placement: heuristic vs exact optimum", [sys.executable, "src/validation/validate_plan.py"])
    step("D · Build the web page", [sys.executable, "src/site/build_site.py"])
    print(f"\nAll done in {time.time() - t0:.1f} s. Open site/index.html in a browser.")


if __name__ == "__main__":
    main()
