// app.js — UI glue + generic dependency-free plot system.
// Renders three interactive illustrations (capping convergence,
// attribution sensitivity, family-parameter sensitivity) with multi-panel
// grids of canvases. Math comes from window.Metrics (metrics.js).

"use strict";

const M = window.Metrics;

const COLORS = {
  green: "#009e73",
  orange: "#d55e00",
  red: "#c1121f",
  blue: "#0072b2",
  merge: "#c1121f",
  shift: "#0072b2",
  black: "#1a1a1a",
  axis: "#4a4a4a",
  grid: "#e6e6e2",
  muted: "#9a9a9a",
};

const FILL = (hex, a) => {
  // hex like "#009e73" → rgba
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${a})`;
};

const state = {
  dataset: null,
  shares: null,
  T_N: 0,
};

/* =========================================================
   Generic plot helper
   ========================================================= */

// opts = {
//   xScale: "linear" | "log",
//   yScale: "linear" | "log",
//   xDomain: [min, max],
//   yDomain: [min, max],     // auto if omitted
//   xLabel: string,
//   yLabel: string,
//   series: [
//     { type: "band", x: [], lower: [], upper: [], color: "#hex", fill: 0.18 },
//     { type: "line", x: [], y: [], color, dashed: bool, width: 1.5 },
//     { type: "hline", y: value, color, dashed: bool },
//     { type: "vline", x: value, color, dashed: bool },
//   ],
//   legend: [ { label, color, dashed: bool, fill: bool } ],
//   xTicks: [], yTicks: [],
//   xTickLabels: [], yTickLabels: [],
//   yClipMax: number   // clip values exceeding this for "∞-ish" axes
// }
function drawPanel(canvas, opts) {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const w = Math.max(60, Math.floor(rect.width));
  const h = Math.max(60, Math.floor(rect.height));
  if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
    canvas.width = w * dpr;
    canvas.height = h * dpr;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);

  const padL = 48, padR = 8, padT = 6, padB = 28;
  const plotW = w - padL - padR;
  const plotH = h - padT - padB;
  if (plotW <= 0 || plotH <= 0) return;

  // ---- axis scale helpers
  const xScaleType = opts.xScale || "linear";
  const yScaleType = opts.yScale || "linear";

  let [xmin, xmax] = opts.xDomain;
  let [ymin, ymax] = opts.yDomain || [Infinity, -Infinity];

  // Auto y-domain if missing
  if (!opts.yDomain || !isFinite(opts.yDomain[0]) || !isFinite(opts.yDomain[1])) {
    let lo = Infinity, hi = -Infinity;
    for (const s of opts.series) {
      const arrs = [];
      if (s.type === "band") arrs.push(s.lower, s.upper);
      if (s.type === "line") arrs.push(s.y);
      if (s.type === "hline") arrs.push([s.y]);
      for (const a of arrs) {
        for (const v of a) {
          let vv = v;
          if (opts.yClipMax !== undefined && vv > opts.yClipMax) vv = opts.yClipMax;
          if (yScaleType === "log" && vv <= 0) continue;
          if (!isFinite(vv)) continue;
          if (vv < lo) lo = vv;
          if (vv > hi) hi = vv;
        }
      }
    }
    if (!isFinite(lo) || !isFinite(hi)) { lo = 0; hi = 1; }
    if (lo === hi) { hi = lo + Math.max(1e-12, Math.abs(lo) * 0.1); }
    if (yScaleType === "log") {
      lo = Math.max(lo, 1e-12);
    } else {
      const pad = (hi - lo) * 0.06;
      lo -= pad; hi += pad;
    }
    ymin = lo; ymax = hi;
  }

  const xToPx = v => {
    if (xScaleType === "log") {
      const lv = Math.log10(Math.max(v, 1e-30));
      const lmin = Math.log10(xmin), lmax = Math.log10(xmax);
      return padL + (lv - lmin) / (lmax - lmin) * plotW;
    }
    return padL + (v - xmin) / (xmax - xmin) * plotW;
  };
  const yToPx = v => {
    let vv = v;
    if (opts.yClipMax !== undefined && vv > opts.yClipMax) vv = opts.yClipMax;
    if (yScaleType === "log") {
      const lv = Math.log10(Math.max(vv, ymin));
      const lmin = Math.log10(ymin), lmax = Math.log10(ymax);
      return padT + plotH - (lv - lmin) / (lmax - lmin) * plotH;
    }
    return padT + plotH - (vv - ymin) / (ymax - ymin) * plotH;
  };

  // ---- gridlines + tick labels
  ctx.font = "10px ui-monospace, monospace";
  ctx.fillStyle = COLORS.muted;
  ctx.strokeStyle = COLORS.grid;
  ctx.lineWidth = 1;

  const xTicks = opts.xTicks || autoTicks(xmin, xmax, xScaleType, 5);
  const yTicks = opts.yTicks || autoTicks(ymin, ymax, yScaleType, 4);

  for (const t of xTicks) {
    const x = xToPx(t);
    if (x < padL - 0.5 || x > padL + plotW + 0.5) continue;
    ctx.beginPath();
    ctx.moveTo(x, padT);
    ctx.lineTo(x, padT + plotH);
    ctx.stroke();
    ctx.fillStyle = COLORS.muted;
    ctx.textAlign = "center";
    ctx.fillText(formatTick(t, xScaleType), x, padT + plotH + 12);
  }
  for (const t of yTicks) {
    const y = yToPx(t);
    if (y < padT - 0.5 || y > padT + plotH + 0.5) continue;
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(padL + plotW, y);
    ctx.stroke();
    ctx.fillStyle = COLORS.muted;
    ctx.textAlign = "right";
    ctx.fillText(formatTick(t, yScaleType), padL - 4, y + 3);
  }

  // ---- axes box
  ctx.strokeStyle = COLORS.axis;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(padL, padT);
  ctx.lineTo(padL, padT + plotH);
  ctx.lineTo(padL + plotW, padT + plotH);
  ctx.stroke();

  // ---- series
  ctx.save();
  ctx.beginPath();
  ctx.rect(padL, padT, plotW, plotH);
  ctx.clip();

  for (const s of opts.series) {
    if (s.type === "band") {
      const fillAlpha = s.fill ?? 0.18;
      if (fillAlpha > 0) {
        ctx.fillStyle = FILL(s.color, fillAlpha);
      }
      ctx.beginPath();
      for (let i = 0; i < s.x.length; i++) {
        const x = xToPx(s.x[i]);
        const y = yToPx(s.upper[i]);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      for (let i = s.x.length - 1; i >= 0; i--) {
        const x = xToPx(s.x[i]);
        const y = yToPx(s.lower[i]);
        ctx.lineTo(x, y);
      }
      ctx.closePath();
      if (fillAlpha > 0) ctx.fill();
      if (s.outline) {
        ctx.strokeStyle = s.color;
        ctx.lineWidth = s.width || 1.5;
        if (s.dashed) ctx.setLineDash([5, 4]); else ctx.setLineDash([]);
        // upper line
        ctx.beginPath();
        for (let i = 0; i < s.x.length; i++) {
          const x = xToPx(s.x[i]);
          const y = yToPx(s.upper[i]);
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();
        // lower line
        ctx.beginPath();
        for (let i = 0; i < s.x.length; i++) {
          const x = xToPx(s.x[i]);
          const y = yToPx(s.lower[i]);
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();
        ctx.setLineDash([]);
      }
    } else if (s.type === "line") {
      ctx.strokeStyle = s.color;
      ctx.lineWidth = s.width || 1.6;
      if (s.dashed) ctx.setLineDash([3, 3]); else ctx.setLineDash([]);
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < s.x.length; i++) {
        if (!isFinite(s.y[i])) { started = false; continue; }
        const x = xToPx(s.x[i]);
        const y = yToPx(s.y[i]);
        if (!started) { ctx.moveTo(x, y); started = true; }
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.setLineDash([]);
    } else if (s.type === "hline") {
      ctx.strokeStyle = s.color || COLORS.muted;
      ctx.lineWidth = 1;
      if (s.dashed) ctx.setLineDash([3, 3]); else ctx.setLineDash([]);
      ctx.beginPath();
      ctx.moveTo(padL, yToPx(s.y));
      ctx.lineTo(padL + plotW, yToPx(s.y));
      ctx.stroke();
      ctx.setLineDash([]);
    } else if (s.type === "vline") {
      ctx.strokeStyle = s.color || COLORS.muted;
      ctx.lineWidth = 1;
      if (s.dashed) ctx.setLineDash([3, 3]); else ctx.setLineDash([]);
      ctx.beginPath();
      ctx.moveTo(xToPx(s.x), padT);
      ctx.lineTo(xToPx(s.x), padT + plotH);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }
  ctx.restore();

  // ---- axis labels
  ctx.fillStyle = COLORS.axis;
  ctx.font = "10px system-ui, sans-serif";
  ctx.textAlign = "center";
  if (opts.xLabel) ctx.fillText(opts.xLabel, padL + plotW / 2, h - 4);
  if (opts.yLabel) {
    ctx.save();
    ctx.translate(12, padT + plotH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(opts.yLabel, 0, 0);
    ctx.restore();
  }

  // ---- legend
  if (opts.legend) {
    ctx.font = "10px system-ui, sans-serif";
    ctx.textBaseline = "middle";
    let lx = padL + 6, ly = padT + 8;
    for (const it of opts.legend) {
      const swatchW = 14;
      if (it.fill) {
        ctx.fillStyle = FILL(it.color, it.fillAlpha ?? 0.22);
        ctx.fillRect(lx, ly - 4, swatchW, 8);
      }
      if (it.dashed) {
        ctx.strokeStyle = it.color;
        ctx.setLineDash([5, 4]);
      } else {
        ctx.strokeStyle = it.color;
        ctx.setLineDash([]);
      }
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.moveTo(lx, ly);
      ctx.lineTo(lx + swatchW, ly);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.textAlign = "left";
      ctx.fillStyle = COLORS.black;
      ctx.fillText(it.label, lx + swatchW + 4, ly + 0.5);
      ly += 12;
    }
    ctx.textBaseline = "alphabetic";
  }
}

function autoTicks(min, max, scale, target) {
  if (scale === "log") {
    const out = [];
    const lo = Math.ceil(Math.log10(min - 1e-15));
    const hi = Math.floor(Math.log10(max + 1e-15));
    for (let p = lo; p <= hi; p++) out.push(Math.pow(10, p));
    return out;
  }
  // linear: ~5 nice ticks
  const span = max - min;
  if (!isFinite(span) || span <= 0) return [min];
  const niceStep = niceLinearStep(span / target);
  const out = [];
  const start = Math.ceil(min / niceStep) * niceStep;
  for (let v = start; v <= max + niceStep * 1e-6; v += niceStep) {
    out.push(+v.toFixed(10));
  }
  return out;
}
function niceLinearStep(approx) {
  const exp = Math.floor(Math.log10(approx));
  const f = approx / Math.pow(10, exp);
  let m;
  if (f < 1.5) m = 1;
  else if (f < 3) m = 2;
  else if (f < 7) m = 5;
  else m = 10;
  return m * Math.pow(10, exp);
}
function formatTick(v, scale) {
  if (!isFinite(v)) return "";
  if (scale === "log") {
    const e = Math.round(Math.log10(v));
    if (Math.abs(e) <= 3) return v.toLocaleString(undefined, { maximumFractionDigits: 3 });
    return "1e" + e;
  }
  const a = Math.abs(v);
  if (a >= 1e5 || (a > 0 && a < 1e-3)) return v.toExponential(1);
  if (a >= 100) return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
  return v.toLocaleString(undefined, { maximumFractionDigits: 3 });
}

/* =========================================================
   Dataset loading
   ========================================================= */

const BUILTIN_URLS = {
  btc10k: "data/bitcoin_top10k.json",
  btc1m:  "data/bitcoin_top1m.json",
  eth10k: "data/eth_top10k.json",
};

async function loadBuiltin(key) {
  const url = BUILTIN_URLS[key];
  if (!url) return null;
  const r = await fetch(url);
  if (!r.ok) throw new Error("Failed to load " + url);
  const j = await r.json();
  const shares = Float64Array.from(j.shares_descending);
  return {
    name: j.name,
    resource: j.resource,
    full_support: j.support_full_observed,
    full_shares: shares,
    denominator: j.denominator,
    denominator_unit: j.denominator_unit || "",
    coverage_full_observed: j.coverage_full_observed,
    coverage_top_k: j.coverage_top_k,
    omitted_tail_mass_top_k_against_supply: j.omitted_tail_mass_top_k_against_supply,
    omitted_positive_count_known: j.omitted_positive_count_known ?? null,
    omitted_positive_count_scenarios: j.omitted_positive_count_scenarios ?? null,
    snapshot: j.snapshot_date || j.snapshot_time_utc || "",
    notes: j.notes || "",
  };
}

function applyCap(dataset, N) {
  const available = dataset.full_shares.length;
  const cap = Math.min(N, available);
  const headFull = dataset.full_shares.subarray(0, cap);
  const shares = new Float64Array(headFull);
  const P_N = M.sumArray(shares);
  // T_N is mass beyond the dated denominator; for ETH bundle (full support
  // observed) this is 0 once N >= support_top_k, but with N < support_top_k
  // there is still tail mass within the observation. For Bitcoin bundle the
  // top-N is a strict cap so T_N = 1 - P_N.
  const complete = cap === available && dataset.omitted_tail_mass_top_k_against_supply === 0;
  const T_N = complete ? 0 : Math.max(0, 1 - P_N);
  return { shares, T_N, available };
}

/* =========================================================
   DOM helpers
   ========================================================= */

function $(id) { return document.getElementById(id); }
function fmt(x, opts = {}) {
  if (x === null || x === undefined) return "—";
  if (x === Infinity) return "∞";
  if (typeof x !== "number" || !isFinite(x)) return String(x);
  if (opts.int) return Math.round(x).toLocaleString();
  const a = Math.abs(x);
  if (a === 0) return "0";
  if (a < 1e-4 || a >= 1e5) return x.toExponential(3);
  if (a < 1) return x.toFixed(6);
  return x.toLocaleString(undefined, { maximumFractionDigits: 4 });
}
function badge(text, cls) { return `<span class="badge ${cls}">${text}</span>`; }
function setTile(id, rows) {
  const node = $(id);
  if (!node) return;
  const body = node.querySelector(".metric-rows");
  body.innerHTML = rows.map(r => {
    if (r.divider) return `<div class="divider">${r.divider}</div>`;
    return `<div class="row"><div class="label">${r.label}</div><div class="value">${r.value}</div></div>`;
  }).join("");
}

function intervalRow(label, iv) {
  if (iv === null) return { label, value: "not computed" };
  if (iv.status === "infeasible") return { label, value: "Count incompatible with omitted mass and share cap" };
  if (iv.lower === iv.upper && iv.status === "exact") {
    return { label, value: `${fmt(iv.lower)} ${badge("exact", "exact")}` };
  }
  if (iv.upper === Infinity) {
    return { label, value: `[${fmt(iv.lower)}, ∞) ${badge(iv.status === "safe" ? "conservative" : iv.status || "lower-only", "unbounded")}` };
  }
  const safeMarker = iv.safe_upper && iv.safe_upper !== iv.upper
    ? ` (conservative ${fmt(iv.safe_upper)})` : "";
  return {
    label,
    value: `[${fmt(iv.lower)}, ${fmt(iv.upper)}]${safeMarker} ${badge(iv.status === "safe" ? "conservative" : iv.status || "interval", iv.status === "safe" ? "safe" : iv.status === "exact" ? "exact" : "interval")}`,
  };
}

/* =========================================================
   Tile rendering
   ========================================================= */

// Format an attribution interval for a tile row. iv = { lower, upper, status }.
// badgeClass controls the strategy color.
// If `descriptiveOnly` is true, report that this calculator omits the bound.
// Used for Gini/entropy attribution and Hill_q for q ≤ 1.
function attribRow(iv, label, badgeClass, descriptiveOnly) {
  if (descriptiveOnly || !iv) return `<span class="badge descriptive">not computed</span>`;
  return intervalRow(label, iv).value;
}

function tileSection(title, rawValue, cappingInterval, attribMerge, attribShift, params, opts = {}) {
  const rho = params.rho.toFixed(2), alpha = params.alpha.toFixed(2);
  const descriptive = opts.descriptive === true;
  return [
    { label: opts.rawLabel || "raw", value: rawValue },
    { divider: opts.cappingLabel || "Capping" },
    intervalRow("[L, U]", cappingInterval),
    { divider: "Capping + attribution" },
    { label: `Merge (ρ=${rho})`, value: attribRow(attribMerge, "Merge", "merge", descriptive) },
    { label: `Shift (ρ=${alpha})`, value: attribRow(attribShift, "Shift", "shift", descriptive) },
  ];
}

function renderTiles(r, params) {
  // CR_k
  setTile("tile-CRk", tileSection(
    "CR_k", fmt(r.raw.CRk), r.capping.CRk,
    r.attribution.merge.CRk, r.attribution.shift.CRk,
    params, { rawLabel: `raw CR_${params.k}` }
  ));

  // NC_τ
  const rawNC = r.raw.NCtau === null ? `> ${state.shares.length} (head insufficient)` : fmt(r.raw.NCtau, { int: true });
  setTile("tile-NCtau", tileSection(
    "NC_τ", rawNC, r.capping.NCtau,
    r.attribution.merge.NCtau, r.attribution.shift.NCtau,
    params, { rawLabel: `raw NC_${params.tau.toFixed(3)}` }
  ));

  // HHI
  setTile("tile-HHI", tileSection(
    "HHI", fmt(r.raw.HHI), r.capping.HHI,
    r.attribution.merge.HHI, r.attribution.shift.HHI,
    params, { rawLabel: "observed contribution" }
  ));

  // S_p
  setTile("tile-Sp", tileSection(
    "S_p", fmt(r.raw.Sp), r.capping.Sp,
    r.attribution.merge.Sp, r.attribution.shift.Sp,
    params, { rawLabel: "observed contribution" }
  ));

  // Gini — count-aware capping band; attribution bounds are not implemented.
  const M_total_val = params.M_total || 0;
  const M_N_val = Math.max(0, M_total_val - state.shares.length);
  const giniNote = "";
  setTile("tile-Gini", tileSection(
    "Gini",
    `${fmt(r.raw.GiniHead)} ${badge("descriptive", "descriptive")}`,
    r.capping.Gini,
    null, null, params,
    {
      rawLabel: "raw Gini (head only)",
      cappingLabel: `Count-aware  M=${M_total_val.toLocaleString()}, M_N=${M_N_val.toLocaleString()}${giniNote}`,
      descriptive: true,
    }
  ));

  // Hill_q — for q > 1 inherits from S_q (attribution OK); for q ≤ 1 descriptive.
  const qVal = params.q;
  const hillDescriptive = qVal <= 1;
  const hillSqRaw = M.Sp(state.shares, qVal);
  const hillBands = hillDescriptive ? { merge: null, shift: null } : {
    merge: M.jointMergeSp(state.shares, state.T_N, qVal, params.rho),
    shift: M.jointShiftSp(state.shares, state.T_N, qVal, params.alpha),
  };
  // Transform S_q bands to Hill_q via z^{1/(1-q)} (orientation flips for q>1).
  const toHill = z => z === 0 ? Infinity : (z === null || !isFinite(z) || z < 0) ? NaN : Math.pow(z, 1 / (1 - qVal));
  const xformBand = b => b === null ? null : {
    lower: Math.min(toHill(b.lower), toHill(b.upper)),
    upper: Math.max(toHill(b.lower), toHill(b.upper)),
    status: b.status,
  };
  setTile("tile-Hill", tileSection(
    "Hill_q",
    `${fmt(r.raw.HillQ)} ${qVal <= 1 ? badge("descriptive for q≤1", "descriptive") : ""}`,
    hillDescriptive ? null : xformBand(M.cappingSp(state.shares, state.T_N, qVal)),
    xformBand(hillBands.merge), xformBand(hillBands.shift),
    params, {
      rawLabel: `Hill_${qVal}`,
      cappingLabel: hillDescriptive ? "Capping — not computed for q ≤ 1" : "Capping",
      descriptive: hillDescriptive,
    }
  ));

  // Entropy — capping endpoints; attribution bounds are not implemented.
  setTile("tile-Entropy", tileSection(
    "Entropy",
    `${fmt(r.raw.Entropy)} ${badge("descriptive", "descriptive")}`,
    r.capping.Entropy,
    null, null, params,
    {
      rawLabel: "observed contribution",
      cappingLabel: "Capping",
      descriptive: true,
    }
  ));

  setTile("tile-Composed", [
    { label: "observed labels", value: fmt(r.summary.support, { int: true }) },
    { label: "observed resource", value: (100 * r.summary.coverage).toFixed(6) + "%" },
    { label: "omitted resource", value: (100 * r.summary.tail_mass).toFixed(6) + "%" },
    { label: "Merge budget", value: (100 * params.rho).toFixed(1) + "% moved as whole holdings" },
    { label: "Shift budget", value: (100 * params.alpha).toFixed(1) + "% moved, including parts" },
  ]);
}

/* =========================================================
   Sweeps for the three figure cards
   ========================================================= */

// Sweep over N (log scale) for the capping panels. Returns arrays
// { Ns, CR_lo, CR_hi, NC_lo, NC_hi, HHI_lo, HHI_hi, Gini_lo, Gini_hi }
function sweepCapping(dataset, k, tau, M_total) {
  const full = dataset.full_shares;
  const max = full.length;
  // Build the log grid of caps; anchor a few round values.
  const anchors = [1, 3, 10, 30, 100, 300, 1000, 3000, 10000, 30000, 100000, 300000, max];
  const Nsset = new Set();
  for (let lg = 2; lg <= Math.log10(max); lg += 0.08) {
    Nsset.add(Math.min(max, Math.max(100, Math.round(Math.pow(10, lg)))));
  }
  for (const a of anchors) if (a <= max) Nsset.add(a);
  const Ns = Array.from(Nsset).sort((a, b) => a - b);

  // Precompute running sums (also cumIX = sum_{j=1..i} j*x_j for the Gini
  // incremental formula, so each Gini sweep point is O(1) instead of O(N)).
  const cumX = M.prefixSums(full);
  const cumX2 = new Float64Array(max);
  const cumIX = new Float64Array(max);
  let sX2 = 0, sIX = 0;
  for (let i = 0; i < max; i++) {
    sX2 += full[i] * full[i];
    sIX += (i + 1) * full[i]; // 1-based rank
    cumX2[i] = sX2;
    cumIX[i] = sIX;
  }

  // For CR_k we also need cumsum at index k-1.
  const CRk_exact = k <= max ? cumX[k - 1] : null;

  const CR_lo = [], CR_hi = [];
  const NC_lo = [], NC_hi = [];
  const HHI_lo = [], HHI_hi = [];
  const Gini_lo = [], Gini_hi = [];

  for (const N of Ns) {
    const P_N = cumX[N - 1];
    const T_N = Math.max(0, 1 - P_N);
    const xN = full[N - 1];

    // CR_k capping
    if (k <= N && CRk_exact !== null) {
      CR_lo.push(CRk_exact);
      CR_hi.push(CRk_exact);
    } else {
      const lo = cumX[N - 1];
      const hi = lo + Math.min(T_N, (k - N) * xN);
      CR_lo.push(lo);
      CR_hi.push(hi);
    }

    const ncBand = M.cappingNCtau(full.subarray(0, N), T_N, tau);
    NC_lo.push(ncBand.lower);
    NC_hi.push(isFinite(ncBand.upper) ? ncBand.upper : NaN);

    // HHI capping (exact tail-packed upper)
    const lowerHHI = cumX2[N - 1];
    let tailUpperExact = 0;
    if (xN > 0 && T_N > 0) {
      const q = Math.floor(T_N / xN + 1e-15);
      const r = T_N - q * xN;
      tailUpperExact = q * xN * xN + r * r;
    }
    HHI_lo.push(lowerHHI);
    HHI_hi.push(lowerHHI + tailUpperExact);

    // Count-aware Gini using M_total to obtain the omitted positive count.
    const M_N = Math.max(0, M_total - N);
    // d_N = sum_i (N + 1 - 2i) * x_i = (N+1) * cumX[N-1] - 2 * cumIX[N-1].
    // Incremental O(1) per sweep point using precomputed prefix sums.
    const d_N = (N + 1) * cumX[N - 1] - 2 * cumIX[N - 1];
    const n_full = N + M_N;
    let g_lo, g_hi;
    if (M_total < N || (T_N > 1e-12 && M_N === 0) || (T_N < 1e-12 && M_N > 0)) {
      g_lo = NaN; g_hi = NaN;
    } else if (M_N === 0) {
      // No omitted accounts; head Gini only.
      g_lo = d_N / (N * Math.max(P_N, 1e-30));
      g_hi = g_lo;
    } else if (xN > 0 && T_N > M_N * xN) {
      // Infeasible: cannot fit tail mass under the y_i <= x_N cap with M_N
      // accounts. Mark as a degenerate point — the certificate is empty.
      g_lo = NaN; g_hi = NaN;
    } else {
      g_lo = (d_N + M_N * (1.0 - T_N) - N * T_N) / n_full;
      if (xN <= 0) {
        g_hi = g_lo;
      } else {
        const q = Math.min(M_N, Math.floor(T_N / xN + 1e-12));
        let r = T_N - q * xN;
        if (r < 0) r = 0;
        if (r >= xN) r = xN - 1e-15;
        const e_max = xN * q * (M_N - q) + r * (M_N - 1 - 2 * q);
        g_hi = (d_N + M_N * (1.0 - T_N) - N * T_N + e_max) / n_full;
      }
      // Clamp to [0, 1] just in case of numerical edge effects.
      g_lo = Math.max(0, Math.min(1, g_lo));
      g_hi = Math.max(0, Math.min(1, g_hi));
    }
    Gini_lo.push(g_lo);
    Gini_hi.push(g_hi);
  }

  return { Ns, CR_lo, CR_hi, NC_lo, NC_hi, HHI_lo, HHI_hi, Gini_lo, Gini_hi };
}

// Sweep over the budget b in [0, 0.3] for the attribution panels.
function sweepAttribution(shares, k, tau) {
  const Bs = [];
  for (let b = 0; b <= 0.3 + 1e-9; b += 0.01) Bs.push(+b.toFixed(4));

  const merge_CR_lo = [], merge_CR_hi = [];
  const shift_CR_lo = [], shift_CR_hi = [];
  const merge_NC_lo = [], merge_NC_hi = [];
  const shift_NC_lo = [], shift_NC_hi = [];

  const merge_HHI_lo = [], merge_HHI_hi = [];
  const shift_HHI_lo = [], shift_HHI_hi = [];

  const baseCRk = M.CRk(shares, k);
  const baseNC = M.NCtau(shares, tau);
  const baseHHI = M.HHI(shares);
  for (const b of Bs) {
    const mc = M.jointMergeCRk(shares, state.T_N, k, b);
    const sc = M.jointShiftCRk(shares, state.T_N, k, b);
    const mn = M.jointMergeNCtau(shares, state.T_N, tau, b);
    const sn = M.jointShiftNCtau(shares, state.T_N, tau, b);
    const mh = M.jointMergeSp(shares, state.T_N, 2, b);
    const sh = M.jointShiftSp(shares, state.T_N, 2, b);
    merge_CR_lo.push(mc.lower); merge_CR_hi.push(mc.upper);
    shift_CR_lo.push(sc.lower); shift_CR_hi.push(sc.upper);
    merge_NC_lo.push(mn.lower); merge_NC_hi.push(isFinite(mn.upper) ? mn.upper : NaN);
    shift_NC_lo.push(sn.lower); shift_NC_hi.push(isFinite(sn.upper) ? sn.upper : NaN);
    merge_HHI_lo.push(mh.lower); merge_HHI_hi.push(mh.upper);
    shift_HHI_lo.push(sh.lower); shift_HHI_hi.push(sh.upper);
  }

  return {
    Bs, baseCRk, baseNC, baseHHI,
    merge_CR_lo, merge_CR_hi, shift_CR_lo, shift_CR_hi,
    merge_NC_lo, merge_NC_hi, shift_NC_lo, shift_NC_hi,
    merge_HHI_lo, merge_HHI_hi, shift_HHI_lo, shift_HHI_hi,
  };
}

// Family-parameter sweep over p (for S_p) and q (for Hill_q).
function sweepFamily(shares, rho) {
  const Ps = [];
  for (let p = 1.1; p <= 5 + 1e-9; p += 0.1) Ps.push(+p.toFixed(3));
  const Sp_lo = [], Sp_hi = [];
  for (const p of Ps) {
    const interval = M.jointMergeSp(shares, state.T_N, p, rho);
    Sp_lo.push(interval.lower);
    Sp_hi.push(interval.upper);
  }

  // Hill_q: avoid q very near 1 where Hill_q via S_q^{1/(1-q)} diverges
  // numerically; restrict to q in [1.25, 5].
  const Qs = [];
  for (let q = 1.25; q <= 5 + 1e-9; q += 0.05) Qs.push(+q.toFixed(3));
  const Hq_lo = [], Hq_hi = [];
  for (const q of Qs) {
    const interval = M.jointMergeSp(shares, state.T_N, q, rho);
    const baseSq = interval.lower;
    const upperSq = interval.upper;
    // Hill_q = S_q^{1/(1-q)}: for q>1, 1/(1-q) < 0, so larger S_q → smaller Hill_q.
    const Hl = Math.pow(upperSq, 1 / (1 - q));
    const Hu = Math.pow(baseSq, 1 / (1 - q));
    Hq_lo.push(Hl);
    Hq_hi.push(Hu);
  }

  return { Ps, Sp_lo, Sp_hi, Qs, Hq_lo, Hq_hi };
}

/* =========================================================
   Render each figure card
   ========================================================= */

function renderCappingPanels(ds, k, tau, M_total) {
  const sw = sweepCapping(ds, k, tau, M_total);

  // CR_k panel (log x, linear y in [0, 1])
  drawPanel($("cap-CR"), {
    xScale: "log", yScale: "linear",
    xDomain: [sw.Ns[0], sw.Ns[sw.Ns.length - 1]],
    yDomain: [0, 1.02],
    xLabel: "cap N", yLabel: `CR_${k}`,
    series: [
      { type: "band", x: sw.Ns, lower: sw.CR_lo, upper: sw.CR_hi, color: COLORS.green, fill: 0.20 },
      { type: "line", x: sw.Ns, y: sw.CR_lo, color: COLORS.green, width: 1.8 },
      { type: "line", x: sw.Ns, y: sw.CR_hi, color: COLORS.green, dashed: true, width: 1.4 },
    ],
  });

  // NC_τ panel (log x, log y, clip ∞)
  const ncMax = Math.max(...sw.NC_lo.filter(v => isFinite(v))) * 5 || ds.full_shares.length;
  const ncHiSeries = sw.NC_hi.map(v => isFinite(v) ? v : ncMax * 2);
  drawPanel($("cap-NC"), {
    xScale: "log", yScale: "log",
    xDomain: [sw.Ns[0], sw.Ns[sw.Ns.length - 1]],
    yLabel: "NC_τ",
    xLabel: "cap N",
    yClipMax: ncMax * 2.5,
    series: [
      { type: "band", x: sw.Ns, lower: sw.NC_lo, upper: ncHiSeries, color: COLORS.green, fill: 0.20 },
      { type: "line", x: sw.Ns, y: sw.NC_lo, color: COLORS.green, width: 1.8 },
    ],
  });

  // HHI panel (log x, log y)
  drawPanel($("cap-HHI"), {
    xScale: "log", yScale: "log",
    xDomain: [sw.Ns[0], sw.Ns[sw.Ns.length - 1]],
    xLabel: "cap N", yLabel: "HHI",
    series: [
      { type: "band", x: sw.Ns, lower: sw.HHI_lo, upper: sw.HHI_hi, color: COLORS.green, fill: 0.20 },
      { type: "line", x: sw.Ns, y: sw.HHI_lo, color: COLORS.green, width: 1.8 },
      { type: "line", x: sw.Ns, y: sw.HHI_hi, color: COLORS.green, dashed: true, width: 1.4 },
    ],
  });

  // Gini panel (log x, linear y in [0, 1])
  drawPanel($("cap-Gini"), {
    xScale: "log", yScale: "linear",
    xDomain: [sw.Ns[0], sw.Ns[sw.Ns.length - 1]],
    yDomain: [0, 1.02],
    xLabel: "cap N", yLabel: `Gini  (M = ${M_total.toLocaleString()})`,
    series: [
      { type: "band", x: sw.Ns, lower: sw.Gini_lo, upper: sw.Gini_hi, color: COLORS.green, fill: 0.20 },
      { type: "line", x: sw.Ns, y: sw.Gini_lo, color: COLORS.green, width: 1.8 },
      { type: "line", x: sw.Ns, y: sw.Gini_hi, color: COLORS.green, dashed: true, width: 1.4 },
    ],
  });
}

function renderAttributionPanels(shares, k, tau) {
  const sw = sweepAttribution(shares, k, tau);
  const modelLegend = [
    { label: "Merge conservative bound", color: COLORS.merge, fill: true, fillAlpha: 0.18 },
    { label: "Shift sharp interval", color: COLORS.shift, dashed: true },
  ];

  // CR_k panel
  drawPanel($("att-CR"), {
    xScale: "linear", yScale: "linear",
    xDomain: [sw.Bs[0], sw.Bs[sw.Bs.length - 1]],
    xLabel: "ρ", yLabel: `CR_${k}`,
    series: [
      { type: "band", x: sw.Bs, lower: sw.merge_CR_lo, upper: sw.merge_CR_hi, color: COLORS.merge, fill: 0.18, outline: true, width: 1.7 },
      { type: "band", x: sw.Bs, lower: sw.shift_CR_lo, upper: sw.shift_CR_hi, color: COLORS.shift, fill: 0.07, outline: true, dashed: true, width: 1.8 },
      { type: "hline", y: sw.baseCRk, color: COLORS.black, dashed: false },
    ],
    legend: modelLegend,
  });

  // NC_τ panel (log y)
  // collect finite values to set domain
  const ncFinite = sw.merge_NC_lo.concat(sw.merge_NC_hi, sw.shift_NC_lo, sw.shift_NC_hi).filter(v => isFinite(v) && v > 0);
  const ncMin = Math.max(1, Math.min(...ncFinite) || 1);
  const ncMax = Math.max(...ncFinite) * 2 || 1e4;
  drawPanel($("att-NC"), {
    xScale: "linear", yScale: "log",
    xDomain: [sw.Bs[0], sw.Bs[sw.Bs.length - 1]],
    yDomain: [ncMin, ncMax],
    xLabel: "ρ", yLabel: "NC_τ",
    series: [
      { type: "band", x: sw.Bs, lower: sw.merge_NC_lo, upper: sw.merge_NC_hi, color: COLORS.merge, fill: 0.18, outline: true, width: 1.7 },
      { type: "band", x: sw.Bs, lower: sw.shift_NC_lo, upper: sw.shift_NC_hi, color: COLORS.shift, fill: 0.07, outline: true, dashed: true, width: 1.8 },
      { type: "hline", y: sw.baseNC || 1, color: COLORS.black },
    ],
    legend: modelLegend,
  });

  // HHI panel
  drawPanel($("att-HHI"), {
    xScale: "linear", yScale: "log",
    xDomain: [sw.Bs[0], sw.Bs[sw.Bs.length - 1]],
    xLabel: "ρ", yLabel: "HHI",
    series: [
      { type: "band", x: sw.Bs, lower: sw.merge_HHI_lo, upper: sw.merge_HHI_hi, color: COLORS.merge, fill: 0.18, outline: true, width: 1.7 },
      { type: "band", x: sw.Bs, lower: sw.shift_HHI_lo, upper: sw.shift_HHI_hi, color: COLORS.shift, fill: 0.07, outline: true, dashed: true, width: 1.8 },
      { type: "hline", y: sw.baseHHI, color: COLORS.black },
    ],
    legend: modelLegend,
  });
}

function renderFamilyPanels(shares, rho) {
  const sw = sweepFamily(shares, rho);
  drawPanel($("fam-Sp"), {
    xScale: "linear", yScale: "log",
    xDomain: [sw.Ps[0], sw.Ps[sw.Ps.length - 1]],
    xLabel: "p", yLabel: `S_p band  (ρ = ${rho.toFixed(2)})`,
    series: [
      { type: "band", x: sw.Ps, lower: sw.Sp_lo, upper: sw.Sp_hi, color: COLORS.green, fill: 0.20 },
      { type: "line", x: sw.Ps, y: sw.Sp_lo, color: COLORS.green, width: 1.8 },
      { type: "line", x: sw.Ps, y: sw.Sp_hi, color: COLORS.green, dashed: true, width: 1.4 },
      { type: "vline", x: 2, color: COLORS.muted, dashed: true },
    ],
  });

  drawPanel($("fam-Hill"), {
    xScale: "linear", yScale: "log",
    xDomain: [sw.Qs[0], sw.Qs[sw.Qs.length - 1]],
    xLabel: "q", yLabel: `Hill_q band  (ρ = ${rho.toFixed(2)})`,
    series: [
      { type: "band", x: sw.Qs, lower: sw.Hq_lo, upper: sw.Hq_hi, color: COLORS.green, fill: 0.20 },
      { type: "line", x: sw.Qs, y: sw.Hq_lo, color: COLORS.green, width: 1.8 },
      { type: "line", x: sw.Qs, y: sw.Hq_hi, color: COLORS.green, dashed: true, width: 1.4 },
      { type: "vline", x: 2, color: COLORS.muted, dashed: true },
    ],
  });
}

/* =========================================================
   Main recompute
   ========================================================= */

function setStatus(text, cls) {
  const node = $("status");
  if (!node) return;
  node.textContent = text;
  node.className = "status" + (cls ? " " + cls : "");
}

function recompute() {
  try {
    if (!state.dataset) { setStatus("no dataset loaded", "error"); return; }
    setStatus("computing…", "computing");
    const t0 = performance.now();
    const requestedN = Math.max(1, parseInt($("N").value, 10) || 1);
    const framed = applyCap(state.dataset, requestedN);
    const N = framed.shares.length;
    $("N").value = N;
    const override = $("T_N").value.trim();
    state.T_N = override === "" ? framed.T_N : Number(override);
    if (!(state.T_N >= 0 && state.T_N < 1)) throw new Error("Omitted mass must be between 0 and 1 (excluding 1)");
    // A tail override changes the denominator: visible shares must sum to 1-T.
    const factor = (1 - state.T_N) / M.sumArray(framed.shares);
    state.shares = Float64Array.from(framed.shares, x => x * factor);
    $("T_N").placeholder = "Auto: " + framed.T_N.toPrecision(8);

    const M_total_input = Math.max(0, parseInt($("M_total").value, 10) || 0);
    const k = Math.max(1, parseInt($("k").value, 10) || 1);
    const tau = parseFloat($("tau").value);
    const p = parseFloat($("p").value);
    const q = parseFloat($("q").value);
    const rho = parseFloat($("rho").value);
    const alpha = parseFloat($("alpha").value);

    $("rho-val").textContent = rho.toFixed(3);
    $("alpha-val").textContent = alpha.toFixed(3);

    const M_total = M_total_input;
    const M_N_for_tile = M_total - N;

    const r = M.computeAll({
      shares: state.shares,
      T_N: state.T_N,
      k, tau, p_default: p, q_default: q, rho, alpha,
      omitted_count: M_N_for_tile,
    });
    renderTiles(r, { k, tau, p, q, rho, alpha, M_total });

    renderCappingPanels({ ...state.dataset, full_shares: state.shares }, k, tau, M_total);
    renderAttributionPanels(state.shares, k, tau);
    renderFamilyPanels(state.shares, rho);

    const ms = Math.round(performance.now() - t0);
    setStatus(`updated in ${ms} ms  (M = ${M_total.toLocaleString()})`, "done");
  } catch (e) {
    console.error("recompute failed:", e);
    setStatus("error: " + e.message, "error");
  }
}

// Debounce wrapper so that holding down a key in a number input doesn't
// trigger 10+ heavy sweeps per second on the 1M dataset.
let debounceTimer = null;
function scheduleRecompute(delay = 30) {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(recompute, delay);
}

/* =========================================================
   Dataset info + upload + wiring
   ========================================================= */

function renderDatasetInfo(ds) {
  $("dataset-info").textContent = [
    `name      : ${ds.name}`,
    `resource  : ${ds.resource}`,
    `snapshot  : ${ds.snapshot}`,
    `labels    : ${ds.full_shares.length.toLocaleString()} of ${ds.full_support.toLocaleString()} supplied records`,
    `denom     : ${fmt(ds.denominator)} ${ds.denominator_unit}`,
    `coverage  : ${fmt(ds.coverage_top_k)} (top-N) | ${fmt(ds.coverage_full_observed)} (full obs.)`,
    `T_N (sup) : ${fmt(ds.omitted_tail_mass_top_k_against_supply)}`,
    ds.omitted_positive_count_known !== null
      ? `M_N known : ${fmt(ds.omitted_positive_count_known, { int: true })}`
      : `M_N scen. : ${(ds.omitted_positive_count_scenarios || []).map(s => s.toLocaleString()).join(" / ")}`,
    "",
    ds.notes,
  ].join("\n");
}

async function parseUpload(file) {
  const text = await file.text();
  const name = file.name.toLowerCase();
  let shares = [];
  if (name.endsWith(".json")) {
    const j = JSON.parse(text);
    if (Array.isArray(j)) shares = j.map(Number);
    else if (j.shares_descending) shares = j.shares_descending.map(Number);
    else if (j.shares) shares = j.shares.map(Number);
    else throw new Error("JSON must be an array or have a 'shares' / 'shares_descending' field");
  } else {
    const lines = text.split(/\r?\n/).filter(l => l.trim().length > 0);
    shares = [];
    for (const line of lines) {
      const tokens = line.split(/[,;\t ]+/).filter(t => t.length > 0);
      let v = NaN;
      for (let j = tokens.length - 1; j >= 0; j--) {
        const t = Number(tokens[j]);
        if (isFinite(t)) { v = t; break; }
      }
      if (isFinite(v) && v > 0) shares.push(v);
    }
  }
  shares = shares.filter(x => Number.isFinite(x) && x > 0);
  if (shares.length === 0) throw new Error("No positive numeric balances found in file.");
  shares.sort((a, b) => b - a);
  const total = shares.reduce((s, x) => s + x, 0);
  const normalized = shares.map(x => x / total);
  return {
    name: `Uploaded: ${file.name}`,
    resource: "custom",
    full_support: shares.length,
    full_shares: Float64Array.from(normalized),
    denominator: total,
    denominator_unit: "(raw sum)",
    coverage_full_observed: 1,
    coverage_top_k: 1,
    omitted_tail_mass_top_k_against_supply: 0,
    omitted_positive_count_known: 0,
    snapshot: new Date().toISOString().slice(0, 10),
    notes: "Custom upload, normalized by the sum of supplied positive balances.",
  };
}

async function selectDataset(key) {
  if (key === "upload") { $("filepicker").click(); return; }
  setStatus("loading dataset…", "computing");
  $("dataset-info").textContent = "loading dataset…";
  const t0 = performance.now();
  let ds;
  try {
    ds = await loadBuiltin(key);
  } catch (e) {
    $("dataset-info").textContent = "Failed to load dataset: " + e.message;
    setStatus("load failed", "error");
    return;
  }
  if (!ds) return;
  state.dataset = ds;
  const defaultN = key === "btc1m" ? 1_000_000 : Math.min(10000, ds.full_shares.length);
  $("N").value = defaultN;
  $("T_N").value = "";
  // M_total field holds the total positive count.
  if (ds.omitted_positive_count_known !== null && ds.omitted_positive_count_known !== undefined) {
    $("M_total").value = ds.omitted_positive_count_known + defaultN;
  } else if (ds.omitted_positive_count_scenarios) {
    $("M_total").value = ds.omitted_positive_count_scenarios[1]; // middle scenario
  } else {
    $("M_total").value = defaultN;
  }
  $("tau").value = key === "eth10k" ? (1 / 3).toFixed(4) : "0.5";
  renderDatasetInfo(ds);
  const loadMs = Math.round(performance.now() - t0);
  console.log(`loaded ${key}: ${ds.full_shares.length.toLocaleString()} shares in ${loadMs} ms`);
  recompute();
}

function wireUp() {
  $("dataset").addEventListener("change", e => selectDataset(e.target.value));
  $("filepicker").addEventListener("change", async e => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      const ds = await parseUpload(file);
      state.dataset = ds;
      $("N").value = Math.min(10000, ds.full_shares.length);
      $("T_N").value = "";
      $("M_total").value = ds.full_shares.length;
      renderDatasetInfo(ds);
      recompute();
    } catch (err) {
      setStatus("upload failed: " + err.message, "error");
    }
  });
  // Sliders → live (no debounce, very cheap)
  for (const id of ["rho", "alpha"]) {
    $(id).addEventListener("input", recompute);
  }
  // Number inputs → live on every keystroke, debounced to coalesce key-repeats
  // and to keep typing responsive on the 1M dataset.
  for (const id of ["N", "T_N", "M_total", "k", "tau", "p", "q"]) {
    $(id).addEventListener("input", () => {
      if (id === "N") $("T_N").value = "";
      scheduleRecompute(60);
    });
    // Also fire on blur (change) so paste / spin-arrow clicks register immediately
    $(id).addEventListener("change", recompute);
  }
  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(recompute, 120);
  });
}

window.addEventListener("DOMContentLoaded", async () => {
  wireUp();
  await selectDataset("btc10k");
});
