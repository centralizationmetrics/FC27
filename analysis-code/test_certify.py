#!/usr/bin/env python3

import math
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import certify


class CertificateRegressionTests(unittest.TestCase):
    def assertClose(self, left, right):
        self.assertTrue(math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12), (left, right))

    def test_exact_packed_tail_power_sum(self):
        lo, hi = certify.cap_power_sum_interval([0.4, 0.3], 0.3, 2.0)
        self.assertClose(lo, 0.25)
        self.assertClose(hi, 0.34)

    def test_fractional_power_at_rounded_packed_tail_boundary(self):
        # This quotient rounds to 39 although its floating residual is
        # slightly negative. Raising that residual to 1.25 used to produce
        # a complex endpoint and made CLI JSON serialization fail.
        x = [0.9981972007890556, 4.506998027360934e-05]
        tail = 0.0017577292306707641
        self.assertLess(tail - math.floor(tail / x[-1])*x[-1], 0)
        lower, upper = self.run_cli(
            x, "--metric", "sp", "--model", "cap", "--tail-mass", str(tail), "--p", "1.25"
        )
        self.assertTrue(math.isfinite(lower) and math.isfinite(upper))
        self.assertLessEqual(lower, upper)
        self.assertClose(upper, certify.power_sum(x, 1.25) + 39*x[-1]**1.25)

    def test_composed_capping_shift_accounts_for_removed_packed_tail(self):
        lo, hi = certify.cap_shift_power_interval([0.4, 0.1], 0.5, 0.12, 2.0)
        self.assertClose(lo, 0.28**2 + 0.1**2)
        self.assertClose(hi, 0.52**2 + 4 * 0.1**2 + 0.08**2)
        # The multiplicity calculation must also handle a tail much larger
        # than could reasonably be materialized as a Python list.
        lo, hi = certify.cap_shift_power_interval([0.4, 1e-12], 0.6 - 1e-12, 0.1, 2.0)
        self.assertClose(lo, 0.3**2 + 1e-24)
        self.assertClose(hi, 0.5**2 + 0.5e-12)

    def test_merge_power_sum_budget(self):
        lo, hi = certify.merge_power_sum_budget([0.9, 0.1], 2.0, 0.1)
        self.assertClose(lo, 0.82)
        self.assertClose(hi, 1.0)

    def test_moved_mass_merge_bounds_contain_all_small_partitions(self):
        # Independent exhaustive partitions check whole-label semantics,
        # including several simultaneous merged groups and unequal receivers.
        from fractions import Fraction as F

        def partitions(items):
            if not items:
                yield []
                return
            first, *rest = items
            for partition in partitions(rest):
                yield [[first], *partition]
                for i in range(len(partition)):
                    yield [group + [first] if j == i else group
                           for j, group in enumerate(partition)]

        for x in ([F(1, 6)]*6, [F(1, 2), F(3, 10), F(1, 5)],
                  [F(2, 5), F(1, 4), F(1, 5), F(1, 10), F(1, 20)]):
            for partition in partitions(list(range(len(x)))):
                grouped = sorted((sum(x[i] for i in group) for group in partition), reverse=True)
                moved = sum(sum(x[i] for i in group) - max(x[i] for i in group)
                            for group in partition)
                for order in (1.25, 2, 3):
                    lower, upper = certify.merge_power_sum_budget(list(map(float, x)), order, float(moved))
                    attained = sum(float(value)**order for value in grouped)
                    self.assertLessEqual(lower, attained + 1e-12)
                    self.assertLessEqual(attained, upper + 1e-12)

    def test_merge_upper_is_reported_as_safe_not_always_attainable(self):
        # Every donor label is larger than .1, so no nontrivial merge fits.
        # The continuous Shift relaxation can nevertheless increase HHI.
        lower, upper = certify.merge_power_sum_budget([0.5, 0.3, 0.2], 2, 0.1)
        self.assertClose(lower, 0.38)
        self.assertClose(upper, 0.46)

    def test_shift_hhi_respects_cross_term_envelope(self):
        x = [0.5, 0.3, 0.2]
        lo, hi = certify.shift_hhi_interval(x, 0.1)
        envelope = certify.hhi(x) + 2 * 0.1 * x[0] + 0.1**2
        self.assertLessEqual(hi, envelope)
        self.assertLess(lo, certify.hhi(x))

    def test_residual_source_shift_hhi(self):
        lo, hi = certify.residual_source_shift_hhi([0.4], [0.3, 0.2, 0.1], 0.1)
        self.assertClose(lo, 0.25)
        self.assertClose(hi, 0.38)

    def test_residual_source_shift_allows_source_receiver_overlap(self):
        lo, hi = certify.residual_source_shift_hhi([0.1], [0.9], 0.2)
        self.assertClose(lo, 0.50)
        self.assertClose(hi, 0.82)

    def test_residual_source_shift_caps_parameter_at_residual_mass(self):
        lo, hi = certify.residual_source_shift_hhi([0.9], [0.1], 0.5)
        self.assertClose(lo, 0.81)
        self.assertClose(hi, 1.00)

    def test_gini_entropy_zipf_are_descriptive_without_extra_assumptions(self):
        for metric in ("gini", "entropy", "zipf"):
            with self.assertRaises(certify.UnsupportedMetricCertificate):
                certify.unsupported_descriptive_metric(metric)

    def test_capped_full_mass_threshold_needs_every_positive_label(self):
        self.assertEqual(certify.cap_nc_interval([0.4, 0.3], 0.3, 1.0, 3), (5, 5))
        self.assertEqual(certify.cap_nc_interval([0.4, 0.3], 0.3, 1.0), (3, math.inf))

    def test_shift_threshold_arithmetic_boundaries(self):
        cases = [
            ([0.6, 0.4], 0.2, 0.8, (1, 2)),
            ([0.5, 0.3, 0.2], 0.1, 0.9, (2, 3)),
            ([0.5, 0.3, 0.2], 0.5, 0.5, (1, 3)),
        ]
        for x, alpha, tau, expected in cases:
            with self.subTest(x=x, alpha=alpha, tau=tau):
                self.assertEqual(certify.shift_nc_interval(x, alpha, tau), expected)
        self.assertEqual(certify.nc([0.1] * 10, 1.0), 10)

    def test_threshold_tolerance_preserves_meaningful_gaps(self):
        self.assertEqual(certify.nc([0.5 - 1e-12, 0.5 + 1e-12], 0.5), 2)
        self.assertEqual(certify.shift_nc_interval([0.6, 0.4], 0.2, 0.8 + 1e-12)[1], math.inf)

    def run_cli(self, x, *arguments):
        with tempfile.TemporaryDirectory() as directory:
            vector = Path(directory) / "shares.json"
            vector.write_text(json.dumps(x))
            completed = subprocess.run(
                [sys.executable, str(Path(certify.__file__)), "--input", str(vector), *arguments],
                check=True, capture_output=True, text=True,
            )
        result = json.loads(completed.stdout)
        return result["lower"], result["upper"]

    def test_cli_dispatches_merge_head_metrics(self):
        self.assertEqual(
            self.run_cli([0.5, 0.3, 0.2], "--metric", "cr", "--model", "merge", "--rho", "0.1", "--k", "1"),
            (0.5, 0.6),
        )
        self.assertEqual(
            self.run_cli([0.5, 0.3, 0.2], "--metric", "nc", "--model", "merge", "--rho", "0.1", "--tau", "0.6"),
            (1, 2),
        )

    def test_cli_preserves_power_order_and_hhi_definition(self):
        lo, hi = self.run_cli(
            [0.5, 0.3, 0.2], "--metric", "sp", "--model", "shift", "--alpha", "0.1", "--p", "3"
        )
        self.assertClose(lo, 0.099)
        self.assertClose(hi, 0.244)
        for model, extra, expected in [
            ("shift", ["--alpha", "0.1"], (0.29, 0.46)),
            ("merge", ["--rho", "0.1"], (0.38, 0.46)),
            ("cap", ["--tail-mass", "0.3"], (0.25, 0.34)),
        ]:
            with self.subTest(model=model):
                x = [0.4, 0.3] if model == "cap" else [0.5, 0.3, 0.2]
                lo, hi = self.run_cli(x, "--metric", "hhi", "--model", model, "--p", "3", *extra)
                self.assertClose(lo, expected[0])
                self.assertClose(hi, expected[1])

    def test_cli_exposes_count_aware_full_mass_threshold(self):
        self.assertEqual(
            self.run_cli([0.4, 0.3], "--metric", "nc", "--model", "cap", "--tail-mass", "0.3", "--tau", "1", "--omitted-count", "3"),
            (5, 5),
        )

    def assert_cli_rejects(self, x, *arguments, message):
        with tempfile.TemporaryDirectory() as directory:
            vector = Path(directory) / "shares.json"
            vector.write_text(json.dumps(x))
            completed = subprocess.run(
                [sys.executable, str(Path(certify.__file__)), "--input", str(vector), *arguments],
                capture_output=True, text=True,
            )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn(message, completed.stderr)

    def test_cli_rejects_invalid_complete_vectors_before_certifying(self):
        for values in ([0.2, 0.2], [2, 1]):
            for model, budget in (("shift", "--alpha"), ("merge", "--rho")):
                with self.subTest(values=values, model=model):
                    self.assert_cli_rejects(
                        values, "--metric", "hhi", "--model", model, budget, "0.1",
                        message="must sum to 1",
                    )
        for invalid in (-0.1, math.nan, math.inf):
            for normalize in ([], ["--normalize"]):
                with self.subTest(invalid=invalid, normalize=normalize):
                    self.assert_cli_rejects(
                        [0.6, 0.4, invalid], "--metric", "hhi", "--model", "shift",
                        "--alpha", "0.1", *normalize, message="finite and nonnegative",
                    )

    def test_cli_normalizes_explicit_complete_weights_and_ignores_zeros(self):
        lo, hi = self.run_cli(
            [2, 0, 5, 3], "--metric", "hhi", "--model", "shift", "--alpha", "0.1", "--normalize"
        )
        self.assertClose(lo, 0.29)
        self.assertClose(hi, 0.46)

    def test_cli_rejects_inconsistent_capped_observations(self):
        cases = [
            ([0.4, 0.3], "0.2", [], "must sum to 1"),
            ([0.4, 0.3], "0.3", ["--omitted-count", "0"], "zero exactly"),
            ([0.6, 0.4], "0", ["--omitted-count", "1"], "zero exactly"),
            ([0.6, 0.1], "0.3", ["--omitted-count", "2"], "cannot hold"),
            ([4, 3], "0.3", ["--normalize"], "only for complete"),
        ]
        for values, tail, extra, message in cases:
            with self.subTest(values=values, tail=tail, extra=extra):
                self.assert_cli_rejects(
                    values, "--metric", "hhi", "--model", "cap", "--tail-mass", tail,
                    *extra, message=message,
                )

    def test_cli_checks_residual_source_common_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            declared = Path(directory) / "declared.json"
            residual = Path(directory) / "residual.json"
            declared.write_text("[0.2]")
            residual.write_text("[0.2]")
            completed = subprocess.run(
                [sys.executable, str(Path(certify.__file__)), "--declared", str(declared),
                 "--residual", str(residual), "--metric", "hhi", "--model", "residual-shift",
                 "--alpha", "0.1"],
                capture_output=True, text=True,
            )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn("declared and residual shares together must sum to 1", completed.stderr)


if __name__ == "__main__":
    unittest.main()
