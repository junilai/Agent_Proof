"""What each figure and table shows, read from results/ without calling any model.

The runs of each experiment are the ones docs/e1.md and docs/e4.md analyse.
The human validation is read from results/f6/analisis.json, which
``python -m experiments.f6`` writes; only the oracle's own reading of the
audited traces is computed here, with the rules installed.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction

from agentproof.cost import ComponentCost, cost_summary
from agentproof.store import Store
from experiments.analysis.detection import detection
from experiments.analysis.reliability import JointRate, joint_failure_rates, pass_hat_k
from experiments.f6.audit import _cases
from experiments.figures.metrics import Classification, classification
from experiments.oracle.predicates import evidence
from experiments.validation import _as_label as found_decision


@dataclass(frozen=True)
class Experiment:
    name: str
    framework: str
    reference: str
    candidates: dict[str, str]
    """Operator -> run."""
    control: str | None = None

    @property
    def runs(self) -> list[str]:
        others = [self.control] if self.control else []
        return [self.reference, *others, *self.candidates.values()]


E1 = Experiment(
    name="E1",
    framework="SDK",
    reference="baseline-a-20261018-000105",
    control="baseline-b-20261018-053952",
    candidates={
        "d1": "d1-20261018-044843",
        "d2": "d2-20261018-053954",
        "d3": "d3-20261018-053958",
        "d4": "d4-20261018-044845",
        "d5": "d5-20261018-053956",
        "d6": "d6-20261018-044847",
    },
)
E4 = Experiment(
    name="E4",
    framework="LangGraph",
    reference="baseline-a-20261111-000112",
    candidates={
        "d1": "d1-20261111-000112",
        "d4": "d4-20261111-000112",
        "d6": "d6-20261111-000112",
    },
)
EXPERIMENTS = (E1, E4)
WITH_PREDICATE = ("d1", "d2", "d4", "d5", "d6")
"""D3 has no exposed set: it is reported only as an effect size."""


def classifications(store: Store) -> list[Classification]:
    return [
        classification(detection(store, exp.reference, run, op), exp.framework)
        for exp in EXPERIMENTS
        for op, run in exp.candidates.items()
        if op in WITH_PREDICATE
    ]


def joint_rates(store: Store, exp: Experiment, operator: str) -> list[JointRate]:
    return joint_failure_rates(store, exp.reference, exp.candidates[operator], operator)


def cards(store: Store) -> dict[str, str]:
    """Scenario -> card, the name the thesis gives each scenario."""
    return {f"sc-{seed.trace_id}": seed.card_id or "" for seed in store.seeds()}


def approval_by_scenario(store: Store, exp: Experiment) -> dict[str, dict[str, Fraction]]:
    """Run label -> scenario -> share of judged repetitions that passed."""
    labels = {exp.reference: "línea base"} | {run: op.upper() for op, run in exp.candidates.items()}
    if exp.control:
        labels[exp.control] = "control"
    table: dict[str, dict[str, Fraction]] = {}
    for run, label in labels.items():
        passed: dict[str, list[bool]] = defaultdict(list)
        for verdict in store.verdicts(run):
            passed[verdict.scenario_id].append(verdict.passed)
        table[label] = {s: Fraction(sum(v), len(v)) for s, v in passed.items()}
    return table


def pass_k(store: Store, exp: Experiment) -> dict[str, dict[int, Fraction]]:
    runs = {"línea base": exp.reference} | {
        op.upper(): run for op, run in exp.candidates.items() if op in ("d1", "d4", "d6")
    }
    return {label: pass_hat_k(store, run) for label, run in runs.items()}


def _analysis(store: Store) -> dict:
    return json.loads((store.root / "results" / "f6" / "analisis.json").read_text("utf-8"))


def judge_matrix(store: Store) -> dict[tuple[bool, bool], int]:
    """(judge passed, majority approved) -> pairs of E2."""
    traces = _analysis(store)["e2"]["traces"]
    return dict(Counter((t["judge_passed"], t["majority_approved"]) for t in traces))


def audit_matrix(store: Store) -> dict[tuple[str, str], int]:
    """(majority decision, oracle decision) -> audited traces with a decision to read."""
    majority = {t["key"]: t["majority"]["decision"] for t in _analysis(store)["audit"]["traces"]}
    found = Counter()
    for case, _ in _cases(store):
        key = f"{case.run_id}/{case.trace.trace_id}"
        if key not in majority or not case.card.has_decision:
            continue
        oracle = found_decision(evidence(case.card, case.trace).decision)
        found[(majority[key] or "sin mayoría", oracle)] += 1
    return dict(found)


def ratings(store: Store) -> dict[str, dict[int, int]]:
    """Annotator -> Likert score -> scenarios of E3."""
    distribution = _analysis(store)["e3"]["distribution"]
    return {
        who: {int(score): n for score, n in counts.items()}
        for who, counts in distribution.items()
        if who != "todos"
    }


def costs(store: Store, exp: Experiment) -> list[ComponentCost]:
    """Simulated user, agent and judge of the experiment's runs; the inducer is the corpus's."""
    return [c for c in cost_summary(store, exp.runs) if c.name != "inductor"]
