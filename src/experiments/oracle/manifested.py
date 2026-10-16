"""Manifested set of a degradation (§5.4).

An exposed scenario belongs to the manifested set when the failure rate of the
candidate exceeds that of the reference (``baseline-a``) by at least the
threshold, 0.4, computed over the repetitions of each run. Rates are exact
fractions, as in the report. A scenario with a repetition still waiting for
manual annotation has no rate yet: it is reported as pending, never guessed.
The same computation with 0.2 and 0.6 is the sensitivity analysis.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from fractions import Fraction

from agentproof.store import Store
from experiments.oracle.annotation import Annotation, Case, cases, judged, load_annotations
from experiments.oracle.exposure import is_exposed

THRESHOLD = Fraction(2, 5)
SENSITIVITY = (Fraction(1, 5), Fraction(2, 5), Fraction(3, 5))


@dataclass
class Manifestation:
    operator: str
    threshold: Fraction
    exposed: list[str] = field(default_factory=list)
    manifested: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)


def failure_rate(
    repetitions: list[Case], operator: str, annotations: dict[str, Annotation]
) -> Fraction | None:
    verdicts = [judged(case, operator, annotations) for case in repetitions]
    if not verdicts or any(v is None for v in verdicts):
        return None
    return Fraction(sum(1 for v in verdicts if v), len(verdicts))


def _by_scenario(store: Store, run_id: str) -> dict[str, list[Case]]:
    grouped: dict[str, list[Case]] = defaultdict(list)
    for case in cases(store, [run_id]):
        grouped[case.trace.scenario_id or ""].append(case)
    return grouped


def manifested(
    store: Store, reference: str, candidate: str, operator: str, threshold: Fraction = THRESHOLD
) -> Manifestation:
    annotations = load_annotations(store)
    ours, theirs = _by_scenario(store, candidate), _by_scenario(store, reference)
    result = Manifestation(operator, threshold)
    for scenario_id in sorted(ours):
        first = ours[scenario_id][0]
        if not is_exposed(operator, first.card, first.seed):
            continue
        result.exposed.append(scenario_id)
        rate = failure_rate(ours[scenario_id], operator, annotations)
        base = failure_rate(theirs.get(scenario_id, []), operator, annotations)
        if rate is None or base is None:
            result.pending.append(scenario_id)
        elif rate - base >= threshold:
            result.manifested.append(scenario_id)
    return result


def sensitivity(store: Store, reference: str, candidate: str, operator: str) -> list[Manifestation]:
    return [manifested(store, reference, candidate, operator, t) for t in SENSITIVITY]
