// =====================================================================================
// mix.js — least-cost local power mix for one industry class in one NUTS-2 region
// -------------------------------------------------------------------------------------
// Load is normalised to 1 MW average (8,760 MWh/yr); the objective is in €/MWh of plant demand.
// The year is split into 8 equal slices: season (winter/summer) x wind state (windy/calm) x
// time of day (day/night). Each slice's capacity factors are derived from the region's ANNUAL
// AVERAGE solar and wind capacity factors with fixed shape rules (config: model.slices), so only
// averages are needed as weather input. See docs/METHODOLOGY.md §3 for the full formulation.
//
// Runs in the browser (bundled into the page by src/site/build_site.py) and in Node
// (src/run/run_scenarios.js). Requires the javascript-lp-solver global `solver` and the
// config object `globalThis.MODEL_CONFIG` (= config/model_config.json).
// =====================================================================================

const TECHS = [
  { k: "pv", name: "Solar PV", c: "--t-pv" },
  { k: "on", name: "Onshore wind", c: "--t-on" },
  { k: "off", name: "Offshore wind", c: "--t-off" },
  { k: "smr", name: "SMR", c: "--t-smr" },
  { k: "ccs", name: "Gas + CCS", c: "--t-ccs" },
  { k: "gas", name: "Gas backup", c: "--t-gas" },
  { k: "imp", name: "Grid import", c: "--t-imp" },
];

const MIX_DEFAULTS = { ...globalThis.MODEL_CONFIG.model.mix };
const SLICE_RULES = globalThis.MODEL_CONFIG.model.slices;

function crfOf(w, n) { return w / (1 - Math.pow(1 + w, -n)); }
const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));

// Eight equal slices built from annual averages (r.pv, r.won, r.coff are capacity factors)
function slices(r) {
  const Q = SLICE_RULES;
  const a = clamp(Q.solar_amp_base + Q.solar_amp_per_deg * (r.lat - Q.ref_lat), Q.solar_amp_min, Q.solar_amp_max); // solar seasonality
  const b = clamp(Q.wind_amp_base + Q.wind_amp_per_deg * (r.lat - Q.ref_lat), Q.wind_amp_min, Q.wind_amp_max);     // wind: winter stronger
  const cOn = Q.onshore_calm_contrast, cOff = Q.offshore_calm_contrast, mx = Q.max_cf;
  const out = [];
  for (const se of ["W", "S"]) for (const wd of ["windy", "calm"]) for (const td of ["day", "night"]) {
    const ss = se === "S" ? 1 : -1, ws = se === "W" ? 1 : -1, wf = wd === "windy" ? 1 : -1;
    out.push({ se, wd, td, k: se + wd,
      pv: td === "day" ? Math.min(mx, 2 * r.pv * (1 + ss * a)) : 0,
      on: Math.min(mx, r.won * (1 + ws * b) * (1 + wf * cOn)),
      off: r.coff ? Math.min(mx, r.coff * (1 + ws * b) * (1 + wf * cOff)) : 0 });
  }
  return out;
}

// Annualised costs in €/MW-yr divided by 8760 -> €/MWh of 1 MW flat load; variable costs in €/MWh
function unitCosts(r, P) {
  const A = (capex, w, n, om) => (capex * 1000 * (crfOf(w, n) + om)) / 8760;
  const ccsCO2 = P.gasEf / P.ccsEff, gasCO2 = P.gasEf / P.gasEff;   // t CO2 per MWh electricity
  return {
    pv: A(P.pvCapex, P.wacc, P.pvLife, P.pvOm), on: A(P.wCapex, P.wacc, P.wLife, P.wOm),
    off: r.kxoff ? A(r.kxoff, P.wacc, P.offLife, P.offOm) : 0,
    bat: A(P.batKwh * P.batHours, P.wacc, P.batLife, P.batOm),
    el: A(P.elCapex, P.wacc, P.elLife, P.elOm),
    smr: (P.smrCapex * 1000 * crfOf(P.smrWacc, P.smrLife) + P.smrFom * 1000) / 8760, smrV: P.smrVar,
    ccs: (P.ccsCapex * 1000 * crfOf(P.wacc, P.ccsLife) + P.ccsFom * 1000) / 8760,
    ccsV: P.gasPrice / P.ccsEff + ccsCO2 * P.ccsCapture * P.ccsTs + ccsCO2 * (1 - P.ccsCapture) * P.co2 + P.ccsVom,
    gas: (P.gasCapex * 1000 * crfOf(P.wacc, P.gasLife) + P.gasFom * 1000) / 8760,
    gasV: P.gasPrice / P.gasEff + gasCO2 * P.co2 + P.gasVom,
  };
}

// Build the LP in javascript-lp-solver format. h = flexible (electrolyser) share of the load.
// opts.noVRE forces the no-new-renewables fallback used when a region's land is exhausted.
function buildLP(r, h, P, opts = {}) {
  const S = slices(r), U = unitCosts(r, P), w = 1 / 8;            // each slice = 1/8 of the year
  const cav = !!r.cav, nukeOK = P.smrOn && !(P.smrBans && r.nban);
  const V = {}, C = {};
  const v = (name, cost) => (V[name] = V[name] || { cost }, V[name]);
  const vre = !opts.noVRE;
  S.forEach((s, i) => { C["bal" + i] = { min: 1 - h }; });          // steady load in every slice
  if (vre) {
    const pv = v("PV", U.pv), on = v("ON", U.on);
    S.forEach((s, i) => { pv["bal" + i] = s.pv; on["bal" + i] = s.on; });
    if (P.offshore && r.coff > 0 && r.kxoff) { const off = v("OFF", U.off); S.forEach((s, i) => { off["bal" + i] = s.off; }); }
    if (P.batOn) {                                                  // day -> following night shifting
      const B = v("BAT", U.bat);
      ["Wwindy", "Wcalm", "Swindy", "Scalm"].forEach((k) => {
        const di = S.findIndex((s) => s.k === k && s.td === "day"), ni = S.findIndex((s) => s.k === k && s.td === "night");
        C["be" + k] = { max: 0 };                                  // discharge <= (hours/12) * BAT
        C["bq" + k] = { equal: 0 };                                // discharge = eta * charge
        const bc = v("bc" + k, 0), bd = v("bd" + k, 0);
        bc["bal" + di] = -1; bd["bal" + ni] = 1;
        bd["be" + k] = 1; B["be" + k] = -P.batHours / 12;
        bd["bq" + k] = 1; bc["bq" + k] = -P.batEta;
      });
    }
  }
  if (nukeOK) { const N = v("SMR", U.smr); S.forEach((s, i) => { C["sm" + i] = { max: 0 }; const n = v("n" + i, U.smrV * w); n["bal" + i] = 1; n["sm" + i] = 1; N["sm" + i] = -P.smrAvail; }); }
  if (P.ccsOn) { const G = v("CCS", U.ccs); S.forEach((s, i) => { C["cc" + i] = { max: 0 }; const g = v("g" + i, U.ccsV * w); g["bal" + i] = 1; g["cc" + i] = 1; G["cc" + i] = -P.ccsAvail; }); }
  if (P.gasOn) {
    const O = v("GAS", U.gas); C.fossil = { max: 8 * P.fossilCap };  // unabated gas <= fossilCap of annual energy
    S.forEach((s, i) => { C["gc" + i] = { max: 0 }; const u = v("u" + i, U.gasV * w); u["bal" + i] = 1; u["gc" + i] = 1; O["gc" + i] = -1; u.fossil = 1; });
  }
  if (P.impOn) S.forEach((s, i) => { const m = v("m" + i, P.impPrice * w); m["bal" + i] = 1; });
  if (h > 0) {                                                      // electrolyser share with H2 storage
    const flex = P.h2On && vre;
    const X = flex ? v("ELX", U.el) : null;                        // only capacity ABOVE flat running is costed
    const cs = cav ? P.cavShort : P.tankShort, cse = cav ? P.cavSeas : P.tankSeas;  // €/MWh H2 shifted
    S.forEach((s, i) => {
      const e = v("e" + i, 0); e["bal" + i] = -1;
      C["fl" + i] = { equal: h }; e["fl" + i] = 1;                  // downstream H2 use is flat
      if (flex) {
        C["ex" + i] = { max: h }; e["ex" + i] = 1; X["ex" + i] = -1;
        const ch = v("ch" + i, 0), ds = v("ds" + i, cs * w * P.h2PerMwhEl);
        ch["fl" + i] = -1; ds["fl" + i] = 1;
        C["sb" + s.se] = { equal: 0 };
        ch["sb" + s.se] = P.h2StoreEff; ds["sb" + s.se] = -1;
      }
    });
    if (flex) {                                                    // seasonal transfers between summer and winter
      const qSW = v("qSW", cse * w * P.h2PerMwhEl), qWS = v("qWS", cse * w * P.h2PerMwhEl);
      qSW.sbW = P.h2StoreEff; qSW.sbS = -1; qWS.sbS = P.h2StoreEff; qWS.sbW = -1;
    }
  }
  return { optimize: "cost", opType: "min", constraints: C, variables: V, _S: S, _h: h };
}

function solveMix(r, h, P, opts = {}) {
  const m = buildLP(r, h, P, opts);
  const res = solver.Solve(m);
  if (!res.feasible) return { cost: Infinity, feasible: false };
  const g = (k) => res[k] || 0, S = m._S;
  const cap = { pv: g("PV"), on: g("ON"), off: g("OFF"), bat: g("BAT"), elx: g("ELX"), smr: g("SMR"), ccs: g("CCS"), gas: g("GAS") };
  // E: delivered energy by generating source (VRE net of curtailment), shares summing to 1
  // St: storage throughput per MWh of demand (battery discharge, hydrogen withdrawn from storage)
  const E = { pv: 0, on: 0, off: 0, smr: 0, ccs: 0, gas: 0, imp: 0 }, St = { bat: 0, h2: 0 };
  S.forEach((s, i) => {
    const avail = { pv: cap.pv * s.pv, on: cap.on * s.on, off: cap.off * s.off };
    const firm = g("n" + i) + g("g" + i) + g("u" + i) + g("m" + i);
    const bd = s.td === "night" ? g("bd" + s.k) : 0, bc = s.td === "day" ? g("bc" + s.k) : 0;
    const need = (1 - h) + (h > 0 ? g("e" + i) : 0) + bc;
    const vreTot = avail.pv + avail.on + avail.off;
    const vreUsed = Math.max(0, Math.min(vreTot, need - firm - bd));
    const f = vreTot > 0 ? vreUsed / vreTot : 0;
    E.pv += avail.pv * f / 8; E.on += avail.on * f / 8; E.off += avail.off * f / 8;
    E.smr += g("n" + i) / 8; E.ccs += g("g" + i) / 8; E.gas += g("u" + i) / 8; E.imp += g("m" + i) / 8;
    St.bat += bd / 8; if (h > 0) St.h2 += g("ds" + i) / 8;
  });
  const tot = Object.values(E).reduce((a, b) => a + b, 0) || 1;
  for (const k in E) E[k] /= tot;
  const vreGen = (cap.pv * r.pv + cap.on * r.won + cap.off * (r.coff || 0)) * 8760; // MWh/yr available per MW load
  return { cost: res.result, feasible: true, cap, E, St, vreGen };
}

if (typeof module !== "undefined") module.exports = { TECHS, MIX_DEFAULTS, slices, unitCosts, buildLP, solveMix, crfOf };
