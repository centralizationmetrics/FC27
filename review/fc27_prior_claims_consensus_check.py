#!/usr/bin/env python3
"""Exact rational check of a published-validator-vector sensitivity example.

Run from any directory; only Python's standard library is required.
The input CSV files retain the authors' token counts and labels unchanged.
"""
import csv
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data" / "motepalli2025"
REVISION = "713a10ab25e7e0c1e2b745696151237be2a86256"
ALPHA = F(3, 20)
INPUT_HASHES = {
    "aptos": "b6884e2bfd934c58675ddbd265a400801d718fdc4dd747d99d04c4a447b24b4c",
    "polygon": "5d07515da892bd8afdedb0ae8065c9d316313650f2da1958fed7b3e7bcb02865",
}


def read_vector(name):
    path = DATA / f"25102024_{name}.csv"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == INPUT_HASHES[name], f"Input checksum mismatch: {path.name}"
    rows = list(csv.DictReader(path.open()))
    weights = [F(row["tokens"]) for row in rows]
    assert all(w >= 0 for w in weights)
    total = sum(weights)
    x = sorted((w / total for w in weights if w), reverse=True)
    return x, {
        "url": f"https://raw.githubusercontent.com/sm86/destake/{REVISION}/data/tnsm/{path.name}",
        "sha256": digest,
        "rows": len(rows), "positive_rows": len(x),
        "token_count_total": str(total),
    }


def hhi(x):
    return sum(t * t for t in x)


def threshold_count(x, threshold):
    """Fewest largest positive holdings reaching an exact resource threshold."""
    prefix = F(0)
    for count, share in enumerate(sorted(x, reverse=True), 1):
        prefix += share
        if prefix >= threshold:
            return count
    raise AssertionError("Normalized vector does not reach the threshold")


def level_cap(x, amount):
    """Exact LevelCap for a decreasing positive vector and 0 < amount < 1."""
    prefix = F(0)
    for j, t in enumerate(x, start=1):
        prefix += t
        level = (prefix - amount) / j
        next_value = x[j] if j < len(x) else F(0)
        if next_value <= level <= t:
            return [min(v, level) for v in x]
    raise AssertionError("No cap level found")


def upper_shift(x, amount):
    amount = min(amount, 1 - x[0])
    out = list(x)
    out[0] += amount
    for i in range(len(x) - 1, 0, -1):
        take = min(out[i], amount)
        out[i] -= take
        amount -= take
    assert amount == 0
    return out


def tv(x, y):
    assert len(x) == len(y)
    return sum(abs(a - b) for a, b in zip(x, y)) / 2


def main():
    a, a_meta = read_vector("aptos")
    p, p_meta = read_vector("polygon")
    # A proportional removal preserves every positive Aptos label.
    a_witness = [a[0] + ALPHA] + [t * (1 - ALPHA / (1 - a[0])) for t in a[1:]]
    # Drain Polygon's five largest weights, then add equally to the other 100.
    p_witness = level_cap(p, ALPHA)
    recipients = [i for i, (x, y) in enumerate(zip(p, p_witness)) if x == y]
    assert len(recipients) == 100
    for i in recipients:
        p_witness[i] += ALPHA / len(recipients)
    assert hhi(a) < hhi(p)
    # Whole-label merging cannot lower HHI, and its moved-mass budget embeds
    # in Shift. The Shift maximum therefore gives a safe Merge upper bound.
    assert hhi(upper_shift(a, ALPHA)) < hhi(p)
    assert hhi(a_witness) > hhi(p_witness)  # Two admissible Shifts reverse it.
    # At ten percent even the sharp Shift intervals remain strictly separated.
    assert hhi(upper_shift(a, F(1, 10))) < hhi(level_cap(p, F(1, 10)))
    assert hhi(upper_shift(a, F(1, 10))) < hhi(p)
    result = {"revision": REVISION, "alpha_and_rho": str(ALPHA),
              "merge_budget": "total mass moved; each group retains its largest label",
              "chains": {}}
    for name, x, witness, metadata in [
        ("aptos", a, a_witness, a_meta), ("polygon", p, p_witness, p_meta)
    ]:
        assert sum(x) == sum(witness) == 1
        assert min(witness) > 0
        assert tv(x, witness) == ALPHA
        assert x[0] + ALPHA < 1
        assert sum(max(old - new, 0) for old, new in zip(x, witness)) == ALPHA
        assert sum(max(new - old, 0) for old, new in zip(x, witness)) == ALPHA
        result["chains"][name] = {
            **metadata, "observed_hhi": float(hhi(x)),
            "largest_observed_share": float(x[0]),
            "merge_safe_interval": [float(hhi(x)), float(hhi(upper_shift(x, ALPHA)))],
            "shift_sharp_endpoints": [float(hhi(level_cap(x, ALPHA))), float(hhi(upper_shift(x, ALPHA)))],
            "shift_sharp_endpoints_at_010": [float(hhi(level_cap(x, F(1, 10)))), float(hhi(upper_shift(x, F(1, 10))))],
            "fixed_support_witness_hhi": float(hhi(witness)),
            "fixed_support_witness_tv_exact": str(tv(x, witness)),
            "witness_sum_exact": str(sum(witness)),
        }
        counts = {}
        for threshold in (F(1, 3), F(2, 3)):
            key = str(threshold)
            baseline = threshold_count(x, threshold)
            merge_safe = [threshold_count(x, threshold - ALPHA), baseline]
            shift_sharp = [merge_safe[0], threshold_count(level_cap(x, ALPHA), threshold)]
            assert merge_safe[0] <= baseline <= merge_safe[1]
            assert shift_sharp[0] <= baseline <= shift_sharp[1]
            counts[key] = {
                "observed": baseline,
                "merge_safe_interval": merge_safe,
                "shift_sharp_interval": shift_sharp,
            }
        result["chains"][name]["threshold_counts"] = counts
        path = DATA / f"{name}_shift_015_witness.csv"
        with path.open("w", newline="") as out:
            writer = csv.writer(out)
            writer.writerow(["rank_in_observation", "observed_share_exact", "shifted_share_exact"])
            writer.writerows((i, str(old), str(new)) for i, (old, new) in enumerate(zip(x, witness), 1))
    # Published rounded HHI/coverage summaries in the additional comparison.
    # x_1^2 <= HHI <= h gives x_1 <= sqrt(h); a rational upper bound keeps
    # this conservative moved-mass calculation entirely exact.
    bitcoin_hhi_upper = F("0.0018975")
    largest_share_upper = F("0.043562")
    assert largest_share_upper**2 >= bitcoin_hhi_upper
    budget = F(3, 20)
    merge_upper = bitcoin_hhi_upper + 2*budget*largest_share_upper + budget**2
    ethereum_hhi_lower = F("0.83")**2 * F("0.069375")
    assert merge_upper < ethereum_hhi_lower
    result["rounded_summary_comparison"] = {
        "bitcoin_full_hhi_upper": str(bitcoin_hhi_upper),
        "bitcoin_largest_share_safe_upper": str(largest_share_upper),
        "moved_mass_budget": str(budget),
        "bitcoin_merge_hhi_safe_upper": float(merge_upper),
        "ethereum_full_hhi_strict_lower": float(ethereum_hhi_lower),
        "ordering_certified": True,
    }
    result["exact_checks"] = "PASS: normalized; same positive supports; removed=added=TV=3/20; moved-mass Merge order preserved at 0.10 and 0.15; Shift order preserved at 0.10 and reversed at 0.15; rounded-summary comparison survives moved-mass Merge at 0.15"
    for threshold in ("1/3", "2/3"):
        a_counts = result["chains"]["aptos"]["threshold_counts"][threshold]
        p_counts = result["chains"]["polygon"]["threshold_counts"][threshold]
        assert a_counts["shift_sharp_interval"][0] > p_counts["shift_sharp_interval"][1]
    text = json.dumps(result, indent=2) + "\n"
    (DATA / "certificate_results.json").write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
