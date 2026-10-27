"""Step C of the pipeline: re-solve a sample of the local-mix LPs with HiGHS (via SciPy) and check that
the in-browser solver (javascript-lp-solver) finds the same optimum.

Reads outputs/validation/lp_sample.json written by src/run/run_scenarios.js.
Writes outputs/validation/lp_check.csv. Exits with an error if any objective differs by > 0.01 €/MWh.

Usage:  python src/validation/validate_lp.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linprog

ROOT = Path(__file__).resolve().parents[2]
VAL = ROOT / "outputs" / "validation"
TOL = 0.01


def solve_highs(m):
    V, C = list(m["variables"]), list(m["constraints"])
    c = np.array([m["variables"][v].get("cost", 0) for v in V])
    A_ub, b_ub, A_eq, b_eq = [], [], [], []
    for k in C:
        con = m["constraints"][k]
        row = np.array([m["variables"][v].get(k, 0) for v in V], float)
        if "equal" in con:
            A_eq.append(row); b_eq.append(con["equal"])
        if "max" in con:
            A_ub.append(row); b_ub.append(con["max"])
        if "min" in con:
            A_ub.append(-row); b_ub.append(-con["min"])
    r = linprog(c, A_ub=np.array(A_ub) if A_ub else None, b_ub=b_ub or None,
                A_eq=np.array(A_eq) if A_eq else None, b_eq=b_eq or None, bounds=(0, None), method="highs")
    return r.fun if r.status == 0 else float("inf")


def main():
    items = json.loads((VAL / "lp_sample.json").read_text())
    rows = []
    for it in items:
        h = solve_highs(it["model"])
        rows.append(dict(nuts2=it["id"], flex_share=it["h"], no_new_renewables=it["noVRE"],
                         js_eur_per_mwh=it["obj"], highs_eur_per_mwh=h, abs_diff=abs(it["obj"] - h)))
    df = pd.DataFrame(rows)
    df.to_csv(VAL / "lp_check.csv", index=False)
    worst = df.abs_diff.max()
    print(f"LP check: {len(df)} problems, worst absolute difference {worst:.5f} €/MWh")
    if worst > TOL:
        print(df[df.abs_diff > TOL].to_string())
        sys.exit("LP check failed: browser solver and HiGHS disagree")


if __name__ == "__main__":
    main()
