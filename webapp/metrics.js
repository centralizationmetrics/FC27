// metrics.js — reference JS implementation of the capping + attribution
// certificates from "How informative are distribution-based decentralization
// metrics? Certificates under capping and attribution uncertainty"
// (Bitcoin running example bundled as default; user can upload any share
// vector).
//
// All inputs assume `shares` is a nonnegative array sorted in *decreasing*
// order with sum <= 1 (any tail mass is described by `T_N` separately).
// Nothing in this file touches the DOM; it can be unit-tested in isolation.

"use strict";

/* ------------------------------------------------------------------ basic */

function sumArray(a) {
  let s = 0, correction = 0;
  for (let i = 0; i < a.length; i++) {
    const term = a[i] - correction;
    const next = s + term;
    correction = (next - s) - term;
    s = next;
  }
  return s;
}

function prefixSums(a) {
  const ps = new Float64Array(a.length);
  let s = 0, correction = 0;
  for (let i = 0; i < a.length; i++) {
    const term = a[i] - correction;
    const next = s + term;
    correction = (next - s) - term;
    s = next;
    ps[i] = s;
  }
  return ps;
}

function prefixSumsPow(a, p) {
  const ps = new Float64Array(a.length);
  let s = 0;
  for (let i = 0; i < a.length; i++) {
    s += Math.pow(a[i], p);
    ps[i] = s;
  }
  return ps;
}

/* ----------------------------------------------------- raw account metrics */

// CR_k on the (already sorted) head x of length N: sum of top k entries.
function CRk(shares, k) {
  if (k <= 0) return 0;
  const N = shares.length;
  const m = Math.min(k, N);
  let s = 0;
  for (let i = 0; i < m; i++) s += shares[i];
  return s;
}

// Smallest k such that prefix sum >= tau. Returns null if head sum < tau.
// Comparisons allow only a few floating-point rounding units. A user-supplied
// threshold separated by more than this is never rounded down to a prefix.
function reaches(mass, threshold) {
  return mass >= threshold || threshold - mass <=
    4 * Number.EPSILON * Math.max(Math.abs(mass), Math.abs(threshold));
}
function ceilCount(value) {
  const nearest = Math.round(value);
  return Math.abs(value - nearest) <= 4 * Number.EPSILON * Math.abs(value)
    ? nearest : Math.ceil(value);
}
function NCtau(shares, tau) {
  let s = 0, correction = 0;
  for (let i = 0; i < shares.length; i++) {
    const term = shares[i] - correction;
    const next = s + term;
    correction = (next - s) - term;
    s = next;
    if (reaches(s, tau)) return i + 1;
  }
  return null;
}

// HHI = sum of squares.
function HHI(shares) {
  let s = 0;
  for (let i = 0; i < shares.length; i++) s += shares[i] * shares[i];
  return s;
}

// The calculator supports finite orders through 6; reject unsupported inputs
// rather than silently underflowing extreme powers to a zero certificate.
function validateOrder(order, minimum = 0) {
  if (!Number.isFinite(order) || order < minimum || order > 6)
    throw new Error(`Use a finite order between ${minimum} and 6`);
}
// S_p; orders below one are used only for descriptive Hill values.
function Sp(shares, p) {
  validateOrder(p);
  if (p === 1) return sumArray(shares);
  if (p === 2) return HHI(shares);
  let s = 0;
  for (let i = 0; i < shares.length; i++) s += Math.pow(shares[i], p);
  return s;
}

// Hill number Hill_q = S_q^{1/(1-q)} for q != 1; for q=1 returns exp(H).
function HillQ(shares, q) {
  validateOrder(q);
  if (Math.abs(q - 1) < 1e-9) {
    let h = 0;
    for (let i = 0; i < shares.length; i++) {
      const xi = shares[i];
      if (xi > 0) h -= xi * Math.log(xi);
    }
    return Math.exp(h);
  }
  const s = Sp(shares, q);
  if (s <= 0) return 0;
  return Math.pow(s, 1 / (1 - q));
}

// Gini coefficient on the *observed* head only (descriptive; not count-aware).
// Uses the standard sorted-vector formula. For sorted-descending shares the
// 1-based rank i has coefficient (n + 1 - 2 i): largest element gets the
// largest positive weight, smallest the largest negative weight, and a
// perfectly uniform vector yields 0.
function GiniHead(shares) {
  const n = shares.length;
  if (n === 0) return 0;
  const total = sumArray(shares);
  if (total <= 0) return 0;
  let num = 0;
  for (let i = 0; i < n; i++) {
    num += (n + 1 - 2 * (i + 1)) * shares[i];
  }
  return num / (n * total);
}

// Shannon entropy H(x) = -sum x_i log x_i, with 0 log 0 = 0.
function ShannonEntropy(shares) {
  let h = 0;
  for (let i = 0; i < shares.length; i++) {
    const xi = shares[i];
    if (xi > 0) h -= xi * Math.log(xi);
  }
  return h;
}

/* ---------------------------------------------------- capping certificates */

// Top-N capping bounds for CR_k under the mass-only observation O_N(x).
// `T_N` is the omitted tail mass against the chosen denominator.
function cappingCRk(shares, T_N, k) {
  const N = shares.length;
  if (k <= N) {
    // Already inside the visible head: exact.
    const v = CRk(shares, k);
    return { lower: v, upper: v, status: "exact" };
  }
  const lower = CRk(shares, N);
  // Upper: best feasible top-(k-N) extension is bounded by (k-N)*x_N or T_N.
  const xN = shares[N - 1];
  const upper = lower + Math.min(T_N, (k - N) * xN);
  return { lower, upper, status: "interval" };
}

// Top-N capping bounds for NC_tau (returns smallest k for which prefix >= tau).
function cappingNCtau(shares, T_N, tau) {
  const N = shares.length;
  const P_N = sumArray(shares);
  if (reaches(P_N, tau)) {
    const k = NCtau(shares, tau);
    return { lower: k, upper: k, status: "exact" };
  }
  // Head insufficient: lower is N + ceil(delta / x_N); upper is +infty for
  // the mass-only observation.
  const xN = shares[N - 1];
  if (xN <= 0) return { lower: Infinity, upper: Infinity, status: "unbounded" };
  const delta = tau - P_N;
  const lower = N + ceilCount(delta / xN);
  return { lower, upper: Infinity, status: "lower-only" };
}

// Top-N capping bounds for S_p under the mass-only observation.
function cappingSp(shares, T_N, p) {
  validateOrder(p, 1);
  const N = shares.length;
  if (p === 1) return { lower: 1, upper: 1, status: "exact" };
  if (!(p > 1)) throw new Error("Power-sum certificates require p > 1");
  const lower = Sp(shares, p);
  if (T_N <= 0) return { lower, upper: lower, status: "exact" };
  // Exact upper under y_i <= x_N: pack tail into floor(T_N / x_N) copies of x_N
  // plus one leftover r.
  const xN = shares[N - 1];
  let tailUpperExact;
  if (xN <= 0) {
    tailUpperExact = 0;
  } else {
    const q = Math.floor(T_N / xN);
    const r = Math.max(0, T_N - q * xN);
    tailUpperExact = q * Math.pow(xN, p) + Math.pow(r, p);
  }
  const safeUpper = lower + Math.pow(T_N, p);
  return {
    lower,
    upper: lower + tailUpperExact,
    safe_upper: safeUpper,
    status: "interval",
  };
}

// Count-aware Gini lower and upper endpoints under known omitted positive
// count M_N. Upper is a supremum under y_i <= x_N.
function cappingGini(shares, T_N, M_N) {
  const N = shares.length;
  const xN = shares[N - 1];
  if (!Number.isInteger(M_N) || M_N < 0 || (T_N > 0 && M_N === 0)
      || (T_N === 0 && M_N > 0) || T_N > M_N * xN + 1e-12)
    return { lower: NaN, upper: NaN, status: "infeasible" };
  // Convention: shares sum to coverage P_N <= 1; tail is T_N.
  // Build the Gini formula directly.
  // d_N := sum_i (N + 1 - 2i) * x_i  (1-based i over head)
  let d_N = 0;
  for (let i = 0; i < N; i++) {
    d_N += (N + 1 - 2 * (i + 1)) * shares[i];
  }
  const n_full = N + M_N;
  // Lower endpoint (equal split of tail across M_N omitted accounts).
  let g_lower;
  if (M_N === 0) {
    // Tail must be empty; just plain Gini over head.
    const total = sumArray(shares);
    g_lower = total > 0 ? (d_N + 0 - N * 0) / N : 0;
  } else {
    g_lower = (d_N + M_N * (1.0 - T_N) - N * T_N) / n_full;
  }
  // Upper endpoint: pack q omitted at x_N, leftover r.
  let g_upper;
  if (M_N === 0) {
    g_upper = g_lower;
  } else if (xN <= 0) {
    g_upper = g_lower;
  } else {
    const q = Math.min(M_N, Math.floor(T_N / xN + 1e-12));
    let r = T_N - q * xN;
    if (r < 0) r = 0;
    if (r >= xN) r = xN - 1e-15;
    const e_max = xN * q * (M_N - q) + r * (M_N - 1 - 2 * q);
    g_upper = (d_N + M_N * (1.0 - T_N) - N * T_N + e_max) / n_full;
  }
  return { lower: g_lower, upper: g_upper, status: "count-aware" };
}

/* ---------------------------------------------- residual operators */

// LevelCap(x, a): remove total mass `a` from the largest coordinates until
// the surviving large coordinates are capped at a common level L.
// Returns the residual vector (sorted descending).
function highDrain(shares, a) {
  const n = shares.length;
  if (a <= 0) return shares.slice();
  const total = sumArray(shares);
  if (a >= total) return new Float64Array(n);
  let prefix = 0, correction = 0, L = 0;
  for (let i = 0; i < n; i++) {
    const term = shares[i] - correction;
    const next = prefix + term;
    correction = (next - prefix) - term;
    prefix = next;
    L = (prefix - a) / (i + 1);
    if (L >= (shares[i + 1] || 0)) break;
  }
  const out = new Float64Array(n);
  for (let i = 0; i < n; i++) out[i] = Math.min(shares[i], L);
  return out;
}

// TailTrim(y, a): remove `a` from the smallest coordinates first. Input may
// be sorted descending; we drain from the tail end.
function smallDrain(shares, a) {
  const n = shares.length;
  const out = new Float64Array(shares);
  let remaining = a;
  for (let i = n - 1; i >= 0 && remaining > 0; i--) {
    if (out[i] <= remaining) {
      remaining -= out[i];
      out[i] = 0;
    } else {
      out[i] -= remaining;
      remaining = 0;
    }
  }
  return out;
}

/* --------------------------------------------- attribution: Merge and Shift */

// Merge keeps one largest label in each group and moves all other whole
// holdings to it. The global cost is sum(group total - largest member).
function mergeCost(shares, groups) {
  const seen = new Set();
  let cost = 0;
  for (const group of groups) {
    if (!group.length) throw new Error("Merge groups must be nonempty");
    let total = 0, largest = 0;
    for (const i of group) {
      if (!Number.isInteger(i) || i < 0 || i >= shares.length || seen.has(i))
        throw new Error("Merge groups must partition the labels");
      seen.add(i); total += shares[i]; largest = Math.max(largest, shares[i]);
    }
    cost += total - largest;
  }
  if (seen.size !== shares.length) throw new Error("Merge groups must cover every label");
  return cost;
}

function packedPower(mass, cap, p) {
  if (mass <= 0) return 0;
  const count = Math.floor(mass / cap);
  return count * Math.pow(cap, p) + Math.pow(Math.max(0, mass - count * cap), p);
}

// The packed omitted tail is represented by its mass and cap, never expanded.
// The exact Shift upper is also a SAFE Merge upper: whole-label merges form
// a subset of the Shift allocations with the same moved-mass budget.
function jointShiftSp(shares, T_N, p, alpha) {
  validateOrder(p, 1);
  if (p === 1) return { lower: 1, upper: 1, status: "exact" };
  if (!(p > 1)) throw new Error("Power-sum certificates require p > 1");
  const x1 = shares[0], a = Math.min(alpha, 1 - x1);
  const residual = highDrain(shares, Math.min(alpha, sumArray(shares)));
  const upperTail = smallDrain(shares.slice(1), Math.max(0, a - T_N));
  const upper = Math.pow(x1 + a, p) + Sp(upperTail, p)
    + packedPower(Math.max(0, T_N - a), shares[shares.length - 1], p);
  return { lower: Sp(residual, p), upper: Math.min(1, upper),
    status: alpha === 0 && T_N === 0 ? "exact" : "interval" };
}

function jointMergeSp(shares, T_N, p, rho) {
  if (rho === 0) return p === 1 ? { lower: 1, upper: 1, status: "exact" }
    : cappingSp(shares, T_N, p);
  if (p === 1) return { lower: 1, upper: 1, status: "exact" };
  return { lower: Sp(shares, p), upper: jointShiftSp(shares, T_N, p, rho).upper,
    status: rho <= T_N ? "interval" : "safe" };
}

function jointShiftCRk(shares, T_N, k, alpha) {
  if (alpha === 0) return cappingCRk(shares, T_N, k);
  return { lower: CRk(highDrain(shares, alpha), k),
    upper: Math.min(1, cappingCRk(shares, T_N, k).upper + alpha), status: "interval" };
}

function jointMergeCRk(shares, T_N, k, rho) {
  const cap = cappingCRk(shares, T_N, k);
  return rho === 0 ? cap : { lower: cap.lower,
    upper: Math.min(1, cap.upper + rho), status: rho <= T_N ? "interval" : "safe" };
}

function packedThreshold(shares, T_N, target) {
  if (target <= 0) return 1;
  const inHead = NCtau(shares, target);
  if (inHead !== null) return inHead;
  const delta = target - sumArray(shares);
  if (reaches(sumArray(shares), target)) return shares.length;
  return shares.length + ceilCount(delta / shares[shares.length - 1]);
}

function jointShiftNCtau(shares, T_N, tau, alpha) {
  if (alpha === 0) return cappingNCtau(shares, T_N, tau);
  const lower = packedThreshold(shares, T_N, tau - alpha);
  const residual = highDrain(shares, alpha);
  // When the remaining visible holdings do not reach tau, fragmentation can
  // make the threshold count arbitrarily large. This also covers tau>1-alpha.
  let upper = NCtau(residual, tau);
  if (upper === null && reaches(sumArray(residual), tau))
    upper = residual.filter(x => x > 0).length || null;
  return { lower, upper: upper ?? Infinity, status: "interval" };
}

function jointMergeNCtau(shares, T_N, tau, rho) {
  const cap = cappingNCtau(shares, T_N, tau);
  return rho === 0 ? cap : { lower: packedThreshold(shares, T_N, tau - rho),
    upper: cap.upper, status: rho <= T_N ? "interval" : "safe" };
}

// Complete-observation helpers. The caller supplies a normalized vector.
const merge_Sp = (shares, p, rho) => jointMergeSp(shares, 0, p, rho);
const merge_CRk = (shares, k, rho) => jointMergeCRk(shares, 0, k, rho);
const merge_NCtau = (shares, tau, rho) => jointMergeNCtau(shares, 0, tau, rho);
const shift_Sp = (shares, p, alpha) => jointShiftSp(shares, 0, p, alpha);
const shift_HHI = (shares, alpha) => jointShiftSp(shares, 0, 2, alpha);
const shift_CRk = (shares, k, alpha) => jointShiftCRk(shares, 0, k, alpha);
const shift_NCtau = (shares, tau, alpha) => jointShiftNCtau(shares, 0, tau, alpha);
const composedHHI = (shares, T_N, alpha) => jointShiftSp(shares, T_N, 2, alpha);

function cappingEntropy(shares, T_N) {
  const head = ShannonEntropy(shares);
  if (T_N === 0) return { lower: head, upper: head, status: "exact" };
  const cap = shares[shares.length - 1], count = Math.floor(T_N / cap);
  const remainder = Math.max(0, T_N - count * cap);
  const term = x => x > 0 ? -x * Math.log(x) : 0;
  return { lower: head + count * term(cap) + term(remainder), upper: Infinity, status: "interval" };
}

/* ---------------------------------------------------- top-level convenience */

// Run everything for a given vector + parameters; returns a flat object.
function computeAll(opts) {
  const {
    shares, T_N, k, tau, p_default, q_default,
    rho, alpha, omitted_count,
  } = opts;
  const N = shares.length;
  const P_N = sumArray(shares);
  if (!N || shares.some((x, i) => !(x > 0) || !Number.isFinite(x) || (i && x > shares[i - 1])))
    throw new Error("Expected positive shares sorted from largest to smallest");
  if (!(T_N >= 0 && T_N < 1) || Math.abs(P_N + T_N - 1) > 1e-9)
    throw new Error("Observed shares and omitted mass must sum to one");
  if (!(tau > 0 && tau <= 1) || !(rho >= 0 && rho <= 1) || !(alpha >= 0 && alpha <= 1))
    throw new Error("Use 0 < threshold ≤ 1 and budgets between zero and one");
  validateOrder(p_default, 1);
  validateOrder(q_default);
  if (!Number.isInteger(k) || k < 1) throw new Error("Use a positive integer rank k");
  return {
    summary: {
      support: N,
      coverage: P_N,
      tail_mass: T_N,
      top_share: shares[0],
      smallest_visible_share: shares[N - 1],
    },
    raw: {
      CRk: CRk(shares, k),
      NCtau: NCtau(shares, tau),
      HHI: HHI(shares),
      Sp: Sp(shares, p_default),
      HillQ: HillQ(shares, q_default),
      GiniHead: GiniHead(shares),
      Entropy: ShannonEntropy(shares),
    },
    capping: {
      CRk: cappingCRk(shares, T_N, k),
      NCtau: cappingNCtau(shares, T_N, tau),
      HHI: cappingSp(shares, T_N, 2),
      Sp: cappingSp(shares, T_N, p_default),
      Gini: cappingGini(shares, T_N, omitted_count),
      Entropy: cappingEntropy(shares, T_N),
    },
    attribution: {
      merge: {
        CRk: jointMergeCRk(shares, T_N, k, rho),
        NCtau: jointMergeNCtau(shares, T_N, tau, rho),
        HHI: jointMergeSp(shares, T_N, 2, rho),
        Sp: jointMergeSp(shares, T_N, p_default, rho),
      },
      shift: {
        CRk: jointShiftCRk(shares, T_N, k, alpha),
        NCtau: jointShiftNCtau(shares, T_N, tau, alpha),
        HHI: jointShiftSp(shares, T_N, 2, alpha),
        Sp: jointShiftSp(shares, T_N, p_default, alpha),
      },
    },
    composed: {
      HHI: composedHHI(shares, T_N, alpha),
    },
  };
}

// Browser and Node share the same dependency-free implementation.
const Metrics = {
    sumArray, prefixSums, prefixSumsPow,
    CRk, NCtau, HHI, Sp, HillQ, GiniHead, ShannonEntropy,
    cappingCRk, cappingNCtau, cappingSp, cappingGini,
    highDrain, smallDrain, mergeCost, packedPower,
    jointShiftSp, jointMergeSp, jointShiftCRk, jointMergeCRk,
    jointShiftNCtau, jointMergeNCtau, cappingEntropy,
    merge_Sp, merge_CRk, merge_NCtau,
    shift_CRk, shift_NCtau, shift_HHI, shift_Sp,
    composedHHI,
    computeAll,
  };
if (typeof window !== "undefined") window.Metrics = Metrics;
if (typeof module !== "undefined") module.exports = Metrics;
