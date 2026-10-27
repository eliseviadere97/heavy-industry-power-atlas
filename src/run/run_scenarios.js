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
const PLANTS = DATA.plants.filter((p) => p.i !== "chlor").map((p) => ({ i: p.i, n: p.n, home: RI[p.r], c: p.c, x: p.x, y: p.y }));
const OUT = path.join(ROOT, "outputs", "results");
const VAL = path.join(ROOT, "outputs", "validation");
fs.mkdirSync(OUT, { recursive: true });
fs.mkdirSync(VAL, { recursive: true });

const GEN = ["pv", "on", "off", "smr", "ccs", "gas", "imp"];
const baseP = () => ({ ...M.MIX_DEFAULTS, ...PL.PLAN_DEFAULTS });
const baseCfg = () => Object.fromEntries(PL.IND.map((i) => [i.k, { on: true, out: i.out, route: 0, int: i.routes[0][1], h: i.routes[0][2] }]));

function computeMixes(P, cfg) {
  const hs = [...new Set(Object.values(cfg).map((c) => c.h))];
  const mixes = { A: {}, B: {} };
  for (const h of hs) {
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
    share_load_moved: a.E ? a.movedE / a.E : 0, regions_used: a.used, unserved_twh: a.unserved };
  GEN.forEach((k) => (row["share_" + k] = (a.mix[k] || 0) / (a.E || 1)));
  row.battery_throughput_share = (a.st.bat || 0) / (a.E || 1);
  row.h2_storage_throughput_share = (a.st.h2 || 0) / (a.E || 1);
  return row;
};

const t0 = Date.now();
const P = baseP(), cfg = baseCfg();
const mixes = computeMixes(P, cfg);
const res = {};
for (const sc of ["stay", "second", "first"]) res[sc] = PL.plan(R, PLANTS, cfg, mixes, P, sc);
console.log(`Default run: ${((Date.now() - t0) / 1000).toFixed(1)} s`);
for (const sc of ["stay", "second", "first"]) console.log(`  ${sc.padEnd(7)} €${res[sc].avg.toFixed(1)}/MWh  €${res[sc].bn.toFixed(1)}bn/yr  moved ${res[sc].moved}/${res[sc].nPlants}  regions ${res[sc].used}`);

// 1) scenario summary
writeCSV(path.join(OUT, "scenario_summary.csv"), ["stay", "second", "first"].map((sc) => summaryRow("default", sc, res[sc])));

// 2) plant allocation, all scenarios
const homeUnit = Object.fromEntries(res.stay.plants.map((p) => [p.q, p.unit]));
const rows = [];
for (const sc of ["stay", "second", "first"]) for (const p of res[sc].plants) {
  const row = { scenario: sc, plant: p.n, industry: p.i, capacity_kt: p.c, demand_twh: p.E, home_nuts2: R[p.home].id, home_region: R[p.home].na,
    site_nuts2: R[p.loc].id, site_region: R[p.loc].na, moved: p.loc !== p.home ? 1 : 0, eur_per_mwh: p.unit, eur_per_mwh_if_stay: homeUnit[p.q],
    share_of_load_on_local_renewables_mix: p.f, unserved_twh: p.uns };
  GEN.forEach((k) => (row["share_" + k] = p.mix[k] || 0));
  row.battery_throughput = p.st.bat || 0; row.h2_storage_throughput = p.st.h2 || 0;
  rows.push(row);
}
writeCSV(path.join(OUT, "plant_allocation.csv"), rows);

// 3) best local mix for each region x industry (per MW of average load)
const mixRows = [];
for (const ind of PL.IND) {
  const h = cfg[ind.k].h;
  R.forEach((r, j) => {
    const m = mixes.A[h][j], b = mixes.B[h][j];
    const row = { nuts2: r.id, region: r.na, industry: ind.k, flex_share: h, feasible: m.feasible ? 1 : 0, eur_per_mwh: m.cost,
      eur_per_mwh_without_new_renewables: b.feasible ? b.cost : null };
    GEN.forEach((k) => (row["share_" + k] = m.feasible ? m.E[k] : null));
    ["pv", "on", "off", "bat", "elx", "smr", "ccs", "gas"].forEach((k) => (row["mw_per_mw_load_" + k] = m.feasible ? m.cap[k] : null));
    row.battery_throughput = m.feasible ? m.St.bat : null; row.h2_storage_throughput = m.feasible ? m.St.h2 : null;
    mixRows.push(row);
  });
}
writeCSV(path.join(OUT, "local_mix_by_region.csv"), mixRows);

// 4) region totals per scenario
const regRows = [];
R.forEach((r, j) => {
  const row = { nuts2: r.id, region: r.na, country: r.cc };
  for (const sc of ["stay", "second", "first"]) row[`load_twh_${sc}`] = res[sc].tot[j];
  row.renewable_potential_left_twh = res.first.res0[j].potTWh;
  regRows.push(row);
});
writeCSV(path.join(OUT, "region_load.csv"), regRows);

// 5) sensitivities: constraints one at a time (second best), technologies (all scenarios)
const sens = [];
const consCases = [
  ["no constraints (= first best)", { cGrid: false, cRE: false, cEco: false }],
  ["grid only", { cRE: false, cEco: false }],
  ["existing renewables only", { cGrid: false, cEco: false }],
  ["ecosystem only", { cGrid: false, cRE: false }],
  ["ecosystem: destinations only, nothing pinned", { cGrid: false, cRE: false, alpha: 0 }],
  ["all three (default)", {}],
];
for (const [label, o] of consCases) sens.push(summaryRow("constraints: " + label, "second", PL.plan(R, PLANTS, cfg, mixes, { ...P, ...o }, "second")));
const techCases = [
  ["no SMRs", { smrOn: false }], ["SMRs everywhere (ignore national bans)", { smrBans: false }], ["no gas with carbon capture", { ccsOn: false }],
  ["no batteries", { batOn: false }], ["no hydrogen storage", { h2On: false }], ["no unabated gas backup", { gasOn: false }],
  ["gas at €88/MWh (Oct 2026 spot)", { gasPrice: 88 }], ["CO2 at €200/t", { co2: 200 }], ["relocation premium €5/MWh", { relocPrem: 5 }],
];
for (const [label, o] of techCases) {
  const Pt = { ...P, ...o }, mx = computeMixes(Pt, cfg);
  for (const sc of ["stay", "second", "first"]) sens.push(summaryRow("technology: " + label, sc, PL.plan(R, PLANTS, cfg, mx, Pt, sc)));
}
writeCSV(path.join(OUT, "sensitivities.csv"), sens);

// 6) a sample of LPs for the independent solver check (src/validation/validate_lp.py)
const pick = ["ES41", "ES61", "DEA1", "NL34", "SE33", "FRE1", "ITF4", "PL22", "DEF0", "FI1D", "BE23", "CZ08"];
const dump = [];
for (const h of [0, 0.75, 0.9]) for (const id of pick) {
  const r = R[RI[id]];
  for (const noVRE of [false, true]) {
    const m = M.buildLP(r, h, P, { noVRE });
    const s = M.solveMix(r, h, P, { noVRE });
    dump.push({ id, h, noVRE, model: { constraints: m.constraints, variables: m.variables }, obj: s.cost });
  }
}
fs.writeFileSync(path.join(VAL, "lp_sample.json"), JSON.stringify(dump));
console.log(`  wrote outputs/validation/lp_sample.json (${dump.length} LPs)`);
fs.writeFileSync(path.join(OUT, "run_info.json"), JSON.stringify({ generated: new Date().toISOString(), seconds: (Date.now() - t0) / 1000,
  defaults: { mix: M.MIX_DEFAULTS, plan: PL.PLAN_DEFAULTS } }, null, 1));
console.log(`Model runs done in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
