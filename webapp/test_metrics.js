"use strict";
// Run with: node webapp/test_metrics.js
const assert = require("node:assert/strict");
const M = require("./metrics.js");
function close(a, b, tol = 1e-11) {
  assert.ok(Math.abs(a - b) <= tol * Math.max(1, Math.abs(b)), `${a} != ${b}`);
}
const head = [0.5, 0.2, 0.15], tail = 0.15;
let interval = M.jointShiftSp(head, tail, 2, 0.3);
close(interval.lower, 0.1025); close(interval.upper, 0.68);
interval = M.jointMergeSp(head, tail, 2, 0.3);
close(interval.lower, 0.3125); close(interval.upper, 0.68);
assert.equal(interval.status, "safe");
for (const rho of [0.05, tail]) {
  assert.equal(M.jointMergeSp(head, tail, 2, rho).status, "interval");
  assert.equal(M.jointMergeCRk(head, tail, 2, rho).status, "interval");
  assert.equal(M.jointMergeNCtau(head, tail, .5, rho).status, "interval");
}
close(M.mergeCost([1 / 6, 1 / 6, 1 / 6, 1 / 6, 1 / 6, 1 / 6], [[0, 1], [2, 3], [4, 5]]), 0.5);
close(M.mergeCost([0.7, 0.2, 0.1], [[0, 1], [2]]), 0.2);
// A small whole holding may merge into a much larger existing holding.
assert.ok(M.merge_Sp([0.7, 0.2, 0.1], 2, 0.2).upper >= 0.82 - 1e-12);
assert.throws(() => M.mergeCost([0.5, 0.5], [[0, 0], [1]]), /partition/);
close(M.jointShiftSp(head, tail, 1, 0.3).lower, 1);
assert.equal(M.jointShiftNCtau([0.7, 0.3], 0, 0.8, 0.3).upper, Infinity);
close(M.jointShiftSp([1], 0, 2, 1).lower, 0);
close(M.jointShiftSp([1], 0, 2, 1).upper, 1);
assert.equal(M.cappingNCtau(Array(6).fill(1/6), 0, 1).upper, 6);
assert.equal(M.cappingNCtau(Array(10000).fill(.0001), 0, 1).upper, 10000);
assert.equal(M.jointShiftNCtau([.5,.2,.15], .15, .55 + 5e-13, .3).upper, Infinity);
assert.equal(M.jointShiftNCtau([.5,.2,.15], .15, .55, .3).upper, 3);
close(M.cappingGini(head, tail, 2).lower, 0.39);
close(M.cappingGini(head, tail, 2).upper, 0.42);
assert.equal(M.cappingGini(head, tail, 0).status, "infeasible");
assert.equal(M.cappingGini([0.5, 0.5], 0, 1).status, "infeasible");
assert.equal(M.cappingEntropy(head, tail).upper, Infinity);
close(M.cappingEntropy([0.5, 0.5], 0).lower, Math.log(2));
function* partitions(n, groups = [], i = 0) {
  if (i === n) { yield groups.map(g => g.slice()); return; }
  for (let j = 0; j < groups.length; j++) {
    groups[j].push(i); yield* partitions(n, groups, i + 1); groups[j].pop();
  }
  groups.push([i]); yield* partitions(n, groups, i + 1); groups.pop();
}
let checked = 0;
for (const shares of [[0.7, 0.2, 0.1], [0.4, 0.25, 0.2, 0.1, 0.05], Array(6).fill(1 / 6)]) {
  for (const grouping of partitions(shares.length)) {
    const cost = M.mergeCost(shares, grouping);
    const grouped = grouping.map(g => g.reduce((s, i) => s + shares[i], 0)).sort((a, b) => b - a);
    for (const p of [1.1, 2, 3.5]) {
      const band = M.merge_Sp(shares, p, cost);
      const value = M.Sp(grouped, p);
      assert.ok(value >= band.lower - 1e-12 && value <= band.upper + 1e-12);
    }
    for (const k of [1, 2, 4]) {
      const band = M.merge_CRk(shares, k, cost);
      const value = M.CRk(grouped, k);
      assert.ok(value >= band.lower - 1e-12 && value <= band.upper + 1e-12);
    }
    checked++;
  }
}
for (const order of [Infinity, NaN, 10000]) {
  assert.throws(() => M.jointShiftSp(head, tail, order, .3), /finite order/);
  assert.throws(() => M.HillQ(head, order), /finite order/);
}
console.log(`Metric checks passed; ${checked} partitions checked against moved-mass bounds.`);
