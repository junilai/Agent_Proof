"""E3: fidelity of the induction, rated by three annotators (pre-registration §6).

Each annotator rates every scenario against its seed conversation on a Likert
scale of 1 to 5 and says whether it would need a correction. The main metric is
the share of scenarios whose median is 4 or more. Agreement is Krippendorff's α
with ordinal weighting, over the three and over each pair, next to the full
distribution of ratings.
"""

from __future__ import annotations

from itertools import combinations
from statistics import mean, median

from pydantic import BaseModel

from experiments.f6.agreement import krippendorff_alpha, majority
from experiments.f6.labels import Rating

POINTS = (1, 2, 3, 4, 5)


class ScenarioE3(BaseModel):
    scenario_id: str
    ratings: dict[str, int]
    median: float
    corrections: dict[str, bool]
    needs_correction: bool


class Pair(BaseModel):
    exact: int
    within_one: int
    total: int
    mean_difference: float
    """Mean of the first annotator's rating minus the second's."""
    alpha_ordinal: float | None


class E3(BaseModel):
    scenarios: int
    median_at_least_4: int
    share_median_at_least_4: float
    alpha_ordinal: float | None
    pairs: dict[str, Pair]
    distribution: dict[str, dict[int, int]]
    needs_correction: int
    share_needs_correction: float
    per_scenario: list[ScenarioE3]


def _pair(first: list[int], second: list[int]) -> Pair:
    pairs = list(zip(first, second, strict=True))
    return Pair(
        exact=sum(a == b for a, b in pairs),
        within_one=sum(abs(a - b) <= 1 for a, b in pairs),
        total=len(pairs),
        mean_difference=mean(a - b for a, b in pairs),
        alpha_ordinal=krippendorff_alpha(pairs),
    )


def e3(labels: dict[str, dict[str, Rating]]) -> E3:
    annotators = sorted(labels)
    found = []
    for scenario_id in sorted(labels[annotators[0]]):
        ratings = {a: labels[a][scenario_id].likert for a in annotators}
        corrections = {a: labels[a][scenario_id].correction for a in annotators}
        found.append(
            ScenarioE3(
                scenario_id=scenario_id,
                ratings=ratings,
                median=median(ratings.values()),
                corrections=corrections,
                needs_correction=bool(majority(list(corrections.values()))),
            )
        )
    column = {a: [s.ratings[a] for s in found] for a in annotators}
    distribution = {a: {p: column[a].count(p) for p in POINTS} for a in annotators}
    distribution["todos"] = {p: sum(d[p] for d in distribution.values()) for p in POINTS}
    high = sum(s.median >= 4 for s in found)
    corrected = sum(s.needs_correction for s in found)
    return E3(
        scenarios=len(found),
        median_at_least_4=high,
        share_median_at_least_4=high / len(found),
        alpha_ordinal=krippendorff_alpha([list(s.ratings.values()) for s in found]),
        pairs={f"{a}-{b}": _pair(column[a], column[b]) for a, b in combinations(annotators, 2)},
        distribution=distribution,
        needs_correction=corrected,
        share_needs_correction=corrected / len(found),
        per_scenario=found,
    )
