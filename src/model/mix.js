// =====================================================================================
// mix.js — least-cost local power mix for one sector class in one NUTS-2 region
// -------------------------------------------------------------------------------------
// Load is normalised to 1 MW average; the objective is in €/MWh of plant demand.
// The year is 24 slices: 12 months × day/night (12 hours each), weighted by their hours.
//   Solar: PVGIS monthly capacity factor, all of it produced in the day slice.
//   Wind:  EMHIRES monthly capacity factor, separately for day (06-18 UTC) and night.
// Supply is islanded ("behind the meter"): no grid import, no unabated gas. Every slice must be
// covered by the plant's own solar, wind, batteries, hydrogen storage, SMRs or gas with capture.
// See docs/METHODOLOGY.md §3. Runs in the browser and in Node (src/run/run_scenarios.js).
// Requires the javascript-lp-solver global `solver` and globalThis.MODEL_CONFIG.
// =====================================================================================

const TECHS = [
  { k: "pv", name: "Solar PV", c: "--t-pv" },
  { k: "on", name: "Onshore wind", c: "--t-on" },
  { k: "smr", name: "SMR", c: "--t-smr" },
  { k: "ccs", name: "Gas + CCS", c: "--t-ccs" },
];

const MIX_DEFAULTS = { ...globalThis.MODEL_CONFIG.model.mix };
const DAYS = [31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

function crfOf(w, n) { return w / (1 - Math.pow(1 + w, -n)); }

// 24 slices from the region's monthly capacity factors (r.pv, r.wd, r.wn: arrays of 12)
function slices(r) {
  const out = [];
  for (let m = 0; m < 12; m++) for (const td of ["day", "night"]) {
    out.push({ m, td, H: DAYS[m] * 12,
      pv: td === "day" ? Math.min(1, 2 * r.pv[m]) : 0,
      on: td === "day" ? r.wd[m] : r.wn[m] });
  }
  return out;
}

// Annualised costs per MW of capacity divided by 8,760 -> €/MWh of 1 MW flat load; variable costs in €/MWh.
// One cost of capital (P.wacc) for every technology.
function unitCosts(P) {
  const A = (capex, n, om) => (capex * 1000 * (crfOf(P.wacc, n) + om)) / 8760;
  const ccsCO2 = P.gasEf / P.ccsEff;                                  // t CO2 per MWh electricity
  return {
    pv: A(P.pvCapex, P.pvLife, P.pvOm), on: A(P.wCapex, P.wLife, P.wOm),
    bat: A(P.batKwh * P.batHours, P.batLife, P.batOm),
    el: A(P.elCapex, P.elLife, P.elOm),
    // hydrogen storage volume, per day of flat electrolyser load (24 MWh of electricity-equivalent)
    h2s: (24 * P.h2PerMwhEl * P.h2StoreKwh * 1000 * (crfOf(P.wacc, P.h2StoreLife) + P.h2StoreOm)) / 8760,
    smr: (P.smrCapex * 1000 * crfOf(P.wacc, P.smrLife) + P.smrFom * 1000) / 8760, smrV: P.smrVar,
    ccs: (P.ccsCapex * 1000 * crfOf(P.wacc, P.ccsLife) + P.ccsFom * 1000) / 8760,
    ccsV: P.gasPrice / P.ccsEff + ccsCO2 * P.ccsCapture * P.ccsTs + ccsCO2 * (1 - P.ccsCapture) * P.co2 + P.ccsVom,
  };
}

// Build the LP in javascript-lp-solver format. h = flexible (electrolyser) share of the load.
// opts.noVRE: the no-new-renewables fallback used when a region's land is exhausted.
function buildLP(r, h, P, opts = {}) {
  const S = slices(r), U = unitCosts(P), T = S.reduce((a, s) => a + s.H, 0);
  const nukeOK = P.smrOn && !(P.smrBans && r.nban), vre = !opts.noVRE;
  const V = {}, C = {};
  const v = (name, cost) => (V[name] = V[name] || { cost }, V[name]);
  S.forEach((s, i) => { C["bal" + i] = { min: 1 - h }; });          // steady load in every slice
  if (vre) {
    const pv = v("PV", U.pv), on = v("ON", U.on);
    S.forEach((s, i) => { pv["bal" + i] = s.pv; on["bal" + i] = s.on; });
    if (P.batOn) {                                                  // charge by day, discharge the same month's nights
      const B = v("BAT", U.bat);
      for (let m = 0; m < 12; m++) {
        const di = 2 * m, ni = 2 * m + 1;
        C["be" + m] = { max: 0 };                                   // nightly discharge <= battery energy (hours/12 of MW)
        C["bq" + m] = { equal: 0 };                                 // discharge = efficiency × charge
        const bc = v("bc" + m, 0), bd = v("bd" + m, 0);
        bc["bal" + di] = -1; bd["bal" + ni] = 1;
        bd["be" + m] = 1; B["be" + m] = -P.batHours / 12;
        bd["bq" + m] = 1; bc["bq" + m] = -P.batEta;
      }
    }
  }
  if (nukeOK) { const N = v("SMR", U.smr); S.forEach((s, i) => { C["sm" + i] = { max: 0 }; const n = v("n" + i, U.smrV * s.H / T); n["bal" + i] = 1; n["sm" + i] = 1; N["sm" + i] = -P.smrAvail; }); }
  if (P.ccsOn) { const G = v("CCS", U.ccs); S.forEach((s, i) => { C["cc" + i] = { max: 0 }; const g = v("g" + i, U.ccsV * s.H / T); g["bal" + i] = 1; g["cc" + i] = 1; G["cc" + i] = -P.ccsAvail; }); }
  if (h > 0) {
    const flex = P.h2On && vre;
    if (!flex) {
      S.forEach((s, i) => { C["bal" + i] = { min: 1 }; });           // electrolysers run flat with the rest of the plant
    } else {
      // e = electrolyser draw, c/d = into/out of storage (MW electricity-equivalent), L = stored hydrogen (days of 1 MW)
      const X = v("ELX", U.el), VOL = v("VOL", U.h2s);              // only electrolyser capacity ABOVE flat running is costed
      S.forEach((s, i) => {
        const e = v("e" + i, 0), c = v("c" + i, 0), d = v("d" + i, 0), L = v("L" + i, 0);
        e["bal" + i] = -1;
        C["fl" + i] = { equal: h }; e["fl" + i] = 1; c["fl" + i] = -1; d["fl" + i] = 1;   // downstream hydrogen use is flat
        C["ex" + i] = { max: h }; e["ex" + i] = 1; X["ex" + i] = -1;
        C["sl" + i] = { equal: 0 };                                 // L_i = L_(i-1) + (eff × c - d) × hours / 24, cyclic
        L["sl" + i] = 1; c["sl" + i] = -P.h2StoreEff * s.H / 24; d["sl" + i] = s.H / 24;
        const prev = (i + S.length - 1) % S.length;
        V["L" + prev] = V["L" + prev] || { cost: 0 };
        C["lv" + i] = { max: 0 }; L["lv" + i] = 1; VOL["lv" + i] = -1;
      });
      S.forEach((s, i) => { const prev = (i + S.length - 1) % S.length; V["L" + prev]["sl" + i] = -1; });
    }
  }
  return { optimize: "cost", opType: "min", constraints: C, variables: V, _S: S, _h: h, _T: T };
}

function solveMix(r, h, P, opts = {}) {
  const m = buildLP(r, h, P, opts);
  const res = solver.Solve(m);
  if (!res.feasible) return { cost: Infinity, feasible: false };
  const g = (k) => res[k] || 0, S = m._S, T = m._T, flex = h > 0 && P.h2On && !opts.noVRE;
  const cap = { pv: g("PV"), on: g("ON"), bat: g("BAT"), elx: g("ELX"), vol: g("VOL"), smr: g("SMR"), ccs: g("CCS") };
  // E: delivered energy by source (solar and wind net of curtailment), shares summing to 1
  // St: storage throughput per MWh of demand (battery discharge, hydrogen drawn from storage)
  const E = { pv: 0, on: 0, smr: 0, ccs: 0 }, St = { bat: 0, h2: 0 };
  S.forEach((s, i) => {
    const w = s.H / T, avail = { pv: cap.pv * s.pv, on: cap.on * s.on };
    const firm = g("n" + i) + g("g" + i);
    const bd = s.td === "night" ? g("bd" + s.m) : 0, bc = s.td === "day" ? g("bc" + s.m) : 0;
    const need = (flex ? 1 - h + g("e" + i) : 1) + bc;
    const vreTot = avail.pv + avail.on;
    const vreUsed = Math.max(0, Math.min(vreTot, need - firm - bd));
    const f = vreTot > 0 ? vreUsed / vreTot : 0;
    E.pv += avail.pv * f * w; E.on += avail.on * f * w;
    E.smr += g("n" + i) * w; E.ccs += g("g" + i) * w;
    St.bat += bd * w; if (flex) St.h2 += g("d" + i) * w;
  });
  const tot = Object.values(E).reduce((a, b) => a + b, 0) || 1;
  for (const k in E) E[k] /= tot;
  return { cost: res.result, feasible: true, cap, E, St };
}

if (typeof module !== "undefined") module.exports = { TECHS, MIX_DEFAULTS, DAYS, slices, unitCosts, buildLP, solveMix, crfOf };
