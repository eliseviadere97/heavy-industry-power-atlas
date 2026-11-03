// =====================================================================================
// Step B of the pipeline: run the model headless with the defaults in config/model_config.json
// and write result tables to outputs/results/. Same code as the web page (src/model/*.js).
//
// Usage:  node src/run/run_scenarios.js
// =====================================================================================
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..", "..");
globalThis.MODEL_CONFIG = JSON.parse(fs.readFileSync(path.join(ROOT, "config", "model_config.json"), "utf8"));
globalThis.solver = require("javascript-lp-solver");
const M = require(path.join(ROOT, "src", "model", "mix.js"));
const PL = require(path.join(ROOT, "src", "model", "plan.js"));

const DATA = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "processed", "data.json"), "utf8"));
const R = DATA.regions;
const RI = Object.fromEntries(R.map((r, j) => [r.id, j]));
const PLANTS = DATA.plants.map((p) => ({ i: p.i, n: p.n, home: RI[p.r], o: p.o, x: p.x, y: p.y }));
const OUT = path.join(ROOT, "outputs", "results");
const VAL = path.join(ROOT, "outputs", "validation");
fs.mkdirSync(OUT, { recursive: true });
fs.mkdirSync(VAL, { recursive: true });

const GEN = M.TECHS.map((t) => t.k);
const SCN = ["stay", "second", "first"];
const baseP = () => ({ ...M.MIX_DEFAULTS, ...PL.PLAN_DEFAULTS });
const baseCfg = () => Object.fromEntries(PL.SECTORS.map((s) => [s.k, { on: true, int: s.mwh_per_t, h: s.flex_share }]));

function computeMixes(P, cfg) {
  const mixes = { A: {}, B: {} };
  for (const h of [...new Set(Object.values(cfg).map((c) => c.h))]) {
    mixes.A[h] = R.map((r) => M.solveMix(r, h, P));
    const cache = {};
    mixes.B[h] = R.map((r) => { const key = P.smrOn && !(P.smrBans && r.nban) ? "n" : "x"; return cache[key] || (cache[key] = M.solveMix(r, h, P, { noVRE: true })); });
  }
  return mixes;
}

const csvEsc = (v) => (v === null || v === undefined ? "" : typeof v === "number" ? (Number.isInteger(v) ? String(v) : v.toFixed(4)) : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v));
function writeCSV(file, rows) {
  if (!rows.length) return;
  const cols = Object.keys(rows[0]);
  fs.writeFileSync(file, [cols.join(","), ...rows.map((r) => cols.map((c) => csvEsc(r[c])).join(","))].join("\n") + "\n");
  console.log(`  wrote ${path.relative(ROOT, file)} (${rows.length} rows)`);
}
const summaryRow = (label, sc, a) => {
  const row = { case: label, scenario: sc, avg_eur_per_mwh: a.avg, cost_bn_eur_per_yr: a.bn, demand_twh: a.E, plants: a.nPlants, plants_moved: a.moved,
    share_load_moved: a.E ? a.movedE / a.E : 0, regions_used: a.used, uncovered_twh: a.uncovered };
  GEN.forEach((k) => (row["share_" + k] = (a.mix[k] || 0) / (a.E || 1)));
  row.battery_throughput_share = (a.st.bat || 0) / (a.E || 1);
  row.h2_storage_throughput_share = (a.st.h2 || 0) / (a.E || 1);
  return row;
};

const t0 = Date.now();
const P = baseP(), cfg = baseCfg();
const mixes = computeMixes(P, cfg);
const tMix = (Date.now() - t0) / 1000;
const res = {};
for (const sc of SCN) res[sc] = PL.plan(R, PLANTS, cfg, mixes, P, sc);
console.log(`Default run: local mixes ${tMix.toFixed(1)} s, plans ${((Date.now() - t0) / 1000 - tMix).toFixed(1)} s`);
for (const sc of SCN) console.log(`  ${sc.padEnd(7)} €${res[sc].avg.toFixed(1)}/MWh  €${res[sc].bn.toFixed(1)}bn/yr  ${res[sc].E.toFixed(0)} TWh  moved ${res[sc].moved}/${res[sc].nPlants}  regions ${res[sc].used}`);

// 1) scenario summary
writeCSV(path.join(OUT, "scenario_summary.csv"), SCN.map((sc) => summaryRow("default", sc, res[sc])));

// 2) plant allocation, all scenarios
const homeUnit = Object.fromEntries(res.stay.plants.map((p) => [p.q, p.unit]));
const rows = [];
for (const sc of SCN) for (const p of res[sc].plants) {
  const row = { scenario: sc, plant: p.n, industry: p.i, output_kt: p.o, demand_twh: p.E, home_nuts2: R[p.home].id, home_region: R[p.home].na,
    site_nuts2: R[p.loc].id, site_region: R[p.loc].na, moved: p.loc !== p.home ? 1 : 0, eur_per_mwh: p.unit, eur_per_mwh_if_stay: homeUnit[p.q],
    share_of_load_on_local_renewables_mix: p.f, uncovered_twh: p.unc };
  GEN.forEach((k) => (row["share_" + k] = p.mix[k] || 0));
  row.battery_throughput = p.st.bat || 0; row.h2_storage_throughput = p.st.h2 || 0;
  rows.push(row);
}
writeCSV(path.join(OUT, "plant_allocation.csv"), rows);

// 3) best local mix for each region x sector (per MW of average load)
const mixRows = [];
for (const s of PL.SECTORS) {
  const h = cfg[s.k].h;
  R.forEach((r, j) => {
    const m = mixes.A[h][j], b = mixes.B[h][j];
    const row = { nuts2: r.id, region: r.na, sector: s.k, flex_share: h, feasible: m.feasible ? 1 : 0, eur_per_mwh: m.cost,
      eur_per_mwh_without_new_renewables: b.feasible ? b.cost : null };
    GEN.forEach((k) => (row["share_" + k] = m.feasible ? m.E[k] : null));
    ["pv", "on", "bat", "elx", "smr", "ccs"].forEach((k) => (row["mw_per_mw_load_" + k] = m.feasible ? m.cap[k] : null));
    row.h2_storage_days_of_load = m.feasible ? m.cap.vol : null;
    row.km2_per_mw_load = m.feasible ? m.cap.pv / P.pvDens + m.cap.on / P.wDens : null;
    row.battery_throughput = m.feasible ? m.St.bat : null; row.h2_storage_throughput = m.feasible ? m.St.h2 : null;
    mixRows.push(row);
  });
}
writeCSV(path.join(OUT, "local_mix_by_region.csv"), mixRows);

// 4) region totals per scenario
writeCSV(path.join(OUT, "region_load.csv"), R.map((r, j) => {
  const row = { nuts2: r.id, region: r.na, country: r.cc };
  for (const sc of SCN) row[`load_twh_${sc}`] = res[sc].tot[j];
  for (const sc of SCN) row[`land_used_km2_${sc}`] = res[sc].landUsed[j];
  row.land_for_solar_and_wind_km2 = res.first.land[j];
  return row;
}));

// 5) sensitivities: second-best constraints one at a time; technologies and prices (all scenarios)
const sens = [];
const consCases = [
  ["no constraints (= first best)", { cGrid: false, cEco: false }],
  ["grid: >=330 kV substation only", { cEco: false }],
  ["clusters only", { cGrid: false }],
  ["clusters: destinations only, nothing pinned", { cGrid: false, alpha: 0 }],
  ["both (default)", {}],
];
for (const [label, o] of consCases) sens.push(summaryRow("constraints: " + label, "second", PL.plan(R, PLANTS, cfg, mixes, { ...P, ...o }, "second")));
const techCases = [
  ["no SMRs", { smrOn: false }], ["SMRs everywhere (ignore national bans)", { smrBans: false }], ["no gas with carbon capture", { ccsOn: false }],
  ["no batteries", { batOn: false }], ["no hydrogen storage", { h2On: false }],
  ["gas at €88/MWh (Oct 2026 spot)", { gasPrice: 88 }], ["CO2 at €200/t", { co2: 200 }],
  ["cost of capital 4%", { wacc: 0.04 }], ["cost of capital 8%", { wacc: 0.08 }],
];
for (const [label, o] of techCases) {
  const Pt = { ...P, ...o }, mx = computeMixes(Pt, cfg);
  for (const sc of SCN) sens.push(summaryRow("technology: " + label, sc, PL.plan(R, PLANTS, cfg, mx, Pt, sc)));
}
writeCSV(path.join(OUT, "sensitivities.csv"), sens);

// 6) a sample of local-mix LPs for the independent solver check (src/validation/validate_lp.py)
const pick = ["ES41", "ES61", "DEA1", "NL34", "SE33", "FRE1", "ITF4", "PL22", "UKC1", "NO0A", "CH04", "CZ08"].filter((id) => id in RI);
const dump = [];
for (const h of [...new Set(Object.values(cfg).map((c) => c.h))]) for (const id of pick) {
  const r = R[RI[id]];
  for (const noVRE of [false, true]) {
    const m = M.buildLP(r, h, P, { noVRE });
    dump.push({ id, h, noVRE, model: { constraints: m.constraints, variables: m.variables }, obj: M.solveMix(r, h, P, { noVRE }).cost });
  }
}
fs.writeFileSync(path.join(VAL, "lp_sample.json"), JSON.stringify(dump));
console.log(`  wrote outputs/validation/lp_sample.json (${dump.length} LPs)`);

// 7) the default planning problems, for the exact check (src/validation/validate_plan.py)
const loads = PL.plantLoads(PLANTS, cfg);
const classes = [...new Set(loads.map((p) => p.h))];
const unit = Object.fromEntries(classes.map((h) => [h, R.map((r, j) => {
  const a = mixes.A[h][j], b = mixes.B[h][j];
  return [a.feasible ? a.cost : null, b.feasible ? b.cost : null, a.feasible ? a.cap.pv / P.pvDens + a.cap.on / P.wDens : 0];
})]));
fs.writeFileSync(path.join(VAL, "plan_problem.json"), JSON.stringify({
  P: { cGrid: P.cGrid, cEco: P.cEco, alpha: P.alpha, infeasible: P.infeasible, relocPrem: P.relocPrem },
  regions: R.map((r) => ({ id: r.id, n330: r.n330, cap: r.cap })), land: PL.regionLand(R, P),
  plants: loads.map((p) => ({ n: p.n, i: p.i, home: p.home, o: p.o, E: p.E, L: p.L, h: p.h })), unit,
  heuristic: Object.fromEntries(SCN.map((sc) => [sc, { cost: res[sc].cost, moved: res[sc].moved }])),
}));
console.log("  wrote outputs/validation/plan_problem.json");
fs.writeFileSync(path.join(OUT, "run_info.json"), JSON.stringify({ generated: new Date().toISOString(), seconds: (Date.now() - t0) / 1000,
  defaults: { mix: M.MIX_DEFAULTS, plan: PL.PLAN_DEFAULTS, sectors: PL.SECTORS } }, null, 1));
console.log(`Model runs done in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
