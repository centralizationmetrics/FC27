"""Checks for the joint Bitcoin calculation, including omitted-tail branches."""

import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import certify
from joint_capping import JointShift, capping_power_interval, joint_metric_bands


class JointCappingTests(unittest.TestCase):
    def assertPairClose(self, actual, expected):
        for a, b in zip(actual, expected):
            self.assertTrue(math.isclose(a, b, rel_tol=2e-12, abs_tol=1e-14), (a, b))

    def test_introductory_example_and_zero_budget(self):
        head = np.array([0.50, 0.20, 0.15])
        self.assertPairClose(capping_power_interval(head, 0.15, 2), (0.3125, 0.335))
        self.assertPairClose(JointShift(head, 0.15, 0).power_interval(2), (0.3125, 0.335))
        self.assertPairClose(JointShift(head, 0.15, 0.30).power_interval(2), (0.1025, 0.68))
        # The moved-mass Merge upper bound uses Shift's maximum. Here it is
        # attained by merging the observed .15 and omitted .15 into .50.
        bands = joint_metric_bands(head, 0.15, np.array([0.0, 0.30]), k=2, tau=0.5)
        self.assertPairClose(tuple(v[-1] for v in bands["hhi_merge"]), (0.3125, 0.68))
        self.assertPairClose(tuple(v[-1] for v in bands["cr_shift"]), (0.4, 1.0))
        self.assertPairClose(tuple(v[-1] for v in bands["nc_shift"]), (1, 3))

    def test_against_independent_reference_across_tail_drain_cases(self):
        observations = [([0.4, 0.1], 0.5), ([0.5, 0.2, 0.15], 0.15),
                        ([0.4, 1e-12], 0.6-1e-12), ([0.6, 0.4], 0.0)]
        for values, tail in observations:
            for budget in (0.0, 0.05, 0.15, 0.30, 0.60, 1.0):
                for p in (1.25, 2.0, 3.0):
                    with self.subTest(values=values, tail=tail, budget=budget, p=p):
                        actual = JointShift(np.array(values), tail, budget).power_interval(p)
                        expected = certify.cap_shift_power_interval(values, tail, budget, p)
                        self.assertPairClose(actual, expected)

    def test_materialized_packed_completion_and_feasible_lower_sequence(self):
        head = np.array([0.4, 0.1])
        tail = 0.5
        completion = [0.4] + [0.1]*6
        for budget in (0.02, 0.12, 0.5, 0.55):
            joint = JointShift(head, tail, budget)
            for p in (1.25, 2, 3):
                lo, hi = joint.power_interval(p)
                self.assertPairClose((hi,), (certify.shift_power_sum_interval(completion, budget, p)[1],))
                # A feasible completion and reassignment must remain inside
                # the computed interval; fragmentation approaches its lower end.
                for count in (10, 100):
                    moved = min(budget, sum(head))
                    residual = certify.level_cap(list(head), moved)
                    output = residual + [tail/count]*count + [moved/count]*count
                    value = certify.power_sum(output, p)
                    self.assertGreaterEqual(value + 1e-14, lo)
                    self.assertLessEqual(value, hi + 1e-14)

    def test_head_metric_scope_is_enforced(self):
        for k, tau in ((4, 0.5), (2, 0.6)):
            with self.assertRaises(ValueError):
                joint_metric_bands(np.array([0.5, 0.2, 0.15]), 0.15,
                                   np.array([0, 0.3]), k=k, tau=tau)

    def test_merge_attains_joint_shift_upper_using_only_omitted_labels(self):
        from fractions import Fraction as F
        for head in ([F(2,5), F(1,10)], [F(1,2), F(1,5), F(3,20)], [F(1,10)]):
            tail = 1-sum(head)
            for rho in (F(0), tail/3, tail/2, tail):
                count = max(1, math.ceil(rho/head[-1]))
                donors = [rho/count]*count if rho else []
                leftover = tail-rho
                full = leftover//head[-1]
                packed = [head[-1]]*full
                remainder = leftover-full*head[-1]
                if remainder:
                    packed.append(remainder)
                completion = head+donors+packed
                self.assertEqual(sum(completion), 1)
                self.assertTrue(all(0 < v <= head[-1] for v in donors+packed))
                self.assertEqual(sum([head[0]]+donors)-max([head[0]]+donors), rho)
                output = [head[0]+rho]+head[1:]+packed
                for p in (2,3):
                    exact = sum(v**p for v in output)
                    calculated = JointShift(np.array(list(map(float, head))), float(tail), float(rho)).power_interval(p)[1]
                    self.assertAlmostEqual(calculated, float(exact), places=13)

    def test_conditional_merge_against_all_allowed_groupings(self):
        def partitions(indices):
            if not indices:
                yield []
                return
            first, *rest = indices
            for groups in partitions(rest):
                yield [[first]] + groups
                for i in range(len(groups)):
                    yield groups[:i] + [[first] + groups[i]] + groups[i+1:]

        for fixed, unresolved in [([.4, .3], [.2, .1]),
                                  ([.1, .2], [.4, .3]), ([.4, .6], [])]:
            values = fixed + unresolved
            outputs = []
            for groups in partitions(list(range(len(values)))):
                if any(sum(i < len(fixed) for i in group) > 1 for group in groups):
                    continue
                cost = sum(sum(values[i] for i in group) - max(values[i] for i in group)
                           for group in groups)
                self.assertLessEqual(cost, sum(unresolved) + 1e-14)
                outputs.append(sorted([sum(values[i] for i in group) for group in groups], reverse=True))
            for k in [1, 2, 5]:
                for tau in [.25, .5, .9]:
                    result = certify.unresolved_merge_intervals(fixed, unresolved, k, tau)
                    for metric, evaluate in [('hhi', certify.hhi),
                                             ('cr', lambda v: certify.cr(v, k)),
                                             ('nc', lambda v: certify.nc(v, tau))]:
                        measured = [evaluate(v) for v in outputs]
                        self.assertPairClose(result[metric], (min(measured), max(measured)))

    def test_withdrawal_partition_cost_retains_largest_holding(self):
        from verify_eth_projection import reconstruct
        first = "11" * 20
        second = "22" * 20
        rows = [(1, "active_ongoing", 1, "0x01" + "00"*11 + first),
                (2, "active_ongoing", 9, "0x02" + "00"*11 + first),
                (3, "active_exiting", 2, "0x00" + "00"*31),
                (4, "active_ongoing", 7, "0x01" + "00"*11 + second)]
        _, _, summary = reconstruct(rows)
        self.assertEqual(summary["group_count"], 3)
        self.assertEqual(summary["merge_moved_effective_gwei"], 1)
        self.assertEqual(summary["merge_moved_mass"], 1/19)

    def test_attainable_gini_curves_use_whole_label_moved_mass(self):
        from summarize_bitcoin_top1m_alpha_variation import (
            gini_desc, gini_head_collapse_curve, gini_tail_collapse_curve,
        )
        x = np.array([0.5, 0.3, 0.15, 0.05])
        budgets = np.array([0, 0.05, 0.15, 0.3, 0.5])
        for method, head_first in ((gini_head_collapse_curve, True),
                                   (gini_tail_collapse_curve, False)):
            moved, values = method(x, budgets)
            for i, budget in enumerate(budgets):
                if budget == 0:
                    expected = x
                else:
                    order = x if head_first else x[::-1]
                    count = max(k for k in range(1, len(x)+1)
                                if sum(order[:k])-max(order[:k]) <= budget + 1e-15)
                    expected = np.sort(np.r_[sum(order[:count]), order[count:]])[::-1]
                    expected_moved = sum(order[:count]) - max(order[:count])
                    self.assertAlmostEqual(moved[i], expected_moved)
                self.assertAlmostEqual(values[i], gini_desc(expected))

    def test_ancillary_zero_budget_intervals_are_exact(self):
        from summarize_attribution_hhi_two_models import model_rows
        x = np.arange(1, 101, dtype=np.float64)[::-1]
        x /= np.sum(x)
        row = model_rows("test", "test", x, np.array([0.0]))[0]
        self.assertEqual(row["merge_lower"], row["merge_upper_safe"])
        self.assertEqual(row["shift_lower_inf"], row["shift_upper_exact"])
        self.assertEqual(row["hhi_raw"], row["shift_lower_inf"])


if __name__ == "__main__":
    unittest.main()
