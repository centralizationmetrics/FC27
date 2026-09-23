"""Independent rational checks of the FC27 capped-observation formulas.

This finite enumeration supplements, and does not replace, the analytic proofs.
Run with Python 3; no third-party packages are needed.
"""

from fractions import Fraction as F
from itertools import accumulate


def partitions(n, cap=None):
    if n == 0:
        yield ()
        return
    for first in range(min(n, n if cap is None else cap), 0, -1):
        for rest in partitions(n - first, first):
            yield (first,) + rest


def ceil(x):
    return -(-x.numerator // x.denominator)


def cr(x, k):
    return sum(x[:k], F(0))


def nc(x, tau):
    return next(i for i, mass in enumerate(accumulate(x), 1) if mass >= tau)


def sp(x, p):
    return sum((v**p for v in x), F(0))


def gini(x):
    return sum((a - b for i, a in enumerate(x) for b in x[i + 1 :]), F(0)) / len(x)


def packed(head, total):
    q = total // head[-1]
    r = total - q * head[-1]
    return head + (head[-1],) * q + ((r,) if r else ())


def upper_shift(x, alpha):
    a = min(alpha, 1 - x[0])
    tail = list(x[1:])
    remaining = a
    for i in range(len(tail) - 1, -1, -1):
        take = min(tail[i], remaining)
        tail[i] -= take
        remaining -= take
    assert remaining == 0
    return (x[0] + a,) + tuple(t for t in tail if t)


def main():
    observations = 0
    checked = 0
    denominator = 16
    for ints in partitions(denominator):
        x = tuple(F(v, denominator) for v in ints)
        for n in range(1, len(x)):
            observations += 1
            head, tail = x[:n], x[n:]
            total, cap, m = sum(tail), head[-1], len(tail)
            prefix = sum(head)
            q, r = total // cap, total % cap
            xp = packed(head, total)
            d = sum(a - b for i, a in enumerate(head) for b in head[i + 1 :])
            emin = d + m * prefix - n * total
            emax = cap * q * (m - q) + r * (m - 1 - 2 * q)
            assert emin / len(x) <= gini(x) <= (emin + emax) / len(x)
            assert 0 <= emax / len(x) <= total
            assert gini(head + (total / m,) * m) == emin / len(x)
            checked += 3
            for k in range(1, len(x) + 3):
                if k <= n:
                    assert cr(x, k) == cr(head, k)
                else:
                    j = min(k - n, m)
                    assert prefix + j * total / m <= cr(x, k) <= prefix + min(total, j * cap)
                    assert cr(xp, k) == prefix + min(total, (k - n) * cap)
                checked += 1
            for tau_int in range(1, denominator + 1):
                tau = F(tau_int, denominator)
                value = nc(x, tau)
                if prefix >= tau:
                    assert value == nc(head, tau)
                else:
                    delta = tau - prefix
                    lower = n + (ceil(delta / cap) if tau < 1 else m)
                    upper = n + ceil(m * delta / total)
                    assert lower <= value <= upper
                    assert nc(head + (total / m,) * m, tau) == upper
                    assert nc(xp, tau) == n + ceil(delta / cap)
                checked += 1
            for p in (2, 3):
                assert sp(head, p) <= sp(x, p) <= sp(xp, p)
                assert sp(xp, p) == sp(head, p) + q * cap**p + r**p
                assert q * cap**p + r**p <= total**p
                checked += 3
            for alpha in (F(0), F(1, 20), F(1, 4), 1 - x[0], F(1)):
                wx, wp = upper_shift(x, alpha), upper_shift(xp, alpha)
                assert sum(wp) == 1
                for k in range(1, max(len(x), len(xp)) + 2):
                    assert cr(wx, k) == min(1, cr(x, k) + alpha)
                    assert cr(wp, k) == min(1, cr(xp, k) + alpha)
                    assert cr(wx, k) <= cr(wp, k)
                    checked += 3
                for p in (2, 3):
                    assert sp(wx, p) <= sp(wp, p)
                    checked += 1
    print(f"PASS: {observations} capped observations from every integer partition of {denominator}; {checked} rational checks.")
    print("Includes count-aware Gini, CR and threshold bounds, tau=1, exact cap multiples, p=2/3, and composed Shift alpha=0/saturation/1.")


if __name__ == "__main__":
    main()
