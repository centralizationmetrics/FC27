#!/usr/bin/env python3
"""Exact-rational enclosures of ordering breakdown budgets for supplied vectors.

Shift endpoints give the breakdown of each strict observed ordering. The Merge
calculation uses a relaxation and gives a certified lower bound, not an exact
whole-label breakdown. Each bisection bracket is checked with rational arithmetic;
no claim is made about attainment at its limiting boundary.
"""
import bisect
import itertools
import json
from fractions import Fraction as F
from pathlib import Path
from statistics import median

from fc27_prior_claims_ten_systems_check import SOURCES, source_vector
from fc27_prior_claims_consensus_check import hhi, level_cap, threshold_count, upper_shift


class Vector:
    def __init__(self, shares):
        self.x = shares
        self.prefix = [F(0)]
        self.squares = [F(0)]
        for v in shares:
            self.prefix.append(self.prefix[-1] + v)
            self.squares.append(self.squares[-1] + v*v)
        self.costs = [self.prefix[j] - j*shares[j] for j in range(1, len(shares))] + [F(1)]

    def level(self, rho):
        j = bisect.bisect_left(self.costs, rho) + 1
        return j, (self.prefix[j] - rho)/j

    def lower_hhi(self, rho):
        j, cap = self.level(rho)
        return j*cap*cap + self.squares[-1] - self.squares[j]

    def upper_hhi(self, rho):
        a = min(rho, 1-self.x[0])
        j = bisect.bisect_right(self.prefix, 1-a) - 1
        remainder = 1-a-self.prefix[j]
        return (self.x[0]+a)**2-self.x[0]**2+self.squares[j]+remainder**2

    def nc(self, tau):
        return max(1, bisect.bisect_left(self.prefix, tau))

    def upper_nc(self, rho, tau):
        if tau > 1-rho:
            return float('inf')
        j, cap = self.level(rho)
        if tau <= j*cap:
            ratio = tau/cap
            return -(-ratio.numerator // ratio.denominator)
        return self.nc(tau+rho)

    def endpoints(self, metric, model, rho):
        if metric == 'HHI':
            lower = self.squares[-1] if model == 'Merge' else self.lower_hhi(rho)
            return lower, self.upper_hhi(rho)
        tau = F(metric.removeprefix('NC_'))
        upper = self.nc(tau) if model == 'Merge' else self.upper_nc(rho, tau)
        return self.nc(tau-rho), upper


def bracket(predicate, steps=40):
    """Predicate is true while a strict interval separation is certified."""
    lo, hi = F(0), F(1)
    assert predicate(lo) and not predicate(hi)
    for _ in range(steps):
        mid = (lo+hi)/2
        if predicate(mid):
            lo = mid
        else:
            hi = mid
    assert predicate(lo) and not predicate(hi)
    return {'lower_exact': str(lo), 'upper_exact': str(hi),
            'lower': float(lo), 'upper': float(hi)}


def main():
    vectors = {name: Vector(source_vector(name)[0]) for name in SOURCES}
    # Check the faster piecewise formulas against independent vector operations.
    for vector in vectors.values():
        for rho in (F(0), F(1,10), F(3,20), F(1,3), F(2,3), F(1)):
            assert vector.lower_hhi(rho) == hhi(level_cap(vector.x, rho))
            assert vector.upper_hhi(rho) == hhi(upper_shift(vector.x, rho))
            for tau in (F(1,3), F(2,3)):
                assert vector.nc(tau-rho) == threshold_count(vector.x, tau-rho)
                if tau <= 1-rho:
                    assert vector.upper_nc(rho, tau) == threshold_count(level_cap(vector.x, rho), tau)
    rows = []
    for metric in ('HHI', 'NC_1/3', 'NC_2/3'):
        for name_a, name_b in itertools.combinations(vectors, 2):
            a, b = vectors[name_a], vectors[name_b]
            a0, b0 = a.endpoints(metric, 'Merge', F(0))[0], b.endpoints(metric, 'Merge', F(0))[0]
            if a0 == b0:
                continue
            if a0 > b0:
                name_a, name_b, a, b = name_b, name_a, b, a
            row = {'metric': metric, 'lower_observed': name_a, 'higher_observed': name_b}
            for model in ('Merge', 'Shift'):
                row[model] = bracket(lambda rho: a.endpoints(metric, model, rho)[1] < b.endpoints(metric, model, rho)[0])
            rows.append(row)
    summary = {}
    for metric in ('HHI', 'NC_1/3', 'NC_2/3'):
        summary[metric] = {}
        for model in ('Merge', 'Shift'):
            values = [r[model]['lower'] for r in rows if r['metric'] == metric]
            summary[metric][model] = {'count': len(values), 'min': min(values), 'median': median(values), 'max': max(values)}
    # This is a guarantee from rounded published summaries, not an exact breakdown.
    btc, largest, eth = F('0.0018975'), F('0.043562'), F('0.83')**2*F('0.069375')
    wealth = bracket(lambda rho: btc+2*rho*largest+rho*rho < eth)
    result = {'meaning': {'Shift': 'breakdown of strict observed ordering; exact-rational enclosing bracket',
                          'Merge': 'boundary of sufficient interval-separation guarantee; lower bound on true breakdown'},
              'maximum_bracket_width': str(F(1, 2**40)), 'pairs': rows,
              'summary': summary, 'published_wealth_safe_budget': wealth}
    path = Path(__file__).resolve().parent / 'data' / 'motepalli2025' / 'breakdown_budgets.json'
    path.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(summary, indent=2))
    print('Aptos/Polygon:', json.dumps([r for r in rows if {r['lower_observed'], r['higher_observed']} == {'aptos','polygon'}], indent=2))
    print('Published-wealth sufficient budget:', wealth)


if __name__ == '__main__':
    main()
