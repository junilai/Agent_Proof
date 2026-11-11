"""Attribution of each drawn discordance of D-016, from the majority of three annotators.

For every cell of ``results/samples/desacuerdos.json`` (a run and a direction
of one disagreement, with one drawn repetition), the predicate of the operator
is recomputed from the majority's facts and the approval from the majority's
criteria (all of them met). Then:

1. **Reglas del oráculo** if the predicate from the labels differs from the
   oracle's, as E1 judged it (its rules and the manual annotations of E1);
2. **Evaluador** if the approval from the labels differs from the judge's verdict;
3. **Alcance distinto** if neither erred and the repetition is still discordant.

1 and 2 can hold at once. Counts are weighted by the discordant repetitions each
cell stands for. A cell the labels cannot settle (a decision without a majority
that changes the predicate, or a fact the predicate needs and nobody was asked)
is reported apart, as is one the installed oracle no longer finds discordant.
"""

from __future__ import annotations

import json

from pydantic import BaseModel

from agentproof.store import Store
from experiments.disagreements import DIRECTIONS, Repetition, direction
from experiments.f6.agreement import majority
from experiments.f6.labels import FACTS, TraceLabel
from experiments.oracle.annotation import Case, judged, load_annotations, seed_and_card
from experiments.oracle.predicates import Evidence, fails
from experiments.validation import _as_extracted

SAMPLE = ("results", "samples", "desacuerdos.json")
CAUSES = ("reglas del oráculo", "evaluador", "alcance distinto")


def attribute(
    oracle_fails: bool | None, labels_fail: bool | None, judge_passed: bool, labels_passed: bool
) -> tuple[list[str], str | None]:
    """The causes of one discordance, or why it is reported apart."""
    if oracle_fails is None:
        return [], "el oráculo no lo resuelve"
    if labels_fail is None:
        return [], "las etiquetas no lo resuelven"
    causes = []
    if oracle_fails != labels_fail:
        causes.append("reglas del oráculo")
    if judge_passed != labels_passed:
        causes.append("evaluador")
    if causes:
        return causes, None
    if direction(Repetition(trace_id="", predicate_fails=oracle_fails, judge_passed=judge_passed)):
        return ["alcance distinto"], None
    return [], "ya no es discordante"


class CellAttribution(BaseModel):
    operator: str
    kind: str
    scenario_id: str
    run: str
    run_id: str
    direction: str
    discordant: int
    trace_id: str
    oracle_fails: bool | None
    labels_fails: bool | None
    judge_passed: bool
    labels_passed: bool
    decision_votes: list[str | None]
    causes: list[str]
    apart: str | None


class Count(BaseModel):
    cells: int = 0
    repetitions: int = 0


class Attribution(BaseModel):
    cells: list[CellAttribution]
    by_cause: dict[str, Count]
    both: Count
    by_operator: dict[str, dict[str, int]]
    by_run: dict[str, dict[str, int]]
    by_direction: dict[str, dict[str, int]]
    apart: dict[str, Count]


def labels_predicate(operator: str, case: Case, votes: list[TraceLabel]) -> bool | None:
    """The predicate on the majority's facts; a decision without a majority is tried with
    each annotator's, and settles it only if all of them give the same result."""
    agreed = {name: majority([getattr(v, name) for v in votes]) for name in FACTS}
    decisions = [agreed["decision"]] if agreed["decision"] else [v.decision for v in votes]
    found = {
        fails(
            operator,
            case.card,
            case.trace,
            Evidence(
                _as_extracted(decision),  # type: ignore[arg-type]
                bool(agreed["contradicts_base"]),
                agreed["answers_card"],
                manual=True,
            ),
        )
        for decision in decisions
    }
    return found.pop() if len(found) == 1 else None


def _split(cells: list[CellAttribution], by: str) -> dict[str, dict[str, int]]:
    found: dict[str, dict[str, int]] = {}
    for cell in cells:
        counts = found.setdefault(getattr(cell, by), {})
        for cause in cell.causes:
            counts[cause] = counts.get(cause, 0) + cell.discordant
    return found


def attribution(store: Store, labels: dict[str, dict[str, TraceLabel]]) -> Attribution:
    sample = json.loads(store.root.joinpath(*SAMPLE).read_text(encoding="utf-8"))
    annotations = load_annotations(store)
    seeds = {seed.trace_id: seed for seed in store.seeds()}
    annotators = sorted(labels)
    found = []
    for d in sample["disagreements"]:
        for cell in d["cells"]:
            key = f"{cell['run_id']}/{cell['trace_id']}"
            trace = next(
                t for t in store.run_traces(cell["run_id"]) if t.trace_id == cell["trace_id"]
            )
            case = Case(cell["run_id"], trace, *seed_and_card(seeds, trace.scenario_id or ""))
            verdict = next(
                v for v in store.verdicts(cell["run_id"]) if v.trace_id == trace.trace_id
            )
            votes = [labels[a][key] for a in annotators]
            criteria = [majority(list(c)) for c in zip(*(v.criteria for v in votes), strict=True)]
            oracle = judged(case, d["operator"], annotations)
            ours = labels_predicate(d["operator"], case, votes)
            passed = all(criteria)
            causes, apart = attribute(oracle, ours, verdict.passed, passed)
            found.append(
                CellAttribution(
                    operator=d["operator"],
                    kind=d["kind"],
                    scenario_id=d["scenario_id"],
                    **{k: cell[k] for k in ("run", "run_id", "direction", "discordant")},
                    trace_id=trace.trace_id,
                    oracle_fails=oracle,
                    labels_fails=ours,
                    judge_passed=verdict.passed,
                    labels_passed=passed,
                    decision_votes=[v.decision for v in votes],
                    causes=causes,
                    apart=apart,
                )
            )
    by_cause = {cause: Count() for cause in CAUSES}
    both, apart_counts = Count(), {}
    for cell in found:
        for cause in cell.causes:
            by_cause[cause].cells += 1
            by_cause[cause].repetitions += cell.discordant
        if len(cell.causes) == 2:
            both.cells += 1
            both.repetitions += cell.discordant
        if cell.apart:
            count = apart_counts.setdefault(cell.apart, Count())
            count.cells += 1
            count.repetitions += cell.discordant
    by_direction = _split(found, "direction")
    return Attribution(
        cells=found,
        by_cause=by_cause,
        both=both,
        by_operator=_split(found, "operator"),
        by_run=_split(found, "run"),
        by_direction={way: by_direction[way] for way in DIRECTIONS if way in by_direction},
        apart=apart_counts,
    )
