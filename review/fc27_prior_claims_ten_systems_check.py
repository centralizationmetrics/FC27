#!/usr/bin/env python3
"""Recompute HHI and threshold-count certificates for ten published PoS vectors.

Inputs are the authors' unchanged CSVs at a pinned repository revision. All
certificate calculations use exact rational arithmetic and the manuscript's
positive-holding and exact-threshold conventions.
"""
import csv
import hashlib
import itertools
import json
from fractions import Fraction as F
from pathlib import Path

from fc27_prior_claims_consensus_check import hhi, level_cap, threshold_count, upper_shift

DATA = Path(__file__).resolve().parent / "data" / "motepalli2025"
REVISION = "713a10ab25e7e0c1e2b745696151237be2a86256"
RHO = F(3, 20)
SOURCES = {
    "aptos": ("25102024_aptos.csv", "b6884e2bfd934c58675ddbd265a400801d718fdc4dd747d99d04c4a447b24b4c"),
    "axelar": ("25102024_axelar.csv", "3eedaba976fdfb0b9db7c050b16d9274387237386c906b9d59b0b05d2ff0bbb1"),
    "binance": ("14122023_binance.csv", "def9b17987f72a73dd9bc5663d7432641588eab025aadf34b35e12f21f0a9f24"),
    "celestia": ("25102024_celestia.csv", "73ea1c7e8a74f507461eca57dff0e315e5a41db515aa23df452b3e59496bb15c"),
    "celo": ("25102024_celo.csv", "28b3dd4c9a45a961c997e045612584c8bb02db9c19772f3309a52430d8736800"),
    "cosmos": ("25102024_cosmos.csv", "64aabf7253557bf8ec23ed36abfbba61d3707650d7e1eba990a6446841f03613"),
    "injective": ("25102024_injective.csv", "0a3fef824aadf0086b927368d09c51e805da5989d5cbff3e577e1c464e35eb24"),
    "osmosis": ("14122023_osmosis.csv", "37770817aac9a97143da65ba67643fccc04bd894275d91b24a7a8a3660176b9d"),
    "polygon": ("25102024_polygon.csv", "5d07515da892bd8afdedb0ae8065c9d316313650f2da1958fed7b3e7bcb02865"),
    "sui": ("25102024_sui.csv", "5cf5a7cc76f1c268f20c0592e75539622a373e87f6320a365dc95cd8ab569a25"),
}


def source_vector(name):
    filename, expected_hash = SOURCES[name]
    path = DATA / filename
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash
    rows = list(csv.DictReader(path.open()))
    weights = [F(row["tokens"]) for row in rows]
    assert all(weight >= 0 for weight in weights) and sum(weights) > 0
    total = sum(weights)
    shares = sorted((weight / total for weight in weights if weight > 0), reverse=True)
    assert sum(shares) == 1
    metadata = {
        "source_url": f"https://raw.githubusercontent.com/sm86/destake/{REVISION}/data/tnsm/{filename}",
        "sha256": expected_hash,
        "rows": len(rows),
        "positive_rows": len(shares),
        "token_count_total": str(total),
    }
    return shares, metadata


def metric_rows(shares):
    capped = level_cap(shares, RHO)
    raised = upper_shift(shares, RHO)
    base_hhi = hhi(shares)
    result = {
        "HHI": {
            "observed": float(base_hhi),
            "merge_safe": [float(base_hhi), float(hhi(raised))],
            "shift_sharp": [float(hhi(capped)), float(hhi(raised))],
        }
    }
    exact = {"HHI": (base_hhi, (base_hhi, hhi(raised)), (hhi(capped), hhi(raised)))}
    for threshold in (F(1, 3), F(2, 3)):
        metric = f"NC_{threshold}"
        observed = threshold_count(shares, threshold)
        lower = threshold_count(shares, threshold - RHO)
        merge = (lower, observed)
        shift = (lower, threshold_count(capped, threshold))
        assert lower <= observed <= shift[1]
        exact[metric] = (observed, merge, shift)
        result[metric] = {"observed": observed, "merge_safe": list(merge), "shift_sharp": list(shift)}
    return result, exact


def comparisons(exact, metric):
    names = sorted(exact)
    observed = 0
    certified_merge = []
    certified_shift = []
    reversed_with_two_new = []
    reversal_margins = []
    for left, right in itertools.combinations(names, 2):
        a, b = exact[left][metric], exact[right][metric]
        if a[0] == b[0]:
            continue
        observed += 1
        low, high = (left, right) if a[0] < b[0] else (right, left)
        if exact[low][metric][1][1] < exact[high][metric][1][0]:
            certified_merge.append([low, high])
        if exact[low][metric][2][1] < exact[high][metric][2][0]:
            certified_shift.append([low, high])
        if metric == "HHI":
            # Increase the originally lower HHI to its attainable Shift maximum.
            # Drain rho from the originally higher HHI via LevelCap, and put
            # rho/2 into each of two new controllers. Both moves cost rho.
            margin = exact[low][metric][2][1] - (exact[high][metric][2][0] + RHO**2 / 2)
            if margin > 0:
                reversed_with_two_new.append([low, high])
                reversal_margins.append(margin)
    assert len(certified_shift) <= len(certified_merge) <= observed
    result = {"strict_observed_pairs": observed,
            "certified_by_safe_merge_bounds": len(certified_merge),
            "certified_by_sharp_shift_intervals": len(certified_shift),
            "merge_pairs": certified_merge, "shift_pairs": certified_shift}
    if metric == "HHI":
        assert len(reversed_with_two_new) == observed
        result["reversible_by_explicit_two_new_controller_shift"] = len(reversed_with_two_new)
        result["smallest_exact_reversal_margin"] = str(min(reversal_margins))
        result["smallest_reversal_margin_decimal"] = float(min(reversal_margins))
    return result


def main():
    source_summary = {row["blockchain"]: row for row in
                      csv.DictReader((DATA / "empiricial-analysis-tnsm.csv").open())
                      if row["scale"] == "tokens"}
    result = {"source_revision": REVISION, "moved_mass_budget": str(RHO), "chains": {}}
    exact = {}
    for name in sorted(SOURCES):
        shares, metadata = source_vector(name)
        rows, exact[name] = metric_rows(shares)
        # The published HHI is rounded to three decimal places.
        assert abs(exact[name]["HHI"][0] - F(source_summary[name]["hhi"])) < F(1, 2000)
        result["chains"][name] = {**metadata, "metrics": rows}
    result["pairwise_orderings"] = {
        metric: comparisons(exact, metric) for metric in ("HHI", "NC_1/3", "NC_2/3")
    }
    assert [(result["pairwise_orderings"][metric]["strict_observed_pairs"],
             result["pairwise_orderings"][metric]["certified_by_safe_merge_bounds"],
             result["pairwise_orderings"][metric]["certified_by_sharp_shift_intervals"])
            for metric in ("HHI", "NC_1/3", "NC_2/3")] == [
                (45, 2, 0), (42, 12, 2), (45, 23, 11)]
    output = DATA / "ten_system_certificates.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print("Metric   Observed strict   Merge certified   Shift certified")
    for metric, row in result["pairwise_orderings"].items():
        print(f"{metric:8} {row['strict_observed_pairs']:>8} {row['certified_by_safe_merge_bounds']:>17} {row['certified_by_sharp_shift_intervals']:>17}")
    hhi_comparisons = result["pairwise_orderings"]["HHI"]
    print(f"HHI reversals using two new controllers: {hhi_comparisons['reversible_by_explicit_two_new_controller_shift']}")


if __name__ == "__main__":
    main()
