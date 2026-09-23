#!/usr/bin/env python3
"""Independently verify Ethereum's conditional Merge bounds using integers."""
import csv
import json
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def nc(values, tau):
    total = F(0)
    for j, value in enumerate(values, 1):
        total += value
        if total >= tau:
            return j
    return float('inf')


def main():
    with (ROOT/'data/eth_execution_withdrawal_address_groups_2026-09-22.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    total = sum(int(row['effective_balance_gwei']) for row in rows)
    fixed = sorted((F(int(row['effective_balance_gwei']), total) for row in rows
                    if not int(row['credential_00_count'])), reverse=True)
    unresolved = [F(int(row['effective_balance_gwei']), total) for row in rows
                  if int(row['credential_00_count'])]
    mass = sum(unresolved)
    baseline = sorted(fixed+unresolved, reverse=True)
    largest = [fixed[0]+mass]+fixed[1:]
    fixed_hhi = sum(v*v for v in fixed)
    unresolved_hhi = sum(v*v for v in unresolved)
    expected = {'hhi': (fixed_hhi+unresolved_hhi, sum(v*v for v in largest)),
                'cr': (sum(baseline[:10000]), sum(largest[:10000])),
                'nc': (nc(largest,F(1,2)), nc(baseline,F(1,2)))}
    with (ROOT/'data/eth_merge_shift_calibration_summary.csv').open() as stream:
        for row in csv.DictReader(stream):
            lo, hi = expected[row['metric']]
            assert abs(float(lo)-float(row['conditional_merge_lower'])) < 1e-12
            assert abs(float(hi)-float(row['conditional_merge_upper'])) < 1e-12
    assert unresolved_hhi <= mass*max(unresolved) < F(5,10**9)
    assert sum([fixed[0]]+unresolved)-max([fixed[0]]+unresolved) <= mass
    result = {'model': 'conditional Merge of whole validator holdings',
              'all_endpoints_attained': True, 'unresolved_mass': float(mass), 'unresolved_hhi': float(unresolved_hhi),
              'grouped_hhi': float(fixed_hhi+unresolved_hhi),
              'sharp_conditional': {m: [float(lo),float(hi)] for m,(lo,hi) in expected.items()},
              'exact_endpoints': {m: [str(lo),str(hi)] for m,(lo,hi) in expected.items()},
              'verified': 'integer input and exact rational endpoint calculations agree with figure summary'}
    (ROOT/'data/eth_conditional_exact_check.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
