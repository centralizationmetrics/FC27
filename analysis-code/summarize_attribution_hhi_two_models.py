#!/usr/bin/env python3

import csv
import gzip
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
BTC_INPUT = ROOT / "data" / "top_mill_adresses.json"
OUTPUT_CSV = ROOT / "data" / "attribution_hhi_two_models_summary.csv"

ALPHA_MAX = 1.0 / 3.0
GRID_SIZE = 101
TABLE_BUDGETS = (0.10, 0.23)


def load_bitcoin_shares(path: Path) -> np.ndarray:
    balances = []
    with open_text(path) as f:
        for line in f:
            row = json.loads(line)
            balances.append(float(row["balance_btc"]))
    return normalized_desc(np.array(balances, dtype=np.float64))


def open_text(path: Path):
    if path.exists():
        return path.open()
    gz_path = path.with_suffix(path.suffix + ".gz")
    if gz_path.exists():
        return gzip.open(gz_path, "rt")
    return path.open()


def normalized_desc(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    values = values[values > 0.0]
    values.sort()
    values = values[::-1]
    return values / values.sum()


def high_drain_s2(
    x: np.ndarray,
    x_asc: np.ndarray,
    prefix: np.ndarray,
    prefix_sq: np.ndarray,
    total_s2: float,
    amount: float,
) -> float:
    amount = min(max(float(amount), 0.0), 1.0)
    if amount <= 0.0:
        return float(np.dot(x, x))
    if amount >= 1.0:
        return 0.0

    low = 0.0
    high = float(x[0])
    for _ in range(80):
        level = 0.5 * (low + high)
        first_above = int(np.searchsorted(x_asc, level, side="right"))
        count = x.size - first_above
        drained = float(prefix[count] - count * level)
        if drained > amount:
            low = level
        else:
            high = level
    first_above = int(np.searchsorted(x_asc, high, side="right"))
    count = x.size - first_above
    return float(count * high * high + (total_s2 - prefix_sq[count]))


def small_drain_s2(y_asc: np.ndarray, prefix_asc: np.ndarray, prefix_sq_asc: np.ndarray, total_s2: float, amount: float) -> float:
    amount = max(float(amount), 0.0)
    if amount <= 0.0:
        return total_s2
    if amount >= float(prefix_asc[-1]):
        return 0.0

    full = int(np.searchsorted(prefix_asc[1:], amount, side="right"))
    removed_s2 = float(prefix_sq_asc[full])
    residual_s2 = total_s2 - removed_s2
    if full < y_asc.size:
        already_removed = float(prefix_asc[full])
        partial = amount - already_removed
        if partial > 0.0:
            original = float(y_asc[full])
            residual_s2 -= original * original - (original - partial) ** 2
    return float(residual_s2)


def model_rows(dataset: str, label: str, x: np.ndarray, budgets: np.ndarray) -> list[dict[str, float | str | int]]:
    hhi = float(np.dot(x, x))
    x1 = float(x[0])
    tail = x[1:]
    x_asc = x[::-1]
    prefix = np.zeros(x.size + 1, dtype=np.float64)
    prefix[1:] = np.cumsum(x)
    prefix_sq = np.zeros(x.size + 1, dtype=np.float64)
    prefix_sq[1:] = np.cumsum(x * x)
    tail_asc = tail[::-1]
    tail_prefix_asc = np.zeros(tail.size + 1, dtype=np.float64)
    tail_prefix_asc[1:] = np.cumsum(tail_asc)
    tail_prefix_sq_asc = np.zeros(tail.size + 1, dtype=np.float64)
    tail_prefix_sq_asc[1:] = np.cumsum(tail_asc * tail_asc)
    tail_s2 = float(np.dot(tail, tail))
    rows = []
    for budget in budgets:
        transfer = min(float(budget), 1.0 - x1)
        shift_upper = (x1 + transfer) ** 2 + small_drain_s2(
            tail_asc,
            tail_prefix_asc,
            tail_prefix_sq_asc,
            tail_s2,
            transfer,
        )
        shift_lower = high_drain_s2(x, x_asc, prefix, prefix_sq, hhi, float(budget))
        # Independent summation orders can differ by a few ULPs. Both models
        # contain the unchanged vector, and zero budget fixes it exactly.
        shift_upper = hhi if budget == 0 else max(hhi, shift_upper)
        shift_lower = hhi if budget == 0 else min(hhi, max(0.0, shift_lower))
        rows.append(
            {
                "dataset": dataset,
                "dataset_label": label,
                "budget": float(budget),
                "support_size": int(x.size),
                "largest_share": x1,
                "hhi_raw": hhi,
                "merge_lower": hhi,
                "merge_upper_safe": shift_upper,
                "shift_lower_inf": shift_lower,
                "shift_upper_exact": shift_upper,
                "shift_upper_safe": min(1.0, hhi + 2.0 * transfer * x1 + transfer * transfer),
            }
        )
    return rows


def write_rows(rows: list[dict[str, float | str | int]]) -> None:
    fieldnames = list(rows[0].keys())
    with OUTPUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    budgets = np.unique(
        np.concatenate(
            [
                np.linspace(0.0, ALPHA_MAX, GRID_SIZE),
                np.asarray(TABLE_BUDGETS, dtype=np.float64),
            ]
        )
    )
    rows = []
    rows.extend(model_rows("bitcoin_top1m", "Bitcoin top-1M addresses", load_bitcoin_shares(BTC_INPUT), budgets))
    write_rows(rows)
    print(f"summary {OUTPUT_CSV.relative_to(ROOT)}")
    row = next(r for r in rows if abs(float(r["budget"]) - 0.10) < 1e-12)
    print(
        "bitcoin_top1m",
        "support",
        row["support_size"],
        "x1",
        f"{row['largest_share']:.8g}",
        "hhi",
        f"{row['hhi_raw']:.8g}",
        "Merge_safe_upper_0.1",
        f"{row['merge_upper_safe']:.8g}",
        "Shift_interval_0.1",
        f"[{row['shift_lower_inf']:.8g},{row['shift_upper_exact']:.8g}]",
    )


if __name__ == "__main__":
    main()
