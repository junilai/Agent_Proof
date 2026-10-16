"""Reliability, raw failure rates and effect size (§5.4, §5.5, §5.8).

pass^k is the probability that k repetitions of a scenario all pass, estimated
without bias as C(c, k) / C(n, k) and averaged over the scenarios (D-006). The
joint distribution of failure rates per scenario is reported so that any other
classification can be rebuilt from the raw data (§5.4). The effect size, the
only measure for D3 and the companion of family B, is the drop of the mean pass
rate from the reference to the candidate (D-006).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction
from math import comb

from agentproof.report import compare_runs
from agentproof.store import Store
from experiments.oracle.annotation import load_annotations, seed_and_card
from experiments.oracle.exposure import is_exposed
from experiments.oracle.manifested import THRESHOLD, by_scenario, failure_rate, manifested


def pass_hat_k(store: Store, run_id: str) -> dict[int, Fraction]:
    """pass^k for k = 1..R; a scenario with fewer than k valid repetitions sits that k out."""
    counts: dict[str, list[bool]] = defaultdict(list)
    for verdict in store.verdicts(run_id):
        counts[verdict.scenario_id].append(verdict.passed)
    result = {}
    for k in range(1, store.manifest(run_id).repetitions + 1):
        estimates = [
            Fraction(comb(sum(v), k), comb(len(v), k)) for v in counts.values() if len(v) >= k
        ]
        if estimates:
            result[k] = sum(estimates, Fraction(0)) / len(estimates)
    return result


@dataclass(frozen=True)
class JointRate:
    scenario_id: str
    reference: Fraction | None
    candidate: Fraction | None
    exposed: bool
    manifested: bool
    status: str | None
    """What the report declared; None when the scenario could not be tested."""


def joint_failure_rates(
    store: Store, reference: str, candidate: str, operator: str, threshold: Fraction = THRESHOLD
) -> list[JointRate]:
    """Failure rates under the operator's predicate in every scenario, exposed or not."""
    annotations = load_annotations(store)
    seeds = {seed.trace_id: seed for seed in store.seeds()}
    ours, theirs = by_scenario(store, candidate), by_scenario(store, reference)
    truth = manifested(store, reference, candidate, operator, threshold)
    report = {c.scenario_id: c for c in compare_runs(store, reference, candidate).comparisons}
    rows = []
    for scenario_id in sorted(ours.keys() | theirs.keys()):
        seed, card = seed_and_card(seeds, scenario_id)
        tested = report.get(scenario_id)
        rows.append(
            JointRate(
                scenario_id=scenario_id,
                reference=failure_rate(theirs.get(scenario_id, []), operator, annotations),
                candidate=failure_rate(ours.get(scenario_id, []), operator, annotations),
                exposed=bool(is_exposed(operator, card, seed)),
                manifested=scenario_id in truth.manifested,
                status=tested.status if tested and tested.p_value is not None else None,
            )
        )
    return rows


def failure_frequencies(rows: list[JointRate]) -> dict[Fraction, int]:
    """How many scenarios the candidate fails 0/5, 1/5, ..., 5/5 of the times."""
    counted = Counter(row.candidate for row in rows if row.candidate is not None)
    return dict(sorted(counted.items()))


@dataclass(frozen=True)
class EffectSize:
    reference: Fraction
    candidate: Fraction
    per_scenario: dict[str, Fraction]
    """Drop of the pass rate in each scenario, so the mean does not hide where it comes from."""

    @property
    def drop(self) -> Fraction:
        return self.reference - self.candidate


def effect_size(
    store: Store, reference: str, candidate: str, scenarios: list[str] | None = None
) -> EffectSize | None:
    """Drop of the mean pass rate, over the suite or over the scenarios given."""
    rated = [
        c
        for c in compare_runs(store, reference, candidate).comparisons
        if c.drop is not None and (scenarios is None or c.scenario_id in scenarios)
    ]
    if not rated:
        return None
    return EffectSize(
        reference=sum((c.baseline.rate or 0 for c in rated), Fraction(0)) / len(rated),
        candidate=sum((c.candidate.rate or 0 for c in rated), Fraction(0)) / len(rated),
        per_scenario={c.scenario_id: c.drop or Fraction(0) for c in rated},
    )
