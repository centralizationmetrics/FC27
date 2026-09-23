"use strict";
// Exercises UI rendering and normalization without a browser or external library.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const noop = () => {};
const draw = new Proxy({}, { get: (_, key) => key === "measureText" ? s => ({ width: String(s).length * 6 }) : noop, set: () => true });
const nodes = new Map();
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {
    value: "", textContent: "", innerHTML: "", className: "", placeholder: "",
    querySelector: () => node(id + "/body"), getBoundingClientRect: () => ({ width: 360, height: 220 }),
    getContext: () => draw, addEventListener: noop,
  });
  return nodes.get(id);
}
const context = vm.createContext({ console: { ...console, error: noop }, performance, setTimeout, clearTimeout,
  Float64Array, window: { Metrics: require("./metrics.js"), addEventListener: noop, devicePixelRatio: 1 },
  document: { getElementById: node, activeElement: null },
});
vm.runInContext(fs.readFileSync(__dirname + "/app.js", "utf8"), context);
for (const [key, value] of Object.entries({ N: 3, T_N: "", M_total: 5, k: 2, tau: .5, p: 2, q: 2, rho: .3, alpha: .3 })) node(key).value = String(value);
vm.runInContext("state.dataset = {full_shares:Float64Array.from([.5,.2,.15])}; recompute()", context);
assert.ok(node("status").textContent.startsWith("updated"), node("status").textContent);
assert.ok(node("tile-HHI/body").innerHTML.includes("0.680000"));
assert.ok(node("tile-HHI/body").innerHTML.includes(">conservative</span>"));
assert.ok(node("tile-HHI/body").innerHTML.includes("0.312500"));
node("T_N").value = ".1";
vm.runInContext("recompute()", context);
assert.ok(node("status").textContent.startsWith("updated"), node("status").textContent);
assert.ok(Math.abs(vm.runInContext("M.sumArray(state.shares)+state.T_N", context) - 1) < 1e-12);
node("T_N").value = ""; node("M_total").value = "3";
vm.runInContext("recompute()", context);
assert.ok(node("tile-Gini/body").innerHTML.includes("incompatible"));
node("N").value = "9999";
vm.runInContext("recompute()", context);
assert.equal(Number(node("N").value), 3);
node("p").value = "10000";
vm.runInContext("recompute()", context);
assert.ok(node("status").textContent.includes("finite order"));
console.log("UI checks passed: joint bounds, conservative labels, omitted-mass normalization, count feasibility, cap clipping.");
