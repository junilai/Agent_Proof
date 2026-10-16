"""Statistics of the regression criterion (§5.5).

Fisher's exact test compares the pass counts of a scenario in two runs, and
Benjamini-Hochberg corrects for comparing many scenarios at once. Both work on
exact fractions: the thresholds of the correction sit close together (with
twenty scenarios, three joint regressions need p <= 0.0075 and four need
p <= 0.01, while the extreme case with R = 5 gives 0.0079), so a rounding error
could change a decision.
"""

from __future__ import annotations

from fractions import Fraction
from math import comb

ALPHA = Fraction(1, 20)


def fisher_exact(passed_a: int, total_a: int, passed_b: int, total_b: int) -> Fraction:
    """Two-sided p-value: every table with the same margins as likely as the observed or less."""
    passed, total = passed_a + passed_b, total_a + total_b
    if total_a == 0 or total_b == 0:
        return Fraction(1)

    def probability(x: int) -> Fraction:
        return Fraction(comb(total_a, x) * comb(total_b, passed - x), comb(total, passed))

    observed = probability(passed_a)
    tables = range(max(0, passed - total_b), min(total_a, passed) + 1)
    return sum((p for p in map(probability, tables) if p <= observed), Fraction(0))


def benjamini_hochberg(p_values: dict[str, Fraction], alpha: Fraction = ALPHA) -> set[str]:
    """Rejected hypotheses: the k smallest p-values, for the largest k with p(k) <= k*alpha/m."""
    ranked = sorted(p_values, key=lambda key: (p_values[key], key))
    m = len(ranked)
    k = max((i for i in range(1, m + 1) if p_values[ranked[i - 1]] <= i * alpha / m), default=0)
    return set(ranked[:k])
