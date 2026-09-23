#!/usr/bin/env python3

import csv
import json
from pathlib import Path

import numpy as np

from summarize_attribution_hhi_two_models import model_rows, open_text


ROOT = Path(__file__).resolve().parents[1]
INPUT_JSONL = ROOT / "data" / "top_mill_adresses.json"
OUTPUT_CSV = ROOT / "data" / "bitcoin_top1m_alpha_variation_summary.csv"

CR_K = 10_000
NC_TAU = 0.5
ALPHA_MAX = 1.0 / 3.0
GRID_SIZE = 101
SNAPSHOT_DATE = "2025-09-23"


def load_shares(path: Path) -> np.ndarray:
    balances = []
    with open_text(path) as f:
        for line in f:
            row = json.loads(line)
            balances.append(float(row["balance_btc"]))
    balances = np.array(balances, dtype=np.float64)
    return balances / balances.sum()


def gini_desc(z: np.ndarray) -> float:
    n = z.size
    coeff = (n + 1) - 2 * np.arange(1, n + 1)
    return float(np.dot(coeff, z) / n)


def segment_weighted_sum(prefix_x: np.ndarray, prefix_jx: np.ndarray, left: int, right: int, a: float) -> float:
    if right < left:
        return 0.0
    sum_x = prefix_x[right] - prefix_x[left - 1]
    sum_jx = prefix_jx[right] - prefix_jx[left - 1]
    return a * sum_x - 2.0 * sum_jx


def gini_tail_collapse_curve(x: np.ndarray, alphas: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = x.size
    prefix_x = np.zeros(n + 1, dtype=np.float64)
    prefix_x[1:] = np.cumsum(x)
    prefix_jx = np.zeros(n + 1, dtype=np.float64)
    prefix_jx[1:] = np.cumsum(np.arange(1, n + 1, dtype=np.float64) * x)
    tail_cum = np.cumsum(x[::-1])
    tail_cost = tail_cum - x[::-1]

    attained_mass = np.zeros_like(alphas)
    gini_vals = np.zeros_like(alphas)
    base = gini_desc(x)
    gini_vals[0] = base

    for idx, alpha in enumerate(alphas[1:], start=1):
        k = int(np.searchsorted(tail_cost, alpha + 8*np.spacing(alpha), side="right"))
        if k == 0:
            attained_mass[idx] = 0.0
            gini_vals[idx] = base
            continue

        s = float(tail_cum[k - 1])
        retained = n - k
        m = n - k + 1
        p = int(np.searchsorted(-x[:retained], -s, side="left")) + 1

        numerator = 0.0
        numerator += segment_weighted_sum(prefix_x, prefix_jx, 1, p - 1, m + 1)
        numerator += (m + 1 - 2 * p) * s
        numerator += segment_weighted_sum(prefix_x, prefix_jx, p, retained, m - 1)

        attained_mass[idx] = tail_cost[k - 1]
        gini_vals[idx] = float(numerator / m)

    return attained_mass, gini_vals


def gini_head_collapse_curve(x: np.ndarray, alphas: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = x.size
    prefix_x = np.zeros(n + 1, dtype=np.float64)
    prefix_x[1:] = np.cumsum(x)
    prefix_jx = np.zeros(n + 1, dtype=np.float64)
    prefix_jx[1:] = np.cumsum(np.arange(1, n + 1, dtype=np.float64) * x)

    attained_mass = np.zeros_like(alphas)
    gini_vals = np.zeros_like(alphas)
    base = gini_desc(x)
    gini_vals[0] = base

    total_x = float(prefix_x[-1])
    total_jx = float(prefix_jx[-1])
    head_cost = prefix_x[1:] - x[0]

    for idx, alpha in enumerate(alphas[1:], start=1):
        k = int(np.searchsorted(head_cost, alpha + 8*np.spacing(alpha), side="right"))
        if k == 0:
            attained_mass[idx] = 0.0
            gini_vals[idx] = base
            continue

        s = float(prefix_x[k])
        m = n - k + 1
        sum_x = total_x - prefix_x[k]
        sum_jx = total_jx - prefix_jx[k]
        numerator = (m - 1.0) * s + (n + k) * sum_x - 2.0 * sum_jx

        attained_mass[idx] = head_cost[k - 1]
        gini_vals[idx] = float(numerator / m)

    return attained_mass, gini_vals


def compute_rows(x: np.ndarray) -> list[dict[str, float]]:
    prefix = np.cumsum(x)
    hhi_true = float(np.dot(x, x))
    hill2_true = float(1.0 / hhi_true)
    cr_true = float(prefix[CR_K - 1])
    nc_true = int(np.searchsorted(prefix, NC_TAU, side="left") + 1)
    gini_true = gini_desc(x)

    alphas = np.linspace(0.0, ALPHA_MAX, GRID_SIZE)
    attained_tail_mass, gini_tail = gini_tail_collapse_curve(x, alphas)
    attained_head_mass, gini_head = gini_head_collapse_curve(x, alphas)
    power_bounds = model_rows("bitcoin_top1m", "Bitcoin top-1M normalized labels", x, alphas)
    rows = []
    for i, alpha in enumerate(alphas):
        rows.append(
            {
                "alpha": float(alpha),
                "snapshot_date": SNAPSHOT_DATE,
                "support_size": int(x.size),
                "cr_lower": cr_true,
                "cr_upper": min(1.0, cr_true + alpha),
                "cr_true": cr_true,
                "nc_lower": int(np.searchsorted(prefix, max(0.0, NC_TAU - alpha), side="left") + 1),
                "nc_upper": nc_true,
                "nc_true": nc_true,
                "hhi_lower": hhi_true,
                "hhi_upper": power_bounds[i]["merge_upper_safe"],
                "hhi_true": hhi_true,
                "hill2_lower": 1.0 / power_bounds[i]["merge_upper_safe"],
                "hill2_upper": hill2_true,
                "hill2_true": hill2_true,
                "gini_true": gini_true,
                "gini_tail_collapse": float(gini_tail[i]),
                "gini_tail_collapse_mass": float(attained_tail_mass[i]),
                "gini_head_collapse": float(gini_head[i]),
                "gini_head_collapse_mass": float(attained_head_mass[i]),
            }
        )
    return rows


def write_summary(rows: list[dict[str, float]]) -> None:
    fieldnames = list(rows[0].keys())
    with OUTPUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    x = load_shares(INPUT_JSONL)
    rows = compute_rows(x)
    write_summary(rows)
    print(f"support_size {x.size}")
    print(f"snapshot_date {SNAPSHOT_DATE}")
    print(f"summary {OUTPUT_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
