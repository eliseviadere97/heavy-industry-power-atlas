"""Step C (part 2): solve the default planning problems exactly and measure the heuristic's gap.

The page and src/run/run_scenarios.js place plants with a fast heuristic (src/model/plan.js). Here the same
problem is written as a mixed-integer programme and solved to optimality with HiGHS (via SciPy):

  min  sum_p,j  E_p * ( cB_pj * x_pj - (cB_pj - cA_pj) * y_pj )
  s.t. sum_j x_pj = 1                      every plant sits in exactly one region
       y_pj <= x_pj                         share of the plant's load on the renewables mix
       sum_p km_pj * L_p * y_pj <= land_j   land for solar and wind in each region
       sum_(p in i, j != home) o_p x_pj <= (1 - alpha) * sum_(p in i) o_p    (second best, clusters)
       x binary, 0 <= y <= 1;  x_pj fixed to 0 where region j is not allowed for plant p

Reads outputs/validation/plan_problem.json written by src/run/run_scenarios.js.
Each solve is capped at TIME_LIMIT seconds. If HiGHS has not closed the gap by then, the check uses its proven
lower bound instead of the optimum, so the reported gap is an upper bound on the heuristic's true gap.

Writes outputs/validation/plan_check.csv. Exits with an error if the heuristic is more than 1% above the bound.

Usage:  python src/validation/validate_plan.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

ROOT = Path(__file__).resolve().parents[2]
VAL = ROOT / "outputs" / "validation"
TOL = 0.01
TIME_LIMIT = 120


def solve(d, scenario):
    P, R, land, plants = d["P"], d["regions"], d["land"], d["plants"]
    U = {float(h): v for h, v in d["unit"].items()}
    cols, cost = [], []                                                # columns: (kind, plant, region)
    for q, p in enumerate(plants):
        u = U[p["h"]]
        ua = lambda j: u[j][0] if u[j][0] is not None else np.inf
        ub = lambda j: u[j][1] if u[j][1] is not None else P["infeasible"]
        home_cost = ub(p["home"])
        fallback_kept = False
        for j in range(len(R)):
            if j != p["home"]:
                if scenario == "stay":
                    continue
                if scenario == "second" and P["cGrid"] and R[j]["n330"] < 1:
                    continue
                if scenario == "second" and P["cEco"] and not R[j]["cap"].get(p["i"], 0) > 0:
                    continue
                if min(ua(j), ub(j)) >= home_cost - 1e-9:                # can never beat staying home: drop (exact)
                    continue
                if ua(j) >= ub(j):                                     # fallback-only regions are interchangeable
                    if fallback_kept:
                        continue
                    fallback_kept = True
            prem = P["relocPrem"] if j != p["home"] else 0
            cols.append(("x", q, j)); cost.append(p["E"] * (ub(j) + prem))
            if ua(j) < ub(j):
                cols.append(("y", q, j)); cost.append(-p["E"] * (ub(j) - ua(j)))
    n = len(cols)
    rows, cidx, vals, lo, hi = [], [], [], [], []
    r = 0
    xcols, byplant = {}, {}
    for c, (k, q, j) in enumerate(cols):
        if k == "x":
            xcols[(q, j)] = c
            byplant.setdefault(q, []).append(c)
    for q in range(len(plants)):                                       # one region per plant
        for c in byplant[q]:
            rows.append(r); cidx.append(c); vals.append(1)
        lo.append(1); hi.append(1); r += 1
    landrow = {}
    for c, (k, q, j) in enumerate(cols):
        if k != "y":
            continue
        rows += [r, r]; cidx += [c, xcols[(q, j)]]; vals += [1, -1]; lo.append(-np.inf); hi.append(0); r += 1
        if j not in landrow:
            landrow[j] = []
        p = plants[q]
        landrow[j].append((c, U[p["h"]][j][2] * p["L"]))
    for j, items in landrow.items():                                   # land in each region
        for c, v in items:
            rows.append(r); cidx.append(c); vals.append(v)
        lo.append(-np.inf); hi.append(land[j]); r += 1
    if scenario == "second" and P["cEco"]:                             # part of each industry stays
        for ind in sorted({p["i"] for p in plants}):
            tot = sum(p["o"] for p in plants if p["i"] == ind)
            for (q, j), c in xcols.items():
                if plants[q]["i"] == ind and j != plants[q]["home"]:
                    rows.append(r); cidx.append(c); vals.append(plants[q]["o"])
            lo.append(-np.inf); hi.append((1 - P["alpha"]) * tot); r += 1
    A = coo_matrix((vals, (rows, cidx)), shape=(r, n)).tocsr()
    integrality = np.array([1 if k == "x" else 0 for k, _, _ in cols])
    t = time.time()
    res = milp(np.array(cost), constraints=LinearConstraint(A, lo, hi), integrality=integrality, bounds=Bounds(0, 1),
               options={"mip_rel_gap": 1e-4, "time_limit": TIME_LIMIT})
    if res.x is None:
        raise SystemExit(f"{scenario}: MILP failed ({res.message})")
    moved = sum(1 for c, (k, q, j) in enumerate(cols) if k == "x" and res.x[c] > 0.5 and j != plants[q]["home"])
    bound = getattr(res, "mip_dual_bound", None)
    bound = res.fun if res.status == 0 or bound is None or not np.isfinite(bound) else bound
    return res.fun, bound, res.status == 0, moved, n, time.time() - t


def main():
    d = json.loads((VAL / "plan_problem.json").read_text())
    rows = []
    for sc in ["stay", "second", "first"]:
        best, bound, proven, moved, n, secs = solve(d, sc)
        h = d["heuristic"][sc]
        r = dict(scenario=sc, heuristic_bn_eur=h["cost"] / 1000, milp_best_bn_eur=best / 1000, lower_bound_bn_eur=bound / 1000,
                 proven_optimal=proven, gap=(h["cost"] - bound) / bound, heuristic_moved=h["moved"], milp_moved=moved,
                 variables=n, seconds=round(secs, 1))
        rows.append(r)
        print(f"Plan check {sc:<7} heuristic €{r['heuristic_bn_eur']:.3f}bn; MILP best €{r['milp_best_bn_eur']:.3f}bn, "
              f"{'optimal' if proven else 'bound €%.3fbn' % r['lower_bound_bn_eur']}; heuristic gap <= {r['gap']:.2%} "
              f"(moved {r['heuristic_moved']} vs {r['milp_moved']}; {n} variables, {r['seconds']} s)", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(VAL / "plan_check.csv", index=False)
    if df.gap.max() > TOL:
        sys.exit("Plan check failed: heuristic more than 1% above the exact optimum")


if __name__ == "__main__":
    main()
