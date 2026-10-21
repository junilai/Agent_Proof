"""Sample of the disagreements between the oracle and AgentProof in E1 (D-016).

A disagreement is a false negative (the oracle's manifested set has the
scenario, the report did not declare a regression) or a false positive (the
report declared it, the oracle did not) of a candidate's confusion matrix.

A disagreement is *of a trace* when some repetition disagrees on its own (the
predicate fails and the judge passed, for a false negative; the judge failed
and the predicate does not, for a false positive): one of those repetitions is
drawn, and the three annotators of F6 label it blind to attribute the
disagreement to the judge, to the criteria or to the oracle. Otherwise it is
*of aggregation*: wherever one fails the other fails too, so the difference
comes from the five repetitions, the multiple-comparison correction or a
baseline that already fails; it is reported without annotation. The analysis
was added after E1 and is exploratory: it changes no result.

    python -m experiments.disagreements --data . --reference <run> --candidate <run> ...
"""

from __future__ import annotations

import random
from fractions import Fraction
from pathlib import Path
from typing import Literal

import typer
from pydantic import BaseModel

from agentproof.store import Store
from experiments.analysis.detection import detection
from experiments.oracle.annotation import judged, load_annotations
from experiments.oracle.manifested import THRESHOLD, by_scenario

SEED = 20261022

Kind = Literal["falso negativo", "falso positivo"]
Run = Literal["referencia", "candidata"]
Direction = Literal["oráculo falla, evaluador aprueba", "evaluador reprueba, oráculo no"]
Origin = Literal["agregación", "traza"]
DIRECTIONS: tuple[Direction, ...] = (
    "oráculo falla, evaluador aprueba",
    "evaluador reprueba, oráculo no",
)


class Repetition(BaseModel):
    trace_id: str
    predicate_fails: bool | None
    judge_passed: bool


def direction(repetition: Repetition) -> Direction | None:
    """How the repetition is discordant, or None if both mechanisms agree on it."""
    if repetition.predicate_fails is True and repetition.judge_passed:
        return "oráculo falla, evaluador aprueba"
    if repetition.predicate_fails is False and not repetition.judge_passed:
        return "evaluador reprueba, oráculo no"
    return None


class Rates(BaseModel):
    """Failures each mechanism counts among the repetitions of one run."""

    repetitions: int
    oracle: int
    judge: int


def rates(repetitions: list[Repetition]) -> Rates:
    return Rates(
        repetitions=len(repetitions),
        oracle=sum(r.predicate_fails is True for r in repetitions),
        judge=sum(not r.judge_passed for r in repetitions),
    )


def origin(reference: Rates, candidate: Rates) -> Origin:
    """Aggregation if both mechanisms are on the same side of the threshold, else traces."""

    def reaches(ours: int, theirs: int) -> bool:
        increase = Fraction(ours, candidate.repetitions) - Fraction(theirs, reference.repetitions)
        return increase >= THRESHOLD

    oracle = reaches(candidate.oracle, reference.oracle)
    judge = reaches(candidate.judge, reference.judge)
    return "agregación" if oracle == judge else "traza"


class Disagreement(BaseModel):
    """One trace to annotate; the operator and the kind are never shown to annotators."""

    operator: str
    kind: Kind
    run_id: str
    scenario_id: str
    trace_id: str | None  # None: a disagreement of aggregation, not annotated


def disagrees(kind: Kind, repetition: Repetition) -> bool:
    if kind == "falso negativo":
        return repetition.predicate_fails is True and repetition.judge_passed
    return repetition.predicate_fails is False and not repetition.judge_passed


def pick(kind: Kind, repetitions: list[Repetition], rng: random.Random) -> str | None:
    """A repetition that disagrees on its own, or None if the disagreement is of aggregation."""
    wanted = sorted(r.trace_id for r in repetitions if disagrees(kind, r))
    return rng.choice(wanted) if wanted else None


def disagreement_sample(store: Store, reference: str, candidates: list[str]) -> list[Disagreement]:
    rng = random.Random(SEED)
    annotations = load_annotations(store)
    sample = []
    for run_id in sorted(candidates):
        operator = store.manifest(run_id).condition
        found = detection(store, reference, run_id, operator)
        passed = {v.trace_id: v.passed for v in store.verdicts(run_id)}
        grouped = by_scenario(store, run_id)
        for kind, scenarios in (
            ("falso negativo", found.false_negatives),
            ("falso positivo", found.false_positives),
        ):
            for scenario_id in sorted(scenarios):
                repetitions = [
                    Repetition(
                        trace_id=case.trace.trace_id,
                        predicate_fails=judged(case, operator, annotations),
                        judge_passed=passed[case.trace.trace_id],
                    )
                    for case in grouped[scenario_id]
                ]
                trace_id = pick(kind, repetitions, rng)
                sample.append(
                    Disagreement(
                        operator=operator,
                        kind=kind,
                        run_id=run_id,
                        scenario_id=scenario_id,
                        trace_id=trace_id,
                    )
                )
    return sample


class DisagreementSample(BaseModel):
    seed: int = SEED
    reference: str
    traces: list[Disagreement]


app = typer.Typer(help="Sorteo de los desacuerdos entre el oráculo y AgentProof (D-016).")
DATA = typer.Option(Path("."), "--data", help="Carpeta que contiene corpus/ y results/.")
REFERENCE = typer.Option(..., "--reference", help="Corrida de referencia (baseline-a).")
CANDIDATES = typer.Option(..., "--candidate", help="Corrida de una mutación con predicado.")


@app.command()
def main(data: Path = DATA, reference: str = REFERENCE, candidate: list[str] = CANDIDATES):
    """Escribe results/samples/desacuerdos.json."""
    store = Store(data)
    sample = DisagreementSample(
        reference=reference, traces=disagreement_sample(store, reference, candidate)
    )
    folder = store.root / "results" / "samples"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "desacuerdos.json").write_text(sample.model_dump_json(indent=2) + "\n")
    drawn = sum(item.trace_id is not None for item in sample.traces)
    typer.echo(
        f"Desacuerdos: {len(sample.traces)}; {drawn} de traza, con una traza sorteada "
        f"(semilla {SEED}), y {len(sample.traces) - drawn} de agregación."
    )
    for item in sample.traces:
        kind = "de agregación" if item.trace_id is None else item.trace_id
        typer.echo(f"  {item.operator} {item.kind}: {item.scenario_id} · {kind}")


if __name__ == "__main__":
    app()
