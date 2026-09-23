#!/usr/bin/env python3

import csv
import gzip
import json
import math
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
INPUT_JSONL = ROOT / "data" / "top_mill_adresses.json"
OUTPUT_CSV = ROOT / "data" / "bitcoin_top1m_capping_convergence_summary.csv"

SNAPSHOT_DATE = "2025-09-23"
# Historical circulating supply for Bitcoin on 2025-09-23.
SATOSHIS_PER_BTC = 100_000_000
TOTAL_SUPPLY_BTC = 19_925_284.0
TOTAL_SUPPLY_SATOSHIS = 19_925_284 * SATOSHIS_PER_BTC
EXPECTED_TOP1M_SATOSHIS = 1_855_762_831_566_030
# Positive-balance Bitcoin address count used for the count-aware Gini panel.
# This is an external count input for the snapshot, separate from the top-1M
# BigQuery rich-list extraction.
N_POSITIVE_ADDRESSES = 55_000_000
CR_K = 10_000
NC_TAU = 0.5
GRID_SIZE = 80
MIN_CAP = 100


def btc_string_to_satoshis(value: str | int) -> int:
    value = str(value)
    whole, separator, fraction = value.partition(".")
    if not separator:
        fraction = ""
    if len(fraction) > 8:
        raise ValueError(f"balance has sub-satoshi precision: {value!r}")
    return int(whole) * SATOSHIS_PER_BTC + int((fraction + "00000000")[:8])


def load_balances(path: Path) -> np.ndarray:
    balances = []
    with open_text(path) as f:
        for line in f:
            row = json.loads(line)
            balances.append(btc_string_to_satoshis(row["balance_btc"]))
    return np.array(balances, dtype=np.int64)


def open_text(path: Path):
    if path.exists():
        return path.open()
    gz_path = path.with_suffix(path.suffix + ".gz")
    if gz_path.exists():
        return gzip.open(gz_path, "rt")
    return path.open()


def log_cap_grid(n: int) -> np.ndarray:
    upper = n
    values = np.geomspace(MIN_CAP, upper, GRID_SIZE)
    values = np.unique(values.astype(int))
    anchors = np.array([100, 300, 1_000, 3_000, 10_000, 30_000, 100_000, 300_000, upper])
    values = np.unique(np.concatenate([values, anchors[anchors <= upper], np.array([upper])]))
    values = values[values >= MIN_CAP]
    return values


def compute_rows(balance_satoshis: np.ndarray) -> list[dict[str, float]]:
    observed_n = balance_satoshis.size
    x = balance_satoshis.astype(np.float64) / TOTAL_SUPPLY_SATOSHIS
    prefix = np.cumsum(balance_satoshis, dtype=np.int64) / TOTAL_SUPPLY_SATOSHIS
    prefix_sq = np.cumsum(x * x)

    observed_mass = float(balance_satoshis.sum(dtype=np.int64) / TOTAL_SUPPLY_SATOSHIS)
    cr_exact = float(prefix[CR_K - 1])
    nc_exact = int(np.searchsorted(prefix, NC_TAU, side="left") + 1) if observed_mass >= NC_TAU else None

    # For count-aware Gini, the omitted positive-balance count M_N depends on
    # an external estimate of the total positive-address population. The full
    # owner-level distribution is never observed.
    rows = []
    for N in log_cap_grid(observed_n):
        P_N = float(prefix[N - 1])
        x_N = float(x[N - 1])
        T_N = float(1.0 - P_N)

        cr_lower = float(prefix[min(CR_K, N) - 1])
        if N >= CR_K:
            cr_upper = cr_lower
        else:
            cr_upper = float(P_N + min(T_N, (CR_K - N) * x_N))

        hhi_lower = float(prefix_sq[N - 1])
        q_hhi = int(T_N / x_N + 1e-12) if x_N > 0 else 0
        r_hhi = T_N - q_hhi * x_N
        if r_hhi < 0.0:
            r_hhi = 0.0
        if x_N > 0 and r_hhi >= x_N:
            r_hhi = float(np.nextafter(x_N, 0.0))
        hhi_tail_exact = float(q_hhi * x_N * x_N + r_hhi * r_hhi)
        hhi_upper = float(hhi_lower + hhi_tail_exact)
        hhi_upper_safe = float(hhi_lower + T_N * T_N)
        hill2_lower = float(1.0 / hhi_upper)
        hill2_upper = float(1.0 / hhi_lower)

        if P_N >= NC_TAU:
            nc_lower = int(np.searchsorted(prefix[:N], NC_TAU, side="left") + 1)
            nc_upper = nc_lower
        else:
            delta = NC_TAU - P_N
            nc_lower = N + math.ceil(delta / x_N - 1e-15)
            nc_upper = float("nan")

        # Count-aware Gini band at the stated positive-address count.
        head = x[:N]
        d_N = float(np.dot((N + 1) - 2 * np.arange(1, N + 1, dtype=np.float64), head))
        M_N = max(N_POSITIVE_ADDRESSES - N, 0)
        n_full = N + M_N
        gini_lower = float((d_N + M_N * (1.0 - T_N) - N * T_N) / n_full)
        if M_N == 0:
            gini_upper = gini_lower
        else:
            q = min(M_N, int(T_N / x_N + 1e-12))
            r = T_N - q * x_N
            if r < 0.0:
                r = 0.0
            if r >= x_N:
                r = float(np.nextafter(x_N, 0.0))
            e_max = x_N * q * (M_N - q) + r * (M_N - 1 - 2 * q)
            gini_upper = float(
                (d_N + M_N * (1.0 - T_N) - N * T_N + e_max) / n_full
            )

        rows.append(
            {
                "snapshot_date": SNAPSHOT_DATE,
                "N": N,
                "coverage": P_N,
                "tail_mass": T_N,
                "observed_support": observed_n,
                "observed_mass_top1m": observed_mass,
                "total_supply_btc": TOTAL_SUPPLY_BTC,
                "cr_lower": cr_lower,
                "cr_upper": cr_upper,
                "cr_exact": cr_exact,
                "nc_lower": nc_lower,
                "nc_upper": nc_upper,
                "nc_exact": nc_exact,
                "hhi_lower": hhi_lower,
                "hhi_upper": hhi_upper,
                "hhi_upper_safe": hhi_upper_safe,
                "hhi_tail_exact": hhi_tail_exact,
                "hill2_lower": hill2_lower,
                "hill2_upper": hill2_upper,
                "positive_address_count": N_POSITIVE_ADDRESSES,
                "omitted_positive_count": M_N,
                "gini_lower_count_aware": gini_lower,
                "gini_upper_count_aware": gini_upper,
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
    balances = load_balances(INPUT_JSONL)
    observed_satoshis = int(balances.sum(dtype=np.int64))
    if observed_satoshis != EXPECTED_TOP1M_SATOSHIS:
        raise ValueError(
            f"top-million balance checksum failed: {observed_satoshis} satoshis"
        )
    rows = compute_rows(balances)
    write_summary(rows)
    print(f"observed_support {balances.size}")
    print(f"top1m_sum_btc {observed_satoshis / SATOSHIS_PER_BTC:.8f}")
    print(f"total_supply_btc {TOTAL_SUPPLY_BTC:.8f}")
    print(f"observed_mass_top1m {observed_satoshis / TOTAL_SUPPLY_SATOSHIS:.10f}")
    print(f"summary {OUTPUT_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
