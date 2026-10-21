"""Disagreements between the oracle and AgentProof in E1 (D-016).

A disagreement is a false negative (the oracle's manifested set has the
scenario, the report did not declare a regression) or a false positive (the
report declared it, the oracle did not) of a candidate's confusion matrix.
Each one is described on two independent axes, over the repetitions of the
reference and of the candidate:

- **Discordant repetitions.** A repetition is discordant when the oracle's
  predicate fails and the judge passed it, or the judge failed it and the
  predicate does not fail. Both runs and both directions count.
- **Origin of the difference.** The increase in the failure rate is computed
  for each mechanism. If both reach the threshold of 0.4, or neither does, the
  two saw the same change and the difference comes from *aggregation* (the
  significance the report also requires); otherwise it comes from the
  *traces*. A scenario can have discordant repetitions and an aggregation
  origin at once.

For every run and direction with discordant repetitions, one of them is drawn
with a fixed seed. The three annotators of F6 label the drawn traces blind,
and each discordance is attributed by recomputing the predicate and the
criteria from their labels. The analysis was added after E1 and is
exploratory: it changes no result.

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


class Cell(BaseModel):
    """The discordant repetitions of one run in one direction, and the one drawn."""

    run: Run
    run_id: str
    direction: Direction
    discordant: int
    trace_id: str


def cells(run: Run, run_id: str, repetitions: list[Repetition], rng: random.Random) -> list[Cell]:
    found = []
    for way in DIRECTIONS:
        ids = sorted(r.trace_id for r in repetitions if direction(r) == way)
        if ids:
            drawn = rng.choice(ids)
            found.append(
                Cell(run=run, run_id=run_id, direction=way, discordant=len(ids), trace_id=drawn)
            )
    return found


class Disagreement(BaseModel):
    """One scenario of the matrix; the operator and the kind are never shown to annotators."""

    operator: str
    kind: Kind
    scenario_id: str
    reference: Rates
    candidate: Rates
    origin: Origin
    cells: list[Cell]


def _repetitions(store: Store, run_id: str, operator: str) -> dict[str, list[Repetition]]:
    annotations = load_annotations(store)
    passed = {v.trace_id: v.passed for v in store.verdicts(run_id)}
    return {
        scenario_id: [
            Repetition(
                trace_id=case.trace.trace_id,
                predicate_fails=judged(case, operator, annotations),
                judge_passed=passed[case.trace.trace_id],
            )
            for case in cases
        ]
        for scenario_id, cases in by_scenario(store, run_id).items()
    }


def disagreements(store: Store, reference: str, candidates: list[str]) -> list[Disagreement]:
    rng = random.Random(SEED)
    found = []
    for run_id in sorted(candidates):
        operator = store.manifest(run_id).condition
        matrix = detection(store, reference, run_id, operator)
        theirs = _repetitions(store, reference, operator)
        ours = _repetitions(store, run_id, operator)
        for kind, scenarios in (
            ("falso negativo", matrix.false_negatives),
            ("falso positivo", matrix.false_positives),
        ):
            for scenario_id in sorted(scenarios):
                base, cand = theirs[scenario_id], ours[scenario_id]
                drawn = cells("referencia", reference, base, rng)
                drawn += cells("candidata", run_id, cand, rng)
                found.append(
                    Disagreement(
                        operator=operator,
                        kind=kind,
                        scenario_id=scenario_id,
                        reference=rates(base),
                        candidate=rates(cand),
                        origin=origin(rates(base), rates(cand)),
                        cells=drawn,
                    )
                )
    return found


class ToAnnotate(BaseModel):
    run_id: str
    trace_id: str


def to_annotate(found: list[Disagreement]) -> list[ToAnnotate]:
    """Every drawn trace once, even if it was drawn for more than one operator."""
    unique = {(c.run_id, c.trace_id) for d in found for c in d.cells}
    return [ToAnnotate(run_id=r, trace_id=t) for r, t in sorted(unique)]


class DisagreementSample(BaseModel):
    seed: int = SEED
    reference: str
    disagreements: list[Disagreement]
    to_annotate: list[ToAnnotate]


app = typer.Typer(help="Desacuerdos entre el oráculo y AgentProof y su sorteo (D-016).")
DATA = typer.Option(Path("."), "--data", help="Carpeta que contiene corpus/ y results/.")
REFERENCE = typer.Option(..., "--reference", help="Corrida de referencia (baseline-a).")
CANDIDATES = typer.Option(..., "--candidate", help="Corrida de una mutación con predicado.")


@app.command()
def main(data: Path = DATA, reference: str = REFERENCE, candidate: list[str] = CANDIDATES):
    """Escribe results/samples/desacuerdos.json."""
    store = Store(data)
    found = disagreements(store, reference, candidate)
    sample = DisagreementSample(
        reference=reference, disagreements=found, to_annotate=to_annotate(found)
    )
    folder = store.root / "results" / "samples"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "desacuerdos.json").write_text(sample.model_dump_json(indent=2) + "\n")
    with_cells = sum(bool(d.cells) for d in found)
    aggregated = sum(d.origin == "agregación" for d in found)
    typer.echo(
        f"Desacuerdos: {len(found)} · con repeticiones discordantes: {with_cells} · "
        f"de origen en la agregación: {aggregated} · en las trazas: {len(found) - aggregated}"
    )
    typer.echo(
        f"Sorteo (semilla {SEED}): {sum(len(d.cells) for d in found)} celdas, "
        f"{len(sample.to_annotate)} trazas para anotar."
    )
    for d in found:
        r, c = d.reference, d.candidate
        typer.echo(
            f"  {d.operator} {d.kind} {d.scenario_id} · origen {d.origin} · "
            f"oráculo {r.oracle}/{r.repetitions}→{c.oracle}/{c.repetitions} · "
            f"evaluador {r.judge}/{r.repetitions}→{c.judge}/{c.repetitions}"
        )
        for cell in d.cells:
            typer.echo(f"      {cell.run}, {cell.direction}: {cell.discordant} → {cell.trace_id}")


if __name__ == "__main__":
    app()
