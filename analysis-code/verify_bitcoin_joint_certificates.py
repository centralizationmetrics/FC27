#!/usr/bin/env python3
"""Check the published Bitcoin rows against exact satoshi/Fraction arithmetic."""

import csv
import json
from fractions import Fraction as F
import math
from pathlib import Path

import numpy as np

from summarize_bitcoin_top1m_capping_convergence import (
    EXPECTED_TOP1M_SATOSHIS, INPUT_JSONL, TOTAL_SUPPLY_SATOSHIS, load_balances,
)


def main():
    data = load_balances(INPUT_JSONL)
    data.sort()
    h = data[::-1]
    assert h.size == 1_000_000 and int(h.sum()) == EXPECTED_TOP1M_SATOSHIS
    D = TOTAL_SUPPLY_SATOSHIS
    observed = int(h.sum())
    tail = D - observed
    cap = int(h[-1])
    q, r = divmod(tail, cap)
    base_sq = sum(int(v)**2 for v in h)
    cap_lo = F(base_sq, D*D)
    cap_hi = F(base_sq + q*cap*cap + r*r, D*D)
    prefix = np.concatenate(([0], np.cumsum(h, dtype=np.int64)))
    path = Path(__file__).resolve().parents[1] / "data/bitcoin_joint_certificates_summary.csv"
    rows = list(csv.DictReader(path.open()))
    merge_gaps = []
    for budget in (F(0), F(1, 10), F(3, 10)):
        row = next(row for row in rows if float(row["budget"]) == float(budget))
        moved = budget * D
        assert moved.denominator == 1
        moved = int(moved)
        # Locate the exact LevelCap threshold, with no floating-point search.
        count = 1
        while count < h.size and int(prefix[count]) - count*int(h[count]) < moved:
            count += 1
        level = F(int(prefix[count]) - moved, count)
        lower = (count*level*level + sum(int(v)**2 for v in h[count:])) / (D*D)
        # Exact TailTrim on the packed completion: omitted shares go first.
        if moved <= tail:
            q_left, r_left = divmod(tail-moved, cap)
            upper = F((int(h[0])+moved)**2 + base_sq-int(h[0])**2
                      + q_left*cap*cap+r_left*r_left, D*D)
        else:
            amount = moved-tail
            upper_sq = (int(h[0])+moved)**2
            for value in h[:0:-1]:
                value = int(value)
                take = min(value, amount)
                upper_sq += (value-take)**2
                amount -= take
            assert amount == 0
            upper = F(upper_sq, D*D)

        def residual_prefix(rank):
            if rank <= count:
                return rank*level / D
            return (count*level + int(prefix[rank])-int(prefix[count])) / D

        expected = {
            "hhi_capping_lower": cap_lo, "hhi_capping_upper": cap_hi,
            "hhi_merge_lower": cap_lo, "hhi_merge_upper": upper,
            "hhi_shift_lower": lower, "hhi_shift_upper": upper,
            "cr_shift_lower": residual_prefix(10_000),
            "cr_shift_upper": min(F(1), F(int(prefix[10_000]), D)+budget),
        }
        for field, exact in expected.items():
            assert math.isclose(float(row[field]), float(exact), rel_tol=2e-12, abs_tol=1e-15), field
        rank = int(float(row["nc_shift_upper"]))
        assert residual_prefix(rank-1) < F(1, 2) <= residual_prefix(rank)
        rank = int(float(row["nc_shift_lower"]))
        assert F(int(prefix[rank-1]), D)+budget < F(1, 2) <= F(int(prefix[rank]), D)+budget
        # A feasible whole-label Merge gives a lower bound on the unknown
        # maximum. Move the omitted tail and as many smallest whole observed
        # holdings as fit; only the Shift trim-point holding is left partial.
        if moved <= tail:
            witness, gap_bound = upper, F(0)
        else:
            remaining, donor_mass, donor_squares = moved-tail, 0, 0
            boundary = 0
            for value in h[:0:-1]:
                value = int(value)
                if value > remaining:
                    boundary = value
                    break
                donor_mass += value
                donor_squares += value*value
                remaining -= value
            witness = F((int(h[0])+tail+donor_mass)**2+base_sq-int(h[0])**2-donor_squares,D*D)
            gap_bound = F(2*(int(h[0])+moved)*boundary,D*D)
            assert upper-witness == F(2*remaining*(int(h[0])+moved-boundary),D*D)
        assert 0 <= upper-witness <= gap_bound
        merge_gaps.append({'budget': str(budget), 'feasible_merge_hhi': float(witness),
                           'shift_upper_minus_merge_witness': float(upper-witness),
                           'gap_bound': float(gap_bound)})
        print(f"budget {budget}: HHI endpoints and head-metric thresholds verified exactly")
    (path.parent/'bitcoin_merge_upper_gaps.json').write_text(json.dumps(merge_gaps,indent=2)+'\n')
    print(json.dumps(merge_gaps,indent=2))


if __name__ == "__main__":
    main()
