"""Agreement among annotators: Fleiss' κ, Krippendorff's α, Cohen's κ by pairs.

Cohen's κ is the one of the oracle validation (D-010), reused as is.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Hashable, Sequence
from fractions import Fraction
from itertools import combinations

from experiments.validation import cohen_kappa


def majority[T: Hashable](values: Sequence[T]) -> T | None:
    """The value more than half of the annotators gave, or None if there is none."""
    if not values:
        return None
    value, count = Counter(values).most_common(1)[0]
    return value if 2 * count > len(values) else None


def fleiss_kappa(items: Sequence[Sequence[Hashable]]) -> float | None:
    """Fleiss' κ over items rated by the same number of raters; None if chance explains all."""
    if not items:
        return None
    raters = len(items[0])
    if raters < 2 or any(len(item) != raters for item in items):
        raise ValueError("cada ítem necesita el mismo número de anotadores, al menos dos")
    counts = [Counter(item) for item in items]
    total = Fraction(len(items) * raters)
    shares = Counter()
    for count in counts:
        shares.update(count)
    chance = sum((Fraction(n) / total) ** 2 for n in shares.values())
    if chance == 1:
        return None
    observed = sum(
        Fraction(sum(n * n for n in count.values()) - raters, raters * (raters - 1))
        for count in counts
    ) / len(items)
    return float((observed - chance) / (1 - chance))


def _distances(totals: dict[int, Fraction], metric: str):
    if metric == "nominal":
        return lambda c, k: 0 if c == k else 1
    if metric == "interval":
        return lambda c, k: (c - k) ** 2
    if metric == "ordinal":
        ranks = sorted(totals)

        def ordinal(c: int, k: int) -> Fraction:
            low, high = sorted((ranks.index(c), ranks.index(k)))
            between = sum(totals[ranks[g]] for g in range(low, high + 1))
            return (between - (totals[c] + totals[k]) / 2) ** 2

        return ordinal
    raise ValueError(f"métrica desconocida: {metric}")


def krippendorff_alpha(
    units: Sequence[Sequence[int | None]], metric: str = "ordinal"
) -> float | None:
    """Krippendorff's α with missing values (None); None when it is undefined."""
    coincidences: Counter[tuple[int, int]] = Counter()
    for unit in units:
        values = [v for v in unit if v is not None]
        if len(values) < 2:
            continue  # a unit with one value cannot be paired
        for i, j in combinations(range(len(values)), 2):
            for c, k in ((values[i], values[j]), (values[j], values[i])):
                coincidences[c, k] += Fraction(1, len(values) - 1)
    totals: dict[int, Fraction] = {}
    for (c, _), o in coincidences.items():
        totals[c] = totals.get(c, Fraction(0)) + o
    delta = _distances(totals, metric)
    n = sum(totals.values())
    observed = sum(o * delta(c, k) for (c, k), o in coincidences.items())
    expected = sum(totals[c] * totals[k] * delta(c, k) for c in totals for k in totals)
    if not expected:
        return None
    return float(1 - (n - 1) * observed / expected)


def cohen_matrix(labels: dict[str, Sequence[Hashable]]) -> dict[tuple[str, str], float | None]:
    """Cohen's κ of every pair of annotators, over the items both labelled."""
    return {
        (a, b): cohen_kappa(list(zip(labels[a], labels[b], strict=True)))
        for a, b in combinations(sorted(labels), 2)
    }
