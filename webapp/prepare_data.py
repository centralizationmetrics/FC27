#!/usr/bin/env python3
"""Build the bundled datasets for the static web app.

Reads the raw Bitcoin snapshot and, when the legacy app-only Ethereum demo
source is available, emits compact JSON files containing sorted share vectors
with dated denominators and omitted-tail metadata.
"""

import csv
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "data"

BTC_TOTAL_SUPPLY = 19_925_284.0
BTC_SNAPSHOT_DATE = "2025-09-23"
ETH_SNAPSHOT_SLOT = 13_909_376
ETH_SNAPSHOT_EPOCH = 434_668
ETH_SNAPSHOT_UTC = "2026-03-17T08:35:35Z"

TOP_K_SMALL = 10_000
TOP_K_FULL = 1_000_000


def open_text(path: Path):
    if path.exists():
        return path.open()
    gz_path = path.with_suffix(path.suffix + ".gz")
    if gz_path.exists():
        return gzip.open(gz_path, "rt")
    return path.open()


def build_btc(top_k: int, out_name: str, label: str):
    src = ROOT / "data" / "top_mill_adresses.json"
    balances = []
    full_sum = 0.0
    with open_text(src) as f:
        for i, line in enumerate(f):
            row = json.loads(line)
            b = float(row["balance_btc"])
            full_sum += b
            if i < top_k:
                balances.append(b)
    coverage_full = full_sum / BTC_TOTAL_SUPPLY
    top_k_sum = sum(balances)
    out = {
        "name": label,
        "resource": "BTC balance",
        "snapshot_date": BTC_SNAPSHOT_DATE,
        "denominator": BTC_TOTAL_SUPPLY,
        "denominator_unit": "BTC",
        "support_full_observed": 1_000_000,
        "support_top_k": top_k,
        "coverage_full_observed": coverage_full,
        "coverage_top_k": top_k_sum / BTC_TOTAL_SUPPLY,
        "omitted_tail_mass_top_k_inside_observed":
            (full_sum - top_k_sum) / BTC_TOTAL_SUPPLY,
        "omitted_tail_mass_top_k_against_supply":
            1.0 - top_k_sum / BTC_TOTAL_SUPPLY,
        "omitted_positive_count_scenarios": [30_000_000, 55_000_000, 80_000_000],
        "shares_descending": [b / BTC_TOTAL_SUPPLY for b in balances],
        "notes": (
            "Shares are dimensionless (balance / dated total supply). "
            "Omitted positive count is an external sensitivity input; "
            "the BigQuery extraction does not recover the true count."
        ),
    }
    out_path = OUT / out_name
    out_path.write_text(json.dumps(out, separators=(",", ":")))
    size_mb = out_path.stat().st_size / 1_048_576
    print(f"wrote {out_path.name} shares={len(balances):,} "
          f"coverage_top_k={out['coverage_top_k']:.6f} size={size_mb:.1f} MB")


def build_eth():
    src = ROOT / "data" / "eth_validator_balances_finalized_2026-03-17.csv"
    if not src.exists():
        print(f"skipping app-only Ethereum demo; missing {src.relative_to(ROOT)}")
        return
    rows = []
    with src.open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(float(r["balance_eth"]))
    rows.sort(reverse=True)
    total = sum(rows)
    top = rows[:TOP_K_SMALL]
    top_sum = sum(top)
    out = {
        "name": "Ethereum validator-balance demo",
        "resource": "Validator actual balance demo (not consensus-control effective balance)",
        "snapshot_slot": ETH_SNAPSHOT_SLOT,
        "snapshot_epoch": ETH_SNAPSHOT_EPOCH,
        "snapshot_time_utc": ETH_SNAPSHOT_UTC,
        "denominator": total,
        "denominator_unit": "ETH (actual validator-balance sum)",
        "support_full_observed": len(rows),
        "support_top_k": TOP_K_SMALL,
        "coverage_full_observed": 1.0,
        "coverage_top_k": top_sum / total,
        "omitted_tail_mass_top_k_inside_observed":
            (total - top_sum) / total,
        "omitted_tail_mass_top_k_against_supply":
            (total - top_sum) / total,
        "omitted_positive_count_known": len(rows) - TOP_K_SMALL,
        "shares_descending": [b / total for b in top],
        "notes": (
            "Validator-level actual-balance shares (no operator clustering). "
            "This app-only dataset is not the effective-balance "
            "consensus-control certificate described in the paper appendix. "
            "The full positive-balance support is observed, so the omitted "
            "positive count is known exactly once a cap is chosen."
        ),
    }
    out_path = OUT / "eth_top10k.json"
    out_path.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {out_path} shares={len(top)} coverage_top_k={out['coverage_top_k']:.6f}")


if __name__ == "__main__":
    build_btc(TOP_K_SMALL, "bitcoin_top10k.json",
              "Bitcoin top-10k balance records")
    build_btc(TOP_K_FULL, "bitcoin_top1m.json",
              "Bitcoin top-1M balance records")
    build_eth()
