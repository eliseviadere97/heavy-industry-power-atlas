// =====================================================================================
// plan.js — relocation planner: whole plants, each powered by its region's least-cost local mix
// -------------------------------------------------------------------------------------
// Step 1 (mix.js) prices every sector class in every region. Step 2 (here) places the plants:
//   "stay"   every plant at home;
//   "first"  any region; only land binds;
//   "second" a plant may leave home only for a region with a >=330 kV substation and, if ticked,
//            one that already hosts its industry; part of each industry must stay.
// Plants keep their output and demand wherever they go. Plants in one region share its land for
// solar and wind; the rest of a plant's load runs on the region's no-new-renewables mix.
// Solved by greedy construction + local search (single moves and pairwise swaps) from two starts;
// src/validation/validate_plan.py checks the result against the exact optimum (HiGHS MILP).
// See docs/METHODOLOGY.md §4-5. Requires globalThis.MODEL_CONFIG.
// =====================================================================================

const SECTORS = globalThis.MODEL_CONFIG.model.sectors;
const PLAN_DEFAULTS = { ...globalThis.MODEL_CONFIG.model.plan };

// Land open to solar and wind (km²): a share of the land not taken by settlements
function regionLand(R, P) {
  return R.map((r) => r.area * (1 - Math.min(0.95, r.pop / P.urbanDensity / r.area)) * P.landShare);
}

// Plants with demand: [{i, n, home, o, x, y}] -> adds E (TWh/yr) and L (MW of average load)
function plantLoads(plants, cfg) {
  return plants.filter((p) => cfg[p.i].on && p.o > 0).map((p) => {
    const E = (p.o * cfg[p.i].int) / 1000;
    return { ...p, E, L: (E * 1e6) / 8760, h: cfg[p.i].h };
  });
}

// mixes: {A: {h: [per region]}, B: {h: [per region]}} from mix.js
function plan(R, plants, cfg, mixes, P, scenario) {
  const N = R.length, land0 = regionLand(R, P), PL = plantLoads(plants, cfg);
  const second = scenario === "second";
  const unitA = (p, j) => { const a = mixes.A[p.h][j]; return a && a.feasible ? a.cost : Infinity; };
  const unitB = (p, j) => { const b = mixes.B[p.h][j]; return b && b.feasible ? b.cost : P.infeasible; };
  const kmA = (p, j) => { const a = mixes.A[p.h][j]; return a && a.feasible ? a.cap.pv / P.pvDens + a.cap.on / P.wDens : 0; }; // km² per MW of load
  const eligible = PL.map((p) => {
    const ok = new Uint8Array(N);
    for (let j = 0; j < N; j++) {
      if (j === p.home) { ok[j] = 1; continue; }
      if (scenario === "stay") continue;
      if (second && P.cGrid && R[j].n330 < 1) continue;
      if (second && P.cEco && !(R[j].cap[p.i] > 0)) continue;
      ok[j] = 1;
    }
    return ok;
  });
  const total = {}; PL.forEach((p) => (total[p.i] = (total[p.i] || 0) + p.o));
  const budget = {}; SECTORS.forEach((s) => (budget[s.k] = second && P.cEco ? (1 - P.alpha) * (total[s.k] || 0) : Infinity));

  // Plants sharing region j: fractional knapsack on land, highest saving per km² first (optimal for one resource)
  function regionCost(j, set) {
    if (!set.length) return { cost: 0, f: {}, full: false };
    let left = land0[j], cost = 0;
    const f = {};
    const gain = (q) => { const p = PL[q], k = kmA(p, j); return k > 0 ? (unitB(p, j) - unitA(p, j)) / k : -Infinity; };
    for (const q of set.slice().sort((x, y) => gain(y) - gain(x))) {
      const p = PL[q], ua = unitA(p, j), ub = unitB(p, j);
      let fq = 0;
      if (isFinite(ua) && ua < ub) { const need = kmA(p, j) * p.L; fq = need > 0 ? Math.min(1, Math.max(0, left) / need) : 1; left -= fq * need; }
      f[q] = fq;
      cost += p.E * (fq * (isFinite(ua) ? ua : 0) + (1 - fq) * ub) + (j !== p.home ? p.E * P.relocPrem : 0);
    }
    return { cost, f, full: left < 1e-6 * land0[j] };
  }

  const loc = PL.map((p) => p.home), sets = Array.from({ length: N }, () => []);
  const moved = {}; SECTORS.forEach((s) => (moved[s.k] = 0));
  const place = (q, j) => { loc[q] = j; sets[j].push(q); if (j !== PL[q].home) moved[PL[q].i] += PL[q].o; };
  const unplace = (q) => { const j = loc[q]; sets[j].splice(sets[j].indexOf(q), 1); if (j !== PL[q].home) moved[PL[q].i] -= PL[q].o; loc[q] = -1; };
  const budgetOK = (q, j) => j === PL[q].home || moved[PL[q].i] + PL[q].o <= budget[PL[q].i] + 1e-6;   // q currently unplaced
  const totalCost = () => sets.reduce((c, s, j) => c + regionCost(j, s).cost, 0);
  const reset = () => { for (let j = 0; j < N; j++) sets[j] = []; SECTORS.forEach((s) => (moved[s.k] = 0)); loc.fill(-1); };

  // Visit plants in order of what moving could save: in total (€), or per tonne of moving allowance when
  // part of each industry must stay (the allowance then goes to the plants that gain most per tonne).
  const rationed = second && P.cEco;
  const saving = PL.map((p, q) => {
    let best = Infinity;
    for (let j = 0; j < N; j++) if (eligible[q][j]) best = Math.min(best, regionCost(j, [q]).cost);
    const s = regionCost(p.home, [q]).cost - best;
    return rationed ? s / p.o : s;
  });
  const order = PL.map((_, q) => q).sort((x, y) => saving[y] - saving[x] || PL[y].E - PL[x].E);

  function localSearch() {
    const costR = sets.map((s, j) => regionCost(j, s).cost);
    for (let pass = 0; pass < 20; pass++) {
      let improved = 0;
      for (const q of order) {                                     // single-plant moves
        const j0 = loc[q];
        unplace(q);
        const c0 = regionCost(j0, sets[j0]).cost;
        let best = j0, bestD = -1e-6;
        for (let j = 0; j < N; j++) {
          if (j === j0 || !eligible[q][j] || !budgetOK(q, j)) continue;
          const d = c0 + regionCost(j, sets[j].concat([q])).cost - costR[j0] - costR[j];
          if (d < bestD) { bestD = d; best = j; }
        }
        place(q, best);
        if (best !== j0) { costR[j0] = c0; costR[best] = regionCost(best, sets[best]).cost; improved++; }
      }
      // pairwise swaps; only useful where land runs out in at least one of the two regions
      const full = sets.map((st, j) => regionCost(j, st).full);
      for (let a = 0; a < PL.length; a++) for (let b = a + 1; b < PL.length; b++) {
        const ja = loc[a], jb = loc[b];
        if (ja === jb || !(full[ja] || full[jb]) || !eligible[a][jb] || !eligible[b][ja]) continue;
        unplace(a); unplace(b);
        const ok = budgetOK(a, jb) && (() => { place(a, jb); const r = budgetOK(b, ja); unplace(a); return r; })();
        if (ok) {
          const sa = sets[ja].concat([b]), sb = sets[jb].concat([a]);
          const ca = regionCost(ja, sa).cost, cb = regionCost(jb, sb).cost;
          if (ca + cb < costR[ja] + costR[jb] - 1e-6) { place(a, jb); place(b, ja); costR[ja] = ca; costR[jb] = cb; improved++; continue; }
        }
        place(a, ja); place(b, jb);
      }
      if (!improved) break;
    }
  }

  PL.forEach((p, q) => place(q, p.home));                          // start 1: today's sites
  if (scenario !== "stay") {
    localSearch();
    const best = loc.slice(), bestC = totalCost();
    reset();                                                       // start 2: greedy, biggest savings first
    for (const q of order) {
      let bj = PL[q].home, bd = Infinity;
      for (let j = 0; j < N; j++) {
        if (!eligible[q][j] || !budgetOK(q, j)) continue;
        const d = regionCost(j, sets[j].concat([q])).cost - regionCost(j, sets[j]).cost;
        if (d < bd) { bd = d; bj = j; }
      }
      place(q, bj);
    }
    localSearch();
    if (totalCost() >= bestC) { reset(); best.forEach((j, q) => place(q, j)); }
  }

  const out = { plants: [], tot: new Float64Array(N), byInd: Array.from({ length: N }, () => ({})), mix: {}, st: {},
    uncovered: 0, cost: 0, E: 0, moved: 0, movedE: 0, nPlants: PL.length, land: land0, landUsed: new Float64Array(N) };
  for (let j = 0; j < N; j++) {
    if (!sets[j].length) continue;
    const rc = regionCost(j, sets[j]);
    for (const q of sets[j]) {
      const p = PL[q], fq = rc.f[q], a = mixes.A[p.h][j], b = mixes.B[p.h][j], ua = unitA(p, j), ub = unitB(p, j);
      const unit = fq * (isFinite(ua) ? ua : 0) + (1 - fq) * ub;
      const mix = {}, st = {};
      const add = (m, w) => { if (!m || !m.feasible || w <= 0) return; for (const k in m.E) mix[k] = (mix[k] || 0) + m.E[k] * w; for (const k in m.St) st[k] = (st[k] || 0) + m.St[k] * w; };
      add(a, fq); add(b, 1 - fq);
      const unc = b && b.feasible ? 0 : (1 - fq) * p.E;              // load with no feasible supply (only if SMR and CCS are both unavailable)
      out.uncovered += unc;
      out.landUsed[j] += fq * kmA(p, j) * p.L;
      out.plants.push({ q, n: p.n, i: p.i, home: p.home, loc: j, E: p.E, o: p.o, f: fq, unit, mix, st, x: p.x, y: p.y, unc });
      out.tot[j] += p.E; out.byInd[j][p.i] = (out.byInd[j][p.i] || 0) + p.E;
      for (const k in mix) out.mix[k] = (out.mix[k] || 0) + mix[k] * p.E;
      for (const k in st) out.st[k] = (out.st[k] || 0) + st[k] * p.E;
      out.cost += p.E * unit + (j !== p.home ? p.E * P.relocPrem : 0); out.E += p.E;
      if (j !== p.home) { out.moved++; out.movedE += p.E; }
    }
  }
  out.avg = out.E ? out.cost / out.E : 0;
  out.bn = out.cost / 1000;
  out.used = Array.from(out.tot).filter((x) => x > 1e-6).length;
  return out;
}

if (typeof module !== "undefined") module.exports = { SECTORS, PLAN_DEFAULTS, plan, plantLoads, regionLand };
