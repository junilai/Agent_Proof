"""Confusion matrix, TPR, FPR and the negative control (§5.5).

A scenario is positive when the oracle placed it in the manifested set of the
operator, and negative otherwise, whether or not it was exposed. It counts as
detected only when the report declared a regression (D-006): a weak signal is
listed apart. The four cells partition every scenario of the comparison; a
scenario that cannot be labelled because a run has no valid repetition is a
deviation from the protocol and is listed, never dropped silently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from agentproof.report import compare_runs
from agentproof.store import Store
from experiments.oracle.manifested import SENSITIVITY, THRESHOLD, manifested
from experiments.oracle.predicates import OPERATORS_WITH_PREDICATE


def _rate(part: int, whole: int) -> Fraction | None:
    return Fraction(part, whole) if whole else None


@dataclass
class Detection:
    operator: str
    threshold: Fraction
    true_positives: list[str] = field(default_factory=list)
    false_negatives: list[str] = field(default_factory=list)
    false_positives: list[str] = field(default_factory=list)
    true_negatives: list[str] = field(default_factory=list)
    exposed: list[str] = field(default_factory=list)
    weak_signals: list[str] = field(default_factory=list)
    deviations: list[str] = field(default_factory=list)

    @property
    def tpr(self) -> Fraction | None:
        return _rate(len(self.true_positives), len(self.true_positives + self.false_negatives))

    @property
    def fpr(self) -> Fraction | None:
        return _rate(len(self.false_positives), len(self.false_positives + self.true_negatives))

    @property
    def false_positives_unexposed(self) -> list[str]:
        return [s for s in self.false_positives if s not in self.exposed]

    @property
    def false_positives_exposed(self) -> list[str]:
        """Exposed scenarios the degradation changed without making them worse."""
        return [s for s in self.false_positives if s in self.exposed]


def _scenarios(store: Store, *run_ids: str) -> list[str]:
    return sorted({t.scenario_id or "" for r in run_ids for t in store.run_traces(r)})


def detection(
    store: Store, reference: str, candidate: str, operator: str, threshold: Fraction = THRESHOLD
) -> Detection:
    if operator not in OPERATORS_WITH_PREDICATE:
        raise ValueError(f"{operator} has no exposed set: report it only as an effect size")
    truth = manifested(store, reference, candidate, operator, threshold)
    if truth.pending:
        raise ValueError(f"{len(truth.pending)} scenario(s) still waiting for manual annotation")
    report = compare_runs(store, reference, candidate)
    tested = {c.scenario_id: c for c in report.comparisons if c.p_value is not None}
    result = Detection(operator, threshold, exposed=truth.exposed)
    result.weak_signals = [c.scenario_id for c in report.weak_signals]
    for scenario_id in _scenarios(store, reference, candidate):
        if scenario_id in truth.incomplete or scenario_id not in tested:
            result.deviations.append(scenario_id)
            continue
        positive, flagged = scenario_id in truth.manifested, tested[scenario_id].regressed
        cell = {
            (True, True): result.true_positives,
            (True, False): result.false_negatives,
            (False, True): result.false_positives,
            (False, False): result.true_negatives,
        }[positive, flagged]
        cell.append(scenario_id)
    return result


def sensitivity(store: Store, reference: str, candidate: str, operator: str) -> list[Detection]:
    return [detection(store, reference, candidate, operator, t) for t in SENSITIVITY]


@dataclass
class NegativeControl:
    """Two runs of the same baseline: every scenario flagged is a false positive."""

    flagged: list[str]
    weak_signals: list[str]
    compared: int

    @property
    def fpr(self) -> Fraction | None:
        return _rate(len(self.flagged), self.compared)


def negative_control(store: Store, reference: str, control: str) -> NegativeControl:
    report = compare_runs(store, reference, control)
    return NegativeControl(
        flagged=[c.scenario_id for c in report.regressions],
        weak_signals=[c.scenario_id for c in report.weak_signals],
        compared=sum(1 for c in report.comparisons if c.p_value is not None),
    )
