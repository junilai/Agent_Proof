"""E2: agreement of the automatic judge with three annotators (pre-registration §6).

Each annotator marks every criterion of the scenario; a trace is approved when
all its criteria are met. The approval of the majority is the one most
annotators gave. The judge is compared with it per trace and per criterion. The
sample is stratified by the judge's verdict (D-011), so the natural approval of
E1 is reported apart.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from pydantic import BaseModel

from agentproof.store import Store
from experiments.f6.agreement import cohen_matrix, fleiss_kappa, majority
from experiments.f6.labels import TraceLabel
from experiments.samples import e1_runs
from experiments.validation import cohen_kappa

SAMPLE = ("results", "samples", "e2.json")


class Agreement(BaseModel):
    agreed: int
    total: int
    kappa: float | None


def agreement(pairs: Sequence[tuple[object, object]]) -> Agreement:
    pairs = list(pairs)
    return Agreement(
        agreed=sum(a == b for a, b in pairs), total=len(pairs), kappa=cohen_kappa(pairs)
    )


def pairwise(labels: dict[str, Sequence[object]]) -> dict[str, float | None]:
    return {f"{a}-{b}": kappa for (a, b), kappa in cohen_matrix(labels).items()}


class Natural(BaseModel):
    passed: int
    judged: int
    share: float


def natural_approval(store: Store) -> Natural:
    """The judge's approvals over every judged trace of E1."""
    verdicts = [v for run_id in e1_runs(store) for v in store.verdicts(run_id)]
    passed = sum(v.passed for v in verdicts)
    return Natural(passed=passed, judged=len(verdicts), share=passed / len(verdicts))


class TraceE2(BaseModel):
    key: str
    stratum: str
    approvals: dict[str, bool]
    majority_approved: bool
    criteria_majority: list[bool]
    judge_passed: bool
    judge_criteria: list[bool]


class Stratum(BaseModel):
    pairs: int
    majority_approved: int
    judge_agreed: int


class E2(BaseModel):
    pairs: int
    approvals: dict[str, int]
    fleiss_approval: float | None
    fleiss_criteria: float | None
    cohen_approval: dict[str, float | None]
    cohen_criteria: dict[str, float | None]
    majority_approved: int
    judge_approval: Agreement
    judge_criteria: Agreement
    strata: dict[str, Stratum]
    approval_of_majority_criteria_differs: int
    """Traces where all criteria met by majority gives another approval than the majority."""
    natural: Natural
    traces: list[TraceE2]


def _sample(store: Store) -> list[dict]:
    return json.loads(store.root.joinpath(*SAMPLE).read_text(encoding="utf-8"))["pairs"]


def _trace(store: Store, pair: dict, labels: dict[str, dict[str, TraceLabel]]) -> TraceE2:
    key = f"{pair['run_id']}/{pair['trace_id']}"
    verdict = next(v for v in store.verdicts(pair["run_id"]) if v.trace_id == pair["trace_id"])
    judged = [c.met for c in verdict.criteria]
    read = {a: list(labels[a][key].criteria) for a in sorted(labels)}
    if any(len(criteria) != len(judged) for criteria in read.values()):
        raise ValueError(f"{key}: el evaluador juzgó {len(judged)} criterios")
    approvals = {a: all(criteria) for a, criteria in read.items()}
    return TraceE2(
        key=key,
        stratum=pair["stratum"],
        approvals=approvals,
        majority_approved=bool(majority(list(approvals.values()))),
        criteria_majority=[bool(majority(votes)) for votes in zip(*read.values(), strict=True)],
        judge_passed=verdict.passed,
        judge_criteria=judged,
    )


def e2(store: Store, labels: dict[str, dict[str, TraceLabel]]) -> E2:
    traces = [_trace(store, pair, labels) for pair in _sample(store)]
    annotators = sorted(labels)
    by_criterion = [
        (t, i, {a: labels[a][t.key].criteria[i] for a in annotators})
        for t in traces
        for i in range(len(t.judge_criteria))
    ]
    strata = {}
    for name in dict.fromkeys(t.stratum for t in traces):
        inside = [t for t in traces if t.stratum == name]
        strata[name] = Stratum(
            pairs=len(inside),
            majority_approved=sum(t.majority_approved for t in inside),
            judge_agreed=sum(t.majority_approved == t.judge_passed for t in inside),
        )
    return E2(
        pairs=len(traces),
        approvals={a: sum(t.approvals[a] for t in traces) for a in annotators},
        fleiss_approval=fleiss_kappa([list(t.approvals.values()) for t in traces]),
        fleiss_criteria=fleiss_kappa([list(votes.values()) for _, _, votes in by_criterion]),
        cohen_approval=pairwise({a: [t.approvals[a] for t in traces] for a in annotators}),
        cohen_criteria=pairwise(
            {a: [votes[a] for _, _, votes in by_criterion] for a in annotators}
        ),
        majority_approved=sum(t.majority_approved for t in traces),
        judge_approval=agreement((t.judge_passed, t.majority_approved) for t in traces),
        judge_criteria=agreement(
            (t.judge_criteria[i], t.criteria_majority[i]) for t, i, _ in by_criterion
        ),
        strata=strata,
        approval_of_majority_criteria_differs=sum(
            all(t.criteria_majority) != t.majority_approved for t in traces
        ),
        natural=natural_approval(store),
        traces=traces,
    )
