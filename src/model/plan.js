// =====================================================================================
// plan.js — relocation planner: whole plants of fixed size, each with its own optimal local mix
// -------------------------------------------------------------------------------------
// Three scenarios share one routine:
//   "stay"   every plant stays at home, powered by the best mix its home region allows;
//   "first"  social planner, free hand: plants may move to any region; only land and weather bind;
//   "second" the planner under the ticked constraints (grid, existing renewables, industrial ecosystem).
// Plants are indivisible and keep their size and electricity demand wherever they go. Plants that share
// a region share its wind/solar potential; the remainder of a plant's load falls back to the region's
// no-new-renewables mix. Solved by greedy construction + single-plant local search from two starts.
// See docs/METHODOLOGY.md §4-5. Requires globalThis.MODEL_CONFIG (= config/model_config.json).
// =====================================================================================

const IND = globalThis.MODEL_CONFIG.model.industries.map((i) => ({
  ...i, routes: i.routes.map((r) => [r.name, r.mwh_per_t, r.flex_share]),   // [name, MWh/t, flexible share]
}));
const PLAN_DEFAULTS = { ...globalThis.MODEL_CONFIG.model.plan };
const RE_CF = globalThis.MODEL_CONFIG.model.existing_re_cf;

// Annual output of the region's existing wind, solar and hydro (TWh/yr), from installed MW x capacity factor
function existingRE(r) {
  return ((r.e.pv * r.pv + r.e.won * r.won + r.e.woff * (r.coff || RE_CF.offshore_if_no_basin)
    + r.e.hres * RE_CF.hydro_reservoir + r.e.hror * RE_CF.hydro_run_of_river) * 8760) / 1e6;
}

// Wind/solar capacity (MW) open to industry in each region, after reserving local demand; plus the
// second-best caps (new renewables vs existing output, grid headroom for relocated load).
function regionResources(R, P, scenario) {
  return R.map((r) => {
    const urbLand = Math.min(0.95, (r.pop * r.urb) / P.urbanDensity / r.area);
    const A = r.area * (1 - urbLand);
    let pv = A * P.pvLand * P.pvDens, on = A * P.wLand * P.wDens, off = P.offshore && r.coff ? r.coast * P.offDens : 0;
    const potE = (pv * r.pv + on * r.won + off * (r.coff || 0)) * 8.76e-3;
    const sc = potE > 0 ? Math.max(0, 1 - (r.pop * P.reserve) / 1e6 / potE) : 0;
    pv *= sc; on *= sc; off *= sc;
    const second = scenario === "second";
    const re = second && P.cRE ? P.reK * existingRE(r) : Infinity;
    const host = second && P.cGrid ? (r.n380 * P.h380 + r.n220 * P.h220) * 8.76e-3 * (P.cCong ? Math.max(0, 1 - r.cong) : 1) : Infinity;
    return { pv, on, off, re, host, potTWh: potE * sc };
  });
}

// plants: [{i (industry key), n, home (region idx), c (capacity)}]; mixes: {A:{h:[per region]}, B:{h:[per region]}}
function plan(R, plants, cfg, mixes, P, scenario) {
  const N = R.length;
  const res0 = regionResources(R, P, scenario);
  const D = {}; IND.forEach((ind) => { const c = cfg[ind.k]; D[ind.k] = c.on ? c.out * c.int : 0; });
  const capTot = {}; plants.forEach((p) => (capTot[p.i] = (capTot[p.i] || 0) + p.c));
  const PL = plants.filter((p) => cfg[p.i].on && D[p.i] > 0).map((p) => {
    const E = (p.c / capTot[p.i]) * D[p.i];                 // TWh/yr, fixed wherever the plant goes
    return { ...p, E, L: (E * 1e6) / 8760, h: cfg[p.i].h };
  });
  const second = scenario === "second";
  const eligible = PL.map((p) => {
    const ok = new Uint8Array(N);
    for (let j = 0; j < N; j++) {
      if (j === p.home) { ok[j] = 1; continue; }
      if (scenario === "stay") continue;
      const r = R[j];
      if (second && P.cEco) {
        const e = P.ecoMode === "same" ? r.cap[p.i] > 0 || (p.i === "chemicals" && r.chlor > 0)
                                       : IND.some((x) => r.cap[x.k] > 0) || r.chlor > 0;
        if (!e) continue;
      }
      if (second && P.cGrid && p.L > P.bigMW && r.n380 < 1) continue;
      ok[j] = 1;
    }
    return ok;
  });
  const budget = {};
  IND.forEach((ind) => (budget[ind.k] = second && P.cEco ? (1 - P.alpha) * (capTot[ind.k] || 0) : Infinity));

  const A = (p, j) => mixes.A[p.h][j], B = (p, j) => mixes.B[p.h][j];
  const unitB = (p, j) => { const b = B(p, j); return b && b.feasible ? b.cost : P.unserved; };
  const unitA = (p, j) => { const a = A(p, j); return a && a.feasible ? a.cost : Infinity; };

  // pack the plants sitting in region j: those gaining most from local renewables get them first
  function regionCost(j, set) {
    if (!set.length) return { cost: 0, f: [] };
    const rs = res0[j];
    let pv = rs.pv, on = rs.on, off = rs.off, re = rs.re, cost = 0;
    const ord = set.slice().sort((x, y) => (unitB(PL[y], j) - unitA(PL[y], j)) - (unitB(PL[x], j) - unitA(PL[x], j)) || PL[y].E - PL[x].E);
    const f = {};
    for (const q of ord) {
      const p = PL[q], a = A(p, j), ub = unitB(p, j), ua = unitA(p, j);
      let fq = 0;
      if (isFinite(ua) && ua < ub) {
        fq = 1;
        const need = [[a.cap.pv * p.L, pv], [a.cap.on * p.L, on], [a.cap.off * p.L, off], [(a.vreGen * p.L) / 1e6, re]];
        for (const [n, have] of need) if (n > 1e-9) fq = Math.min(fq, Math.max(0, have) / n);
        pv -= fq * a.cap.pv * p.L; on -= fq * a.cap.on * p.L; off -= fq * a.cap.off * p.L; re -= (fq * a.vreGen * p.L) / 1e6;
      }
      f[q] = fq;
      cost += p.E * (fq * (isFinite(ua) ? ua : 0) + (1 - fq) * ub) + (j !== p.home ? p.E * P.relocPrem : 0);
    }
    return { cost, f };
  }

  const loc = PL.map((p) => p.home);
  const sets = Array.from({ length: N }, () => []);
  const hostUsed = new Float64Array(N);
  const moved = {}; IND.forEach((i) => (moved[i.k] = 0));
  function place(q, j) { loc[q] = j; sets[j].push(q); if (j !== PL[q].home) { hostUsed[j] += PL[q].E; moved[PL[q].i] += PL[q].c; } }
  function unplace(q) { const j = loc[q]; sets[j].splice(sets[j].indexOf(q), 1); if (j !== PL[q].home) { hostUsed[j] -= PL[q].E; moved[PL[q].i] -= PL[q].c; } loc[q] = -1; }
  const canGo = (q, j) => {
    const p = PL[q];
    if (!eligible[q][j]) return false;
    if (j === p.home) return true;
    if (hostUsed[j] + p.E > res0[j].host + 1e-9) return false;
    const alreadyMoved = loc[q] >= 0 && loc[q] !== p.home;
    if (!alreadyMoved && moved[p.i] + p.c > budget[p.i] + 1e-6) return false;
    return true;
  };

  function localSearch() {
    const costR = sets.map((s, j) => regionCost(j, s).cost);
    const order = PL.map((_, q) => q).sort((x, y) => PL[y].E - PL[x].E);
    for (let pass = 0; pass < 12; pass++) {
      let improved = 0;
      for (const q of order) {
        const j0 = loc[q];
        unplace(q);
        const s0 = sets[j0], c0new = regionCost(j0, s0).cost;
        let best = j0, bestD = 0;
        const base = costR[j0];
        for (let j = 0; j < N; j++) {
          if (j === j0 || !canGo(q, j)) continue;
          const cj = regionCost(j, sets[j].concat([q])).cost;
          const d = (c0new + cj) - (base + costR[j]);
          if (d < bestD - 1e-6) { bestD = d; best = j; }
        }
        if (best !== j0) {
          place(q, best); costR[j0] = c0new; costR[best] = regionCost(best, sets[best]).cost; improved++;
        } else place(q, j0);
      }
      if (!improved) break;
    }
  }
  function totalCost() { let c = 0; for (let j = 0; j < N; j++) c += regionCost(j, sets[j]).cost; return c; }
  function snapshot() { return loc.slice(); }
  function restore(L) { for (let j = 0; j < N; j++) sets[j] = []; hostUsed.fill(0); IND.forEach((i) => (moved[i.k] = 0)); loc.fill(-1); L.forEach((j, q) => place(q, j)); }

  // start 1: today's sites
  PL.forEach((p, q) => place(q, p.home));
  if (scenario !== "stay") {
    localSearch();
    let best = snapshot(), bestC = totalCost();
    // start 2: constructive greedy, biggest plants first
    for (let j = 0; j < N; j++) sets[j] = []; hostUsed.fill(0); IND.forEach((i) => (moved[i.k] = 0)); loc.fill(-1);
    const order = PL.map((_, q) => q).sort((x, y) => PL[y].E - PL[x].E);
    for (const q of order) {
      let bj = PL[q].home, bd = Infinity;
      for (let j = 0; j < N; j++) {
        if (!canGo(q, j)) continue;
        const d = regionCost(j, sets[j].concat([q])).cost - regionCost(j, sets[j]).cost;
        if (d < bd) { bd = d; bj = j; }
      }
      place(q, bj);
    }
    localSearch();
    const c2 = totalCost();
    if (c2 >= bestC) restore(best);
  }

  // outputs
  const out = { plants: [], tot: new Float64Array(N), byInd: Array.from({ length: N }, () => ({})), mix: {}, st: {}, unserved: 0, cost: 0, E: 0, moved: 0, movedE: 0, nPlants: PL.length };
  for (let j = 0; j < N; j++) {
    if (!sets[j].length) continue;
    const rc = regionCost(j, sets[j]);
    for (const q of sets[j]) {
      const p = PL[q], fq = rc.f[q], a = A(p, j), b = B(p, j), ua = unitA(p, j), ub = unitB(p, j);
      const unit = fq * (isFinite(ua) ? ua : 0) + (1 - fq) * ub;
      const mix = {}, st = {};
      const add = (m, w) => { if (!m || !m.feasible) return; for (const k in m.E) mix[k] = (mix[k] || 0) + m.E[k] * w; for (const k in m.St) st[k] = (st[k] || 0) + m.St[k] * w; };
      add(a, fq); add(b, 1 - fq);
      const uns = b && b.feasible ? 0 : (1 - fq) * p.E;
      out.unserved += uns;
      out.plants.push({ q, n: p.n, i: p.i, home: p.home, loc: j, E: p.E, c: p.c, f: fq, unit, mix, st, x: p.x, y: p.y, uns });
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
  out.res0 = res0;
  return out;
}

if (typeof module !== "undefined") module.exports = { IND, PLAN_DEFAULTS, plan, regionResources, existingRE };
