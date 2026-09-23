#!/usr/bin/env python3
"""Reproduce the full-denominator Bitcoin capping x attribution report."""

import csv
from pathlib import Path

import numpy as np

from joint_capping import joint_metric_bands, load_bitcoin_observation
from summarize_bitcoin_top1m_capping_convergence import TOTAL_SUPPLY_BTC

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "bitcoin_joint_certificates_summary.csv"


def main():
    head, tail = load_bitcoin_observation()
    budgets = np.unique(np.concatenate((np.linspace(0, 1/3, 70), [0.10, 0.30])))
    bands = joint_metric_bands(head, tail, budgets, k=10_000, tau=0.5)
    rows = []
    for i, b in enumerate(budgets):
        row = dict(budget=float(b), observed_count=head.size,
                   total_supply_btc=TOTAL_SUPPLY_BTC, coverage=1-tail,
                   omitted_mass=tail, largest_share=float(head[0]),
                   omitted_share_cap=float(head[-1]))
        for metric in ("cr", "nc", "hhi"):
            row[f"{metric}_capping_lower"], row[f"{metric}_capping_upper"] = bands[f"{metric}_cap"]
            for model in ("merge", "shift"):
                for j, endpoint in enumerate(("lower", "upper")):
                    row[f"{metric}_{model}_{endpoint}"] = float(bands[f"{metric}_{model}"][j][i])
        rows.append(row)
    with OUTPUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    for row in rows:
        if row["budget"] in (0.0, 0.10, 0.30):
            print(row)


if __name__ == "__main__":
    main()
