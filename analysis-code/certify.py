#!/usr/bin/env python3
"""Certificate endpoint toolbox for share vectors.

The functions in this file mirror the paper's reporting rules.  They are small
and explicit rather than optimized: the intended use is to make certificates
auditable from an input vector and a stated model parameter.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Iterable


class UnsupportedMetricCertificate(ValueError):
    pass


def normalize(xs: Iterable[float]) -> list[float]:
    vals = sort_shares(xs)
    total = math.fsum(vals)
    return sorted((x / total for x in vals), reverse=True)


def sort_shares(xs: Iterable[float]) -> list[float]:
    vals = [float(x) for x in xs]
    if any(not math.isfinite(x) or x < 0 for x in vals):
        raise ValueError("shares must be finite and nonnegative")
    vals = [x for x in vals if x > 0]
    if not vals:
        raise ValueError("share vector must have positive entries")
    return sorted(vals, reverse=True)


def load_vector(path: str | Path, *, normalize_input: bool = False) -> list[float]:
    path = Path(path)
    text = path.read_text().strip()
    vals: list[float] = []
    if path.suffix == ".json":
        obj = json.loads(text)
        if isinstance(obj, list):
            vals = [float(x) for x in obj]
        else:
            for key in ("shares", "balances", "values"):
                if key in obj:
                    vals = [float(x) for x in obj[key]]
                    break
    else:
        for row in csv.reader(text.splitlines()):
            for cell in row:
                try:
                    vals.append(float(cell))
                    break
                except ValueError:
                    continue
    return normalize(vals) if normalize_input else sort_shares(vals)


def cr(x: list[float], k: int) -> float:
    return math.fsum(x[: min(k, len(x))])


def reaches(value: float, threshold: float) -> bool:
    """Compare a computed prefix at floating-point arithmetic precision.

    The allowance is eight ULPs, not a user-scale tolerance: a genuine
    threshold gap (for example 1e-12 on unit mass) remains a gap.
    """
    tolerance = 8 * max(math.ulp(value), math.ulp(threshold))
    return value >= threshold or threshold - value <= tolerance


def ceil_ratio(numerator: float, denominator: float) -> int:
    quotient = numerator / denominator
    below = math.floor(quotient)
    return below if reaches(float(below), quotient) else below + 1


def nc(x: list[float], tau: float) -> float:
    acc = 0.0
    correction = 0.0
    for i, val in enumerate(x, 1):
        adjusted = val - correction
        updated = acc + adjusted
        correction = (updated - acc) - adjusted
        acc = updated
        if reaches(acc, tau):
            return float(i)
    return math.inf


def power_sum(x: list[float], p: float) -> float:
    return math.fsum(v**p for v in x)


def hhi(x: list[float]) -> float:
    return power_sum(x, 2.0)


def level_cap(x: list[float], amount: float) -> list[float]:
    if amount <= 0:
        return list(x)
    total = sum(x)
    if amount >= total:
        return [0.0 for _ in x]
    lo, hi = 0.0, x[0]
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        drained = sum(max(v - mid, 0.0) for v in x)
        if drained > amount:
            lo = mid
        else:
            hi = mid
    cap = 0.5 * (lo + hi)
    return [min(v, cap) for v in x]


def tail_trim(x: list[float], amount: float) -> list[float]:
    out = list(x)
    remaining = amount
    for i in range(len(out) - 1, -1, -1):
        if remaining <= 0:
            break
        take = min(out[i], remaining)
        out[i] -= take
        remaining -= take
    return out


def declared_share_merge(declared: list[float], residual: list[float]) -> list[float]:
    return sort_shares([*declared, *residual])


def cap_cr_interval(visible: list[float], tail_mass: float, k: int) -> tuple[float, float]:
    if k <= len(visible):
        val = cr(visible, k)
        return val, val
    cap = visible[-1]
    return cr(visible, k), sum(visible) + min(tail_mass, (k - len(visible)) * cap)


def cap_nc_interval(
    visible: list[float], tail_mass: float, tau: float, omitted_count: int | None = None
) -> tuple[float, float]:
    prefix = math.fsum(visible)
    if reaches(prefix, tau):
        val = nc(visible, tau)
        return val, val
    cap = visible[-1]
    delta = tau - prefix
    lower = len(visible) + ceil_ratio(delta, cap)
    if omitted_count is None:
        return float(lower), math.inf
    if tau == 1.0:
        # Every omitted label is positive, so reaching all mass requires all
        # N + M labels, irrespective of how their positive shares are split.
        exact = float(len(visible) + omitted_count)
        return exact, exact
    upper = len(visible) + ceil_ratio(omitted_count * delta, tail_mass)
    return float(lower), float(upper)


def cap_power_sum_interval(visible: list[float], tail_mass: float, p: float) -> tuple[float, float]:
    cap = visible[-1]
    q = math.floor(tail_mass / cap)
    # A quotient just below an integer may round up to that integer; clamp
    # the resulting tiny negative remainder before a fractional power.
    r = max(0.0, tail_mass - q * cap)
    base = power_sum(visible, p)
    return base, base + q * cap**p + r**p


def cap_shift_power_interval(
    visible: list[float], tail_mass: float, alpha: float, p: float
) -> tuple[float, float]:
    """Sharp power-sum endpoints after mass-only capping and then Shift.

    TailTrim on the packed completion is evaluated by multiplicities, so a
    very small visible cap does not require constructing a huge tail vector.
    Inputs follow the paper: sorted positive visible shares, total mass one,
    a nonnegative tail, alpha in [0,1], and p > 1.
    """
    lower = power_sum(level_cap(visible, min(alpha, math.fsum(visible))), p)
    cap = visible[-1]
    q = math.floor(tail_mass / cap)
    remainder = max(0.0, tail_mass - q * cap)
    amount = min(alpha, 1.0 - visible[0])
    # The remainder and then the q capped coordinates are the smallest
    # coordinates of the packed completion, before the remaining head.
    remainder_left = max(0.0, remainder - amount)
    after_remainder = max(0.0, amount - remainder)
    if after_remainder >= q * cap:
        packed_tail_power = remainder_left**p
        head_left = tail_trim(visible[1:], after_remainder - q * cap)
    else:
        fully_removed = math.floor(after_remainder / cap)
        partial = after_remainder - fully_removed * cap
        capped_left = q - fully_removed
        packed_tail_power = (
            (capped_left - 1) * cap**p + (cap - partial)**p + remainder_left**p
        )
        head_left = visible[1:]
    upper = (visible[0] + amount)**p + power_sum(head_left, p) + packed_tail_power
    return lower, upper


def merge_power_sum_budget(x: list[float], p: float, rho: float) -> tuple[float, float]:
    """Safe Merge interval for a budget on mass moved in whole-label merges.

    A group retains its largest original label; the other labels' entire
    shares move to it. The total moved mass is bounded by rho. Coarsening
    cannot decrease S_p, and every such merge is a feasible Shift. Its sharp
    Shift upper endpoint is therefore safe here, but need not be attainable
    by whole-label merges.
    """
    return power_sum(x, p), shift_power_sum_upper(x, rho, p)


def merge_cr_budget(x: list[float], rho: float, k: int) -> tuple[float, float]:
    """Safe bounds from coarsening monotonicity and Merge's Shift embedding."""
    base = cr(x, k)
    return base, min(1.0, base + rho)


def merge_nc_budget(x: list[float], rho: float, tau: float) -> tuple[float, float]:
    """Safe bounds from coarsening monotonicity and Merge's Shift embedding."""
    return nc(x, max(0.0, tau - rho)), nc(x, tau)


def shift_cr_interval(x: list[float], alpha: float, k: int) -> tuple[float, float]:
    return cr(level_cap(x, alpha), k), min(1.0, cr(x, k) + alpha)


def shift_nc_interval(x: list[float], alpha: float, tau: float) -> tuple[float, float]:
    lower = nc(x, max(0.0, tau - alpha))
    if alpha > 0 and not reaches(1.0 - alpha, tau):
        return lower, math.inf
    drained = level_cap(x, alpha)
    upper = nc(drained, tau)
    return lower, upper


def shift_power_sum_upper(x: list[float], alpha: float, p: float) -> float:
    """Sharp Shift maximum; also a safe moved-mass Merge upper bound."""
    head = x[0]
    a = min(alpha, 1.0 - head)
    upper_vec = [head + a, *tail_trim(x[1:], a)]
    return power_sum(upper_vec, p)


def shift_power_sum_interval(x: list[float], alpha: float, p: float) -> tuple[float, float]:
    lower = power_sum(level_cap(x, alpha), p)
    return lower, shift_power_sum_upper(x, alpha, p)


def shift_hhi_interval(x: list[float], alpha: float) -> tuple[float, float]:
    return shift_power_sum_interval(x, alpha, 2.0)


def residual_source_shift_hhi(
    declared: list[float], residual: list[float], alpha_res: float
) -> tuple[float, float]:
    a = min(alpha_res, sum(residual))
    lower = power_sum(declared, 2.0) + power_sum(level_cap(residual, a), 2.0)
    base = declared_share_merge(declared, tail_trim(residual, a))
    base[0] += a
    upper = hhi(sort_shares(base))
    return lower, upper


def unresolved_merge_intervals(
    fixed: list[float], unresolved: list[float], k: int, tau: float
) -> dict[str, tuple[float, float]]:
    """Sharp conditional Merge bounds, with every endpoint attained.

    Each unresolved whole holding may join a fixed controller or other
    unresolved holdings. Distinct fixed controllers cannot be combined.
    All shares use the full total; no holding may be split.
    """
    values = list(fixed) + list(unresolved)
    if (not fixed or any(not math.isfinite(v) or v <= 0 for v in values)
            or not isinstance(k, int) or k < 1 or not 0 < tau <= 1
            or not math.isclose(math.fsum(values), 1, abs_tol=1e-12, rel_tol=0)):
        raise ValueError('positive fixed and unresolved holdings must sum to one')
    fixed = sorted(fixed, reverse=True)
    baseline = sorted(values, reverse=True)
    most_concentrated = [fixed[0] + math.fsum(unresolved)] + fixed[1:]
    return {'hhi': (hhi(baseline), hhi(most_concentrated)),
            'cr': (cr(baseline, k), cr(most_concentrated, k)),
            'nc': (nc(most_concentrated, tau), nc(baseline, tau))}


def unsupported_descriptive_metric(metric: str) -> None:
    if metric in {"gini", "entropy", "zipf"}:
        raise UnsupportedMetricCertificate(
            f"{metric} is descriptive unless omitted-count, tail-shape, or ownership-count assumptions are supplied"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute decentralization certificate endpoints.")
    parser.add_argument("--input", help="CSV/TXT/JSON share vector")
    parser.add_argument("--declared", help="Declared-share vector for residual-shift")
    parser.add_argument("--residual", help="Residual share vector for residual-shift")
    parser.add_argument("--metric", required=True, choices=["cr", "nc", "hhi", "sp", "gini", "entropy", "zipf"])
    parser.add_argument(
        "--model", required=True, choices=["cap", "merge", "shift", "residual-shift"],
        help="merge reports safe outer bounds: its power-sum upper bound uses the Shift relaxation, not exact whole-label optimization",
    )
    parser.add_argument("--rho", type=float, help="maximum mass moved by whole-label Merge")
    parser.add_argument("--alpha", type=float)
    parser.add_argument("--tail-mass", type=float)
    parser.add_argument("--omitted-count", type=int)
    parser.add_argument("--p", type=float, default=2.0)
    parser.add_argument("--k", type=int, default=10_000)
    parser.add_argument("--tau", type=float, default=0.5)
    parser.add_argument("--normalize", action="store_true", help="Normalize complete Merge/Shift input weights to one")
    args = parser.parse_args()

    for name in ("rho", "alpha", "tail_mass"):
        value = getattr(args, name)
        if value is not None and (not math.isfinite(value) or not 0.0 <= value <= 1.0):
            parser.error(f"--{name.replace('_', '-')} must lie in [0,1]")
    if not math.isfinite(args.p) or args.p <= 1:
        parser.error("--p must be finite and greater than 1")
    if args.k < 1:
        parser.error("--k must be positive")
    if not math.isfinite(args.tau) or not 0.0 < args.tau <= 1.0:
        parser.error("--tau must lie in (0,1]")
    if args.omitted_count is not None and args.omitted_count < 0:
        parser.error("--omitted-count must be nonnegative")
    exponent = 2.0 if args.metric == "hhi" else args.p

    if args.normalize and args.model in {"cap", "residual-shift"}:
        parser.error("--normalize is supported only for complete Merge/Shift inputs; supply shares on one common denominator")

    def load_cli_vector(path: str, *, normalize_input: bool = False) -> list[float]:
        try:
            return load_vector(path, normalize_input=normalize_input)
        except (OSError, ValueError, TypeError, OverflowError) as exc:
            parser.error(f"invalid share vector: {exc}")

    def require_unit_mass(total: float, description: str) -> None:
        if not math.isfinite(total) or not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=8 * math.ulp(1.0)):
            hint = "; use --normalize for raw weights" if args.model in {"merge", "shift"} else ""
            parser.error(f"{description} must sum to 1 (received {total:.17g}){hint}")

    unsupported_descriptive_metric(args.metric)

    if args.model == "residual-shift":
        if not args.declared or not args.residual or args.alpha is None:
            raise SystemExit("residual-shift requires --declared, --residual, and --alpha")
        declared = load_cli_vector(args.declared)
        residual = load_cli_vector(args.residual)
        require_unit_mass(math.fsum(declared) + math.fsum(residual), "declared and residual shares together")
        if args.metric != "hhi":
            raise SystemExit("CLI residual-shift currently reports HHI; use functions for CR/NC variants")
        lo, hi = residual_source_shift_hhi(declared, residual, args.alpha)
    else:
        if not args.input:
            raise SystemExit("--input is required")
        x = load_cli_vector(args.input, normalize_input=args.normalize)
        if args.model == "cap":
            if args.tail_mass is None:
                raise SystemExit("cap model requires --tail-mass")
            require_unit_mass(math.fsum(x) + args.tail_mass, "visible shares plus omitted mass")
            if args.omitted_count is not None:
                if (args.omitted_count == 0) != (args.tail_mass == 0):
                    parser.error("omitted positive-label count must be zero exactly when omitted mass is zero")
                if not reaches(args.omitted_count * x[-1], args.tail_mass):
                    parser.error("omitted count cannot hold the omitted mass under the last visible share cap")
            if args.metric == "cr":
                lo, hi = cap_cr_interval(x, args.tail_mass, args.k)
            elif args.metric == "nc":
                lo, hi = cap_nc_interval(x, args.tail_mass, args.tau, args.omitted_count)
            else:
                lo, hi = cap_power_sum_interval(x, args.tail_mass, exponent)
        elif args.model == "merge":
            require_unit_mass(math.fsum(x), "complete shares")
            if args.rho is None:
                raise SystemExit("merge model requires --rho")
            if args.metric == "cr":
                lo, hi = merge_cr_budget(x, args.rho, args.k)
            elif args.metric == "nc":
                lo, hi = merge_nc_budget(x, args.rho, args.tau)
            else:
                lo, hi = merge_power_sum_budget(x, exponent, args.rho)
        else:
            require_unit_mass(math.fsum(x), "complete shares")
            if args.alpha is None:
                raise SystemExit("shift model requires --alpha")
            if args.metric == "cr":
                lo, hi = shift_cr_interval(x, args.alpha, args.k)
            elif args.metric == "nc":
                lo, hi = shift_nc_interval(x, args.alpha, args.tau)
            else:
                lo, hi = shift_power_sum_interval(x, args.alpha, exponent)

    print(json.dumps({"lower": lo, "upper": hi}, indent=2))


if __name__ == "__main__":
    main()
