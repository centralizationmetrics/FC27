"""Joint capping/attribution calculations used by the Bitcoin paper figures.

Shares use the full stated resource denominator. Omitted shares are positive,
at most the last observed share, and have no count bound. No omitted vector
needs to be materialized, even when its packed completion has millions of rows.
"""

import math

import numpy as np

from summarize_bitcoin_top1m_capping_convergence import (
    EXPECTED_TOP1M_SATOSHIS, INPUT_JSONL, TOTAL_SUPPLY_SATOSHIS, load_balances,
)


def load_bitcoin_observation():
    balances = load_balances(INPUT_JSONL)
    if balances.size != 1_000_000 or np.any(balances <= 0):
        raise ValueError("expected one million positive Bitcoin balance records")
    observed = int(balances.sum(dtype=np.int64))
    if observed != EXPECTED_TOP1M_SATOSHIS:
        raise ValueError("Bitcoin balance total differs from the released input")
    balances.sort()
    head = balances[::-1].astype(np.float64) / TOTAL_SUPPLY_SATOSHIS
    tail = (TOTAL_SUPPLY_SATOSHIS - observed) / TOTAL_SUPPLY_SATOSHIS
    return head, tail


def packed_power(mass, cap, p):
    count = math.floor(mass / cap)
    remainder = mass - count * cap
    return count * cap**p + max(0.0, remainder)**p


def capping_power_interval(head, tail, p):
    lower = float(np.sum(head**p))
    return lower, lower + packed_power(tail, float(head[-1]), p)


def level_cap(head, amount):
    """LevelCap using sorted-prefix searches rather than repeated full scans."""
    if amount <= 0:
        return head.copy()
    if amount >= float(np.sum(head)):
        return np.zeros_like(head)
    prefix = np.concatenate(([0.0], np.cumsum(head)))
    lo, hi = 0.0, float(head[0])
    for _ in range(80):
        level = (lo + hi) / 2
        count = head.size - int(np.searchsorted(head[::-1], level, side="right"))
        if prefix[count] - count * level > amount:
            lo = level
        else:
            hi = level
    return np.minimum(head, (lo + hi) / 2)


def tail_trim(head, amount):
    if amount <= 0 or head.size == 0:
        return head.copy()
    ascending_prefix = np.concatenate(([0.0], np.cumsum(head[::-1])))
    full = int(np.searchsorted(ascending_prefix[1:], amount, side="right"))
    if full == head.size:
        return np.empty(0)
    residual = head[:head.size - full].copy()
    residual[-1] -= amount - ascending_prefix[full]
    return residual


class JointShift:
    """Reuse the joint Shift endpoint constructions across power orders p>1."""

    def __init__(self, head, tail, alpha):
        self.lower_head = level_cap(head, min(alpha, float(np.sum(head))))
        moved = min(alpha, 1.0 - float(head[0]))
        self.largest = float(head[0]) + moved
        # TailTrim drains the packed omitted shares before any observed share.
        self.upper_head_tail = tail_trim(head[1:], max(0.0, moved - tail))
        self.upper_omitted_mass = max(0.0, tail - moved)
        self.cap = float(head[-1])

    def power_interval(self, p):
        lower = float(np.sum(self.lower_head**p))
        upper = (self.largest**p + float(np.sum(self.upper_head_tail**p))
                 + packed_power(self.upper_omitted_mass, self.cap, p))
        return lower, upper


def joint_metric_bands(head, tail, budgets, k, tau):
    """CR/NC/HHI bands in the visible-prefix regime used by Figure 2.

    Requires k<=N and tau strictly below the residual observed mass at every
    budget. Thus the relevant threshold crossings remain in the visible head;
    arbitrarily fine omitted shares attain the same head-metric limits.
    Merge bands are safe; Shift bands and capping endpoints are sharp.
    """
    if not 1 <= k <= head.size or not 0 < tau < float(np.sum(head)) - max(budgets):
        raise ValueError("joint head metrics require a sufficient visible prefix")
    prefix = np.cumsum(head)
    cr = float(np.sum(head[:k]))
    nc = float(np.searchsorted(prefix, tau, side="left") + 1)
    hhi_cap = capping_power_interval(head, tail, 2.0)
    bands = {f"{metric}_{model}": ([], [])
             for metric in ("cr", "nc", "hhi") for model in ("merge", "shift")}
    for budget in budgets:
        b = float(budget)
        shift = JointShift(head, tail, b)
        residual_prefix = np.cumsum(shift.lower_head)
        nc_lower = float(np.searchsorted(prefix, max(0.0, tau - b), side="left") + 1)
        hhi_shift = shift.power_interval(2.0)
        endpoints = {
            "cr_merge": (cr, min(1.0, cr + b)),
            "cr_shift": (float(np.sum(shift.lower_head[:k])), min(1.0, cr + b)),
            "nc_merge": (nc_lower, nc),
            "nc_shift": (nc_lower, float(np.searchsorted(residual_prefix, tau, side="left") + 1)),
            "hhi_merge": (hhi_cap[0], hhi_shift[1]),
            "hhi_shift": hhi_shift,
        }
        for name, (lower, upper) in endpoints.items():
            bands[name][0].append(lower)
            bands[name][1].append(upper)
    bands = {name: tuple(np.asarray(v) for v in pair) for name, pair in bands.items()}
    bands.update(cr_cap=(cr, cr), nc_cap=(nc, nc), hhi_cap=hhi_cap)
    return bands
