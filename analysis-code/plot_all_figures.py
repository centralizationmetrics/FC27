#!/usr/bin/env python3
"""Regenerate all paper figures with compact wide-row layouts.

Outputs (PDF + PNG):
  - figure_bitcoin_top1m_capping_convergence.{pdf,png}     (1x4, capping)
  - figure_attribution_two_models.{pdf,png}                (1x3 attribution
                                                            sensitivity for
                                                            Merge/Shift)
  - figure_eth_merge_shift_calibration.{pdf,png}           (1x3 Ethereum
                                                            withdrawal-address
                                                            sensitivity)
  - figure_family_parameter_sensitivity.{pdf,png}          (1x2: Merge/Shift
                                                            power-sum and Hill
                                                            bands as the family
                                                            parameter varies)
"""

import csv
import gzip
import json
import runpy
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FixedLocator, MaxNLocator
import numpy as np

from joint_capping import (
    JointShift, capping_power_interval, joint_metric_bands, load_bitcoin_observation,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# Unified colour palette (Wong colorblind-friendly).
LINE_TRUTH = "#111111"
COLOR_MERGE = "#c1121f"        # Merge region (red)
COLOR_CAPPING = "#009e73"  # Bitcoin capping band (green)
COLOR_SHIFT = "#0072b2"        # Shift region / envelope (blue)
COLOR_GINI_TAIL = "#7f4ea3"
COLOR_GINI_HEAD = "#bc4749"

# FC uses the single-column LNCS text block (12.2 cm).  Generate Figures 2
# and 4 at their final physical width so their point sizes survive unchanged.
LNCS_TEXT_WIDTH_IN = 12.2 / 2.54
HATCH_MERGE = "//"              # upward diagonal
HATCH_SHIFT = r"\\"             # downward diagonal
FILL_MERGE = matplotlib.colors.to_rgba(COLOR_MERGE, 0.18)
FILL_SHIFT = matplotlib.colors.to_rgba(COLOR_SHIFT, 0.13)

# Capping-figure bands use the same colorblind-friendly palette as the
# attribution-figure regions.
BAND_BTC = COLOR_CAPPING

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.size": 18,
        "axes.titlesize": 18,
        "axes.labelsize": 18,
        "xtick.labelsize": 18,
        "ytick.labelsize": 18,
        "legend.fontsize": 18,
        "figure.titlesize": 18,
        "axes.linewidth": 0.9,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linewidth": 0.6,
        "hatch.linewidth": 1.4,
        "pdf.fonttype": 42,
    }
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open() as f:
        return list(csv.DictReader(f))


def open_text(path: Path):
    if path.exists():
        return path.open()
    gz_path = path.with_suffix(path.suffix + ".gz")
    if gz_path.exists():
        return gzip.open(gz_path, "rt")
    return path.open()


def col(rows: list[dict[str, str]], key: str, cast=float) -> np.ndarray:
    out = []
    for r in rows:
        v = r[key]
        if v == "" or v == "nan":
            out.append(np.nan)
        else:
            out.append(cast(v))
    return np.asarray(out)


def plot_band(ax, x, lower, upper, color, label=None, alpha=0.22):
    ax.fill_between(x, lower, upper, color=color, alpha=alpha, linewidth=0,
                    label=label)
    ax.plot(x, lower, color=color, linewidth=1.3)
    ax.plot(x, upper, color=color, linewidth=1.3)


def style_logx(ax):
    ax.set_xscale("log")
    ax.tick_params(axis="both", which="major", length=3.5)
    ax.tick_params(axis="both", which="minor", length=2)


# ---------------------------------------------------------------------------
# Capping figures
# ---------------------------------------------------------------------------

def make_capping_figure(rows, color, panels, out_stem, figsize):
    n_panels = len(panels)
    fig, axes = plt.subplots(
        1, n_panels, figsize=figsize, sharex=True, constrained_layout=True
    )
    if n_panels == 1:
        axes = [axes]
    N = col(rows, "N", int)
    for ax, panel in zip(axes, panels):
        lower = col(rows, panel["lower"])
        upper = col(rows, panel["upper"])
        truth_key = panel.get("truth")
        if truth_key is not None:
            truth = float(rows[0][truth_key])
            ax.axhline(truth, color=LINE_TRUTH, linewidth=1.1, linestyle="-")
        plot_band(ax, N, lower, upper, color)
        # Optional sensitivity outlines on additional scenario columns
        for extra in panel.get("extras", []):
            lo = col(rows, extra["lower"])
            up = col(rows, extra["upper"])
            ax.plot(N, lo, color=color, linewidth=1.0, linestyle="--", alpha=0.7)
            ax.plot(N, up, color=color, linewidth=1.0, linestyle="--", alpha=0.7)
        if panel.get("ylog"):
            ax.set_yscale("log")
        # These panels are reduced from 20 inches to the 12.2 cm LNCS block.
        # Thirty-point source text remains about 7 points in the paper.
        ax.set_title(panel["title"], fontsize=30, pad=12)
        style_logx(ax)
        ax.xaxis.set_major_locator(FixedLocator([100, 10_000, 1_000_000]))
        ax.yaxis.set_major_locator(MaxNLocator(nbins=3))
        ax.tick_params(axis="both", labelsize=28, pad=5)
        if panel.get("scientific"):
            ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0), useMathText=True)
            ax.yaxis.get_offset_text().set_fontsize(26)
    fig.supxlabel(r"Observed cap $N$", fontsize=30)
    for ext in ("pdf", "png"):
        fig.savefig(ROOT / f"{out_stem}.{ext}", dpi=220, bbox_inches="tight")
    plt.close(fig)


def bitcoin_capping():
    rows = read_csv(DATA / "bitcoin_top1m_capping_convergence_summary.csv")
    panels = [
        {"title": r"$\mathrm{CR}_{10^4}$",
         "ylabel": "value",
         "lower": "cr_lower", "upper": "cr_upper", "truth": "cr_exact"},
        {"title": r"$\mathrm{NC}_{1/2}$",
         "ylabel": "value",
         "lower": "nc_lower", "upper": "nc_upper", "truth": "nc_exact"},
        {"title": r"$\mathrm{HHI}=S_2$",
         "ylabel": "value",
         "scientific": True,
         "lower": "hhi_lower", "upper": "hhi_upper", "truth": None},
        {"title": "Gini",
         "ylabel": "value",
         "lower": "gini_lower_count_aware",
         "upper": "gini_upper_count_aware"},
    ]
    make_capping_figure(
        rows, BAND_BTC, panels,
        "figure_bitcoin_top1m_capping_convergence",
        figsize=(20, 4.8),
    )

# ---------------------------------------------------------------------------
# Attribution figure (1x3 metrics with shaded bands, Merge/Shift)
# ---------------------------------------------------------------------------

def water_fill_drain_top(x_desc: np.ndarray, alpha: float) -> np.ndarray:
    """HD(x, alpha) for descending-sorted x: cap top entries to remove alpha mass."""
    if alpha <= 0.0:
        return x_desc.copy()
    if alpha >= 1.0:
        return np.zeros_like(x_desc)
    lo, hi = 0.0, float(x_desc[0])
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        drained = float(np.sum(np.maximum(x_desc - mid, 0.0)))
        if drained > alpha:
            lo = mid
        else:
            hi = mid
    L = 0.5 * (lo + hi)
    return np.minimum(x_desc, L)


def cr_of(x_desc: np.ndarray, k: int) -> float:
    return float(np.sum(x_desc[:k]))


def nc_of(x_desc: np.ndarray, tau: float) -> float:
    prefix = np.cumsum(x_desc)
    idx = int(np.searchsorted(prefix, tau, side="left"))
    if idx >= prefix.size:
        return float("inf")
    return float(idx + 1)


def merge_shift_bands(x_desc: np.ndarray, alphas: np.ndarray, k: int, tau: float):
    """Return Merge and Shift bands for CR_k, NC_tau, HHI as functions of alpha.

    HHI uses the Shift upper endpoint = drain_to_largest
    (only if alpha <= 1 - x_1) and the Shift lower endpoint = HHI of the
    LevelCap residual.
    """
    cr_raw = cr_of(x_desc, k)
    nc_raw = nc_of(x_desc, tau)
    hhi_raw = float(np.sum(x_desc ** 2))
    prefix = np.cumsum(x_desc)

    n = alphas.size
    cr_merge_lo, cr_merge_hi = np.full(n, cr_raw), np.empty(n)
    cr_shift_lo, cr_shift_hi = np.empty(n), np.empty(n)

    nc_merge_lo, nc_merge_hi = np.empty(n), np.full(n, nc_raw)
    nc_shift_lo, nc_shift_hi = np.empty(n), np.empty(n)

    hhi_merge_lo, hhi_merge_hi = np.full(n, hhi_raw), np.empty(n)
    hhi_shift_lo, hhi_shift_hi = np.empty(n), np.empty(n)

    x1 = float(x_desc[0])

    for i, a in enumerate(alphas):
        a = float(a)
        # Merge endpoints
        cr_merge_hi[i] = min(1.0, cr_raw + a)
        # Merge lower NC: min k such that CR_k(x) + a >= tau
        nc_merge_lo[i] = float(np.searchsorted(prefix, max(0.0, tau - a),
                                           side="left") + 1)

        # Drain top a to get HD(x, a)
        drained = water_fill_drain_top(x_desc, a)
        prefix_drain = np.cumsum(drained)

        # Shift endpoints
        cr_shift_hi[i] = min(1.0, cr_raw + a)
        cr_shift_lo[i] = float(prefix_drain[k - 1]) if k <= drained.size else float(prefix_drain[-1])
        nc_shift_lo[i] = nc_merge_lo[i]  # same formula
        if float(prefix_drain[-1]) >= tau:
            nc_shift_hi[i] = float(np.searchsorted(prefix_drain, tau,
                                               side="left") + 1)
        else:
            nc_shift_hi[i] = np.nan  # unreachable, threshold above remaining mass
        # HHI Shift exact upper: (x1 + a_eff)^2 + S_2(SD(tail, a_eff))
        a_eff = min(a, 1.0 - x1)
        # SD(tail, a_eff): remove a_eff mass from smallest-first of tail
        tail = x_desc[1:]
        tail_asc = tail[::-1]
        tail_prefix_asc = np.concatenate([[0.0], np.cumsum(tail_asc)])
        if tail_asc.size == 0 or a_eff <= 0.0:
            sd_s2 = float(np.sum(tail ** 2))
        else:
            # remove a_eff from ascending; how many full entries can we remove?
            full = int(np.searchsorted(tail_prefix_asc[1:], a_eff,
                                       side="right"))
            sd_s2 = float(np.sum(tail ** 2))
            if full > 0:
                sd_s2 -= float(np.sum(tail_asc[:full] ** 2))
            if full < tail_asc.size:
                already = float(tail_prefix_asc[full])
                partial = a_eff - already
                if partial > 0:
                    orig = float(tail_asc[full])
                    sd_s2 -= orig * orig - (orig - partial) ** 2
        hhi_shift_hi[i] = (x1 + a_eff) ** 2 + sd_s2
        # Whole-label Merge is contained in Shift at the same moved mass.
        # This upper bound is safe for Merge, sharp for Shift.
        hhi_merge_hi[i] = hhi_shift_hi[i]
        # HHI Shift lower: HHI of LevelCap(x, a).
        hhi_shift_lo[i] = float(np.sum(drained ** 2))

    return {
        "cr_raw": cr_raw, "nc_raw": nc_raw, "hhi_raw": hhi_raw,
        "cr_merge": (cr_merge_lo, cr_merge_hi),
        "cr_shift": (cr_shift_lo, cr_shift_hi),
        "nc_merge": (nc_merge_lo, nc_merge_hi),
        "nc_shift": (nc_shift_lo, nc_shift_hi),
        "hhi_merge": (hhi_merge_lo, hhi_merge_hi),
        "hhi_shift": (hhi_shift_lo, hhi_shift_hi),
    }


def shade_merge_shift(ax, alphas, raw_value, merge_band, shift_band):
    """Plot Merge and Shift as two complete, overlaid regions.

    Uses the same visual grammar as the family-parameter sensitivity figure:
    Merge is red with upward diagonal hatching; Shift is blue with downward
    diagonal hatching and dotted boundaries.
    """
    lo_merge, hi_merge = merge_band
    lo_shift, hi_shift = shift_band

    ax.fill_between(
        alphas, lo_shift, hi_shift,
        facecolor=FILL_SHIFT, hatch=HATCH_SHIFT, edgecolor=COLOR_SHIFT,
        linewidth=0.55, zorder=1,
    )
    ax.fill_between(
        alphas, lo_merge, hi_merge,
        facecolor=FILL_MERGE, hatch=HATCH_MERGE, edgecolor=COLOR_MERGE,
        linewidth=0.55, zorder=2,
    )

    # Draw the solid Merge edge first and the dotted Shift edge over it.  Thus
    # coincident endpoints (notably the CR upper edge) still show both models.
    ax.plot(alphas, hi_merge, color=COLOR_MERGE, linewidth=1.05, zorder=5)
    ax.plot(alphas, lo_merge, color=COLOR_MERGE, linewidth=1.05, zorder=5)
    ax.plot(alphas, hi_shift, color=COLOR_SHIFT, linewidth=1.25,
            linestyle=(0, (1, 1.45)), zorder=6)
    ax.plot(alphas, lo_shift, color=COLOR_SHIFT, linewidth=1.25,
            linestyle=(0, (1, 1.45)), zorder=6)

    for value in np.unique(np.atleast_1d(raw_value)):
        ax.axhline(value, color=LINE_TRUTH, linewidth=1.05, linestyle="-",
                   zorder=7)


def attribution_figure():
    # Preserve the dated-supply denominator and include the unobserved tail.
    x, tail_mass = load_bitcoin_observation()

    alphas = np.unique(np.concatenate((np.linspace(0.0, 1.0 / 3.0, 70), [0.10, 0.30])))
    bands = joint_metric_bands(x, tail_mass, alphas, k=10_000, tau=0.5)

    fig, axes = plt.subplots(
        1,
        3,
        figsize=(LNCS_TEXT_WIDTH_IN, 2.42),
        constrained_layout=False,
    )
    ax_cr, ax_nc, ax_hhi = axes

    shade_merge_shift(ax_cr, alphas, bands["cr_cap"], bands["cr_merge"],
                      bands["cr_shift"])
    ax_cr.set_title(r"$\mathrm{CR}_{10^4}$", fontsize=9.0)
    ax_cr.set_ylabel("Value", fontsize=8.5, labelpad=2.0)
    ax_cr.set_ylim(0.0, 1.02)

    shade_merge_shift(ax_nc, alphas, bands["nc_cap"], bands["nc_merge"],
                      bands["nc_shift"])
    ax_nc.set_title(r"$\mathrm{NC}_{1/2}$", fontsize=9.0)
    ax_nc.set_yscale("log")

    shade_merge_shift(ax_hhi, alphas, bands["hhi_cap"],
                      bands["hhi_merge"], bands["hhi_shift"])
    ax_hhi.set_title(r"$\mathrm{HHI}$", fontsize=9.0)
    ax_hhi.set_yscale("log")

    for ax in axes:
        ax.tick_params(axis="both", which="major", length=2.7, width=0.6,
                       labelsize=8.0, pad=1.8)
        ax.tick_params(axis="both", which="minor", length=1.7, width=0.5)
        for spine in ax.spines.values():
            spine.set_linewidth(0.65)
        ax.set_xlim(0.0, float(alphas.max()))
        ax.axvline(tail_mass, color="0.35", linestyle="--", linewidth=0.8, zorder=8)
        ax.text(tail_mass+0.004, 0.98, r"$T_N$", transform=ax.get_xaxis_transform(),
                va="top", fontsize=7, color="0.25")

    # Reserve space at the bottom for the shared x label and model legend.
    fig.subplots_adjust(left=0.095, right=0.995, top=0.92, bottom=0.34,
                        wspace=0.46)
    fig.text(0.52, 0.205,
             r"Moved-mass budget $\rho$",
             ha="center", va="center", fontsize=8.5)

    legend_handles = [
        Patch(facecolor=FILL_MERGE, edgecolor=COLOR_MERGE,
              hatch=HATCH_MERGE, label="Merge"),
        Patch(facecolor=FILL_SHIFT, edgecolor=COLOR_SHIFT,
              hatch=HATCH_SHIFT, label="Shift (sharp)"),
        Line2D([0], [0], color=LINE_TRUTH, linewidth=1.05,
               label="Capping only"),
    ]
    fig.legend(handles=legend_handles, loc="lower center",
               bbox_to_anchor=(0.5, 0.025), ncol=len(legend_handles),
               frameon=False, columnspacing=1.5, fontsize=8.0,
               handlelength=1.6, handletextpad=0.55)

    for ext in ("pdf", "png"):
        fig.savefig(ROOT / f"figure_attribution_two_models.{ext}",
                    dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Family-parameter sensitivity figure
# ---------------------------------------------------------------------------

def load_bitcoin_shares() -> np.ndarray:
    path = DATA / "top_mill_adresses.json"
    balances = []
    with open_text(path) as f:
        for line in f:
            obj = json.loads(line)
            balances.append(float(obj["balance_btc"]))
    arr = np.asarray(balances, dtype=np.float64)
    arr.sort()
    arr = arr[::-1]
    return arr / arr.sum()


def power_sum_band_merge(x: np.ndarray, p: float, rho: float) -> tuple[float, float]:
    """Safe Merge band: baseline lower and Shift upper at equal moved mass."""
    sp = float(np.sum(x ** p))
    amount = min(rho, 1.0 - float(x[0]))
    upper = (float(x[0]) + amount)**p + float(np.sum(small_drain_tail(x[1:], amount)**p))
    return sp, upper


def small_drain_tail(x_desc: np.ndarray, alpha: float) -> np.ndarray:
    """SD(x, alpha) for descending-sorted x: drain from the smallest entries."""
    if alpha <= 0.0:
        return x_desc.copy()
    out = x_desc.copy()
    remaining = float(alpha)
    for i in range(out.size - 1, -1, -1):
        if remaining <= 0.0:
            break
        take = min(float(out[i]), remaining)
        out[i] -= take
        remaining -= take
    return out


def power_sum_band_shift(
    x: np.ndarray,
    p: float,
    alpha: float,
    hd: np.ndarray | None = None,
    sd_tail: np.ndarray | None = None,
) -> tuple[float, float]:
    """Exact Shift interval for S_p from Theorem 14."""
    a = min(float(alpha), 1.0 - float(x[0]))
    hd_x = hd if hd is not None else water_fill_drain_top(x, alpha)
    sd_y = sd_tail if sd_tail is not None else small_drain_tail(x[1:], a)
    lower = float(np.sum(hd_x ** p))
    upper = float((x[0] + a) ** p + np.sum(sd_y ** p))
    return lower, upper


def hill_from_power_band(s_lower: float, s_upper: float, q: float) -> tuple[float, float]:
    """Map an S_q interval to a Hill_q interval for q > 1."""
    assert q > 1.0
    exponent = 1.0 / (1.0 - q)
    return s_upper ** exponent, s_lower ** exponent


def hill_band_q_above_one_merge(x: np.ndarray, q: float, rho: float) -> tuple[float, float]:
    """Hill_q band for q > 1 derived from the Merge budget on S_q.

    For q > 1, Hill_q(z) = S_q(z)^{1/(1-q)} is monotone decreasing in S_q, so
    the upper Hill bound uses the lower S_q endpoint and vice versa.
    """
    sq_lower, sq_upper = power_sum_band_merge(x, q, rho)
    return hill_from_power_band(sq_lower, sq_upper, q)


def raw_hill(x: np.ndarray, q: float) -> float:
    if q == 0.0:
        return float(np.count_nonzero(x))
    if abs(q - 1.0) < 1e-12:
        mask = x > 0
        return float(np.exp(-np.sum(x[mask] * np.log(x[mask]))))
    return float(np.sum(x ** q) ** (1.0 / (1.0 - q)))


def plot_family_bands(ax, t, raw, a_lower, a_upper, b_lower, b_upper, raw_upper=None):
    """Plot Merge and Shift family-parameter bands on one axis."""
    ax.fill_between(
        t, b_lower, b_upper,
        facecolor=FILL_SHIFT, hatch=HATCH_SHIFT, edgecolor=COLOR_SHIFT,
        linewidth=0.55, zorder=1,
    )
    ax.fill_between(
        t, a_lower, a_upper,
        facecolor=FILL_MERGE, hatch=HATCH_MERGE, edgecolor=COLOR_MERGE,
        linewidth=0.55, zorder=2,
    )
    ax.plot(t, a_lower, color=COLOR_MERGE, linewidth=1.0, zorder=5)
    ax.plot(t, a_upper, color=COLOR_MERGE, linewidth=1.0, zorder=5)
    ax.plot(t, b_lower, color=COLOR_SHIFT, linewidth=1.2,
            linestyle=(0, (1, 1.45)), zorder=6)
    ax.plot(t, b_upper, color=COLOR_SHIFT, linewidth=1.2,
            linestyle=(0, (1, 1.45)), zorder=6)

    ax.plot(t, raw, color=LINE_TRUTH, linewidth=1.05, zorder=7)
    if raw_upper is not None:
        ax.plot(t, raw_upper, color=LINE_TRUTH, linewidth=1.05, zorder=7)


def family_sensitivity_figure(budget: float = 0.10):
    x, tail_mass = load_bitcoin_observation()
    ps = np.linspace(1.1, 5.0, 50)
    qs = np.linspace(1.25, 5.0, 50)

    alpha = float(budget)
    joint_shift = JointShift(x, tail_mass, alpha)

    sp_raw = np.empty_like(ps)
    sp_cap_upper = np.empty_like(ps)
    sp_merge_lower = np.empty_like(ps)
    sp_merge_upper = np.empty_like(ps)
    sp_shift_lower = np.empty_like(ps)
    sp_shift_upper = np.empty_like(ps)
    for i, p in enumerate(ps):
        p_float = float(p)
        sp_raw[i], sp_cap_upper[i] = capping_power_interval(x, tail_mass, p_float)
        sp_merge_lower[i] = sp_raw[i]
        sp_shift_lower[i], sp_shift_upper[i] = joint_shift.power_interval(p_float)
        sp_merge_upper[i] = sp_shift_upper[i]

    hill_raw = np.empty_like(qs)
    hill_cap_upper = np.empty_like(qs)
    hill_merge_lower = np.empty_like(qs)
    hill_merge_upper = np.empty_like(qs)
    hill_shift_lower = np.empty_like(qs)
    hill_shift_upper = np.empty_like(qs)
    for i, q in enumerate(qs):
        q_float = float(q)
        sq_lower, sq_upper = capping_power_interval(x, tail_mass, q_float)
        hill_raw[i], hill_cap_upper[i] = hill_from_power_band(sq_lower, sq_upper, q_float)
        sq_shift_lower, sq_shift_upper = joint_shift.power_interval(q_float)
        sq_merge_lower, sq_merge_upper = sq_lower, sq_shift_upper
        hill_merge_lower[i], hill_merge_upper[i] = hill_from_power_band(
            sq_merge_lower, sq_merge_upper, q_float
        )
        hill_shift_lower[i], hill_shift_upper[i] = hill_from_power_band(
            sq_shift_lower, sq_shift_upper, q_float
        )

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(LNCS_TEXT_WIDTH_IN, 2.72),
        constrained_layout=False,
    )
    ax_sp, ax_hill = axes

    plot_family_bands(ax_sp, ps, sp_raw, sp_merge_lower, sp_merge_upper,
                      sp_shift_lower, sp_shift_upper, raw_upper=sp_cap_upper)
    ax_sp.axvline(2.0, color="#777777", linewidth=0.9, linestyle=":")
    ax_sp.set_title(rf"Power sums $S_p$ ($\rho={budget:g}$)", fontsize=9.0)
    ax_sp.set_xlabel(r"Family parameter $p$", fontsize=8.5, labelpad=2.0)
    ax_sp.set_ylabel("Value", fontsize=8.5, labelpad=2.0)
    ax_sp.set_yscale("log")
    # "HHI" marker near the top of the axvline (above the band/curves)
    ax_sp.annotate("HHI", xy=(2.0, 1.0), xycoords=("data", "axes fraction"),
                   xytext=(4, -2), textcoords="offset points",
                   color="#555", va="top", ha="left", fontsize=8.0)

    plot_family_bands(ax_hill, qs, hill_raw, hill_merge_lower, hill_merge_upper,
                      hill_shift_lower, hill_shift_upper, raw_upper=hill_cap_upper)
    ax_hill.axvline(2.0, color="#777777", linewidth=0.9, linestyle=":")
    ax_hill.set_title(rf"Hill numbers $\mathrm{{N}}_q$ ($\rho={budget:g}$)",
                      fontsize=9.0)
    ax_hill.set_xlabel(r"Family parameter $q$", fontsize=8.5, labelpad=2.0)
    ax_hill.set_ylabel("Value", fontsize=8.5, labelpad=2.0)
    ax_hill.set_yscale("log")
    ax_hill.annotate(r"$\mathrm{N}_2$",
                     xy=(2.0, 1.0), xycoords=("data", "axes fraction"),
                     xytext=(4, -2), textcoords="offset points",
                     color="#555", va="top", ha="left", fontsize=8.0)

    legend_handles = [
        Patch(facecolor=FILL_MERGE, edgecolor=COLOR_MERGE,
              hatch=HATCH_MERGE, label="Merge (conservative)"),
        Patch(facecolor=FILL_SHIFT, edgecolor=COLOR_SHIFT,
              hatch=HATCH_SHIFT, label="Shift (sharp)"),
        Line2D([0], [0], color=LINE_TRUTH, linewidth=1.05,
               label="Capping only"),
    ]
    for ax in axes:
        ax.tick_params(axis="both", which="major", length=2.7, width=0.6,
                       labelsize=8.0, pad=1.8)
        ax.tick_params(axis="both", which="minor", length=1.7, width=0.5)
        for spine in ax.spines.values():
            spine.set_linewidth(0.65)

    fig.subplots_adjust(left=0.105, right=0.995, top=0.91, bottom=0.27,
                        wspace=0.45)
    fig.legend(handles=legend_handles, loc="lower center",
               bbox_to_anchor=(0.5, 0.015), ncol=len(legend_handles),
               frameon=False, columnspacing=1.5, fontsize=8.0,
               handlelength=1.6, handletextpad=0.55)

    for ext in ("pdf", "png"):
        fig.savefig(ROOT / f"figure_family_parameter_sensitivity.{ext}",
                    dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def main():
    bitcoin_capping()
    attribution_figure()
    family_sensitivity_figure(budget=0.10)
    runpy.run_path(str(ROOT / "analysis-code" / "plot_eth_merge_shift_calibration.py"), run_name="__main__")
    print("regenerated 4 paper figures")


if __name__ == "__main__":
    main()
