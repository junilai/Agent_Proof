"""Blind manual annotation queue (§5.4).

The traces the rules could not decide are shown to the author in a random order
with a fixed seed, through the same blind transcript the judge reads: no
condition, variant or model. The author annotates what the agent communicated
against the card and the knowledge base; the annotation is stored as manual and
replaces the extracted evidence of that trace for every operator.

    python -m experiments.oracle.annotation --data .
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import typer
from pydantic import BaseModel, TypeAdapter

from agentproof.schema import Trace
from agentproof.store import Store
from agentproof.transcript import render_transcript
from casestudy.domain.catalog import ORDERS_BY_ID
from casestudy.domain.policy import Decision
from experiments.cards import CARDS_BY_ID, Card
from experiments.conditions import CONDITIONS_BY_NAME
from experiments.oracle.exposure import is_exposed, seed_of
from experiments.oracle.predicates import OPERATORS_WITH_PREDICATE, Evidence, fails

QUEUE_SEED = 20261016


class Annotation(BaseModel):
    run_id: str
    trace_id: str
    decision: Literal["procede", "no procede", "escalamiento"] | None
    contradicts_base: bool
    answers_card: bool
    annotated_at: datetime
    manual: Literal[True] = True

    def evidence(self) -> Evidence:
        decision = Decision(self.decision) if self.decision else None
        return Evidence(decision, self.contradicts_base, self.answers_card, manual=True)


_ANNOTATIONS = TypeAdapter(list[Annotation])


def annotations_path(store: Store) -> Path:
    return store.root / "results" / "oracle" / "annotations.json"


def load_annotations(store: Store) -> dict[str, Annotation]:
    path = annotations_path(store)
    if not path.exists():
        return {}
    return {a.trace_id: a for a in _ANNOTATIONS.validate_json(path.read_bytes())}


def save_annotation(store: Store, annotation: Annotation) -> None:
    annotations = load_annotations(store) | {annotation.trace_id: annotation}
    path = annotations_path(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_ANNOTATIONS.dump_json(list(annotations.values()), indent=2) + b"\n")


def operators_for(condition: str) -> tuple[str, ...]:
    """Predicates a run is judged with: its own operator, or all of them for the reference."""
    role = CONDITIONS_BY_NAME[condition].role
    if role == "reference":
        return OPERATORS_WITH_PREDICATE
    return (condition,) if role == "candidate" and condition in OPERATORS_WITH_PREDICATE else ()


@dataclass(frozen=True)
class Case:
    run_id: str
    trace: Trace
    seed: Trace
    card: Card


def seed_and_card(seeds: dict[str, Trace], scenario_id: str) -> tuple[Trace, Card]:
    """The seed a scenario was induced from and its card, reached through identifiers only."""
    seed = seeds[seed_of(scenario_id)]
    return seed, CARDS_BY_ID[seed.card_id or ""]


def cases(store: Store, run_ids: list[str]) -> list[Case]:
    """Every valid repetition of the runs, with its seed and card.

    A trace that ended in ``simulator_error`` is an invalid repetition (D-001):
    the judge skips it and so does the oracle. Two valid traces of the same
    repetition would be counted twice, so they are refused.
    """
    seeds = {seed.trace_id: seed for seed in store.seeds()}
    found = []
    for run_id in run_ids:
        seen: set[tuple[str, int | None]] = set()
        for trace in store.run_traces(run_id):
            if trace.termination == "simulator_error":
                continue
            repetition = (trace.scenario_id or "", trace.repetition)
            if repetition in seen:
                raise ValueError(f"two valid traces of repetition {repetition} in {run_id}")
            seen.add(repetition)
            found.append(Case(run_id, trace, *seed_and_card(seeds, repetition[0])))
    return found


def judged(case: Case, operator: str, annotations: dict[str, Annotation]) -> bool | None:
    annotation = annotations.get(case.trace.trace_id)
    return fails(operator, case.card, case.trace, annotation.evidence() if annotation else None)


def pending(store: Store, run_ids: list[str]) -> list[Case]:
    """Exposed cases some predicate leaves undecided, shuffled with a fixed seed."""
    annotations = load_annotations(store)
    queue = [
        case
        for case in cases(store, run_ids)
        if any(
            is_exposed(op, case.card, case.seed) and judged(case, op, annotations) is None
            for op in operators_for(case.trace.condition or "")
        )
    ]
    queue.sort(key=lambda case: case.trace.trace_id)
    random.Random(QUEUE_SEED).shuffle(queue)
    return queue


def _order_facts(card: Card) -> str:
    if not card.orders:
        return "(la tarjeta no involucra pedidos)"
    order = ORDERS_BY_ID[card.orders[0]]
    delivered = order.delivery_date.isoformat() if order.delivery_date else "—"
    return (
        f"{order.order_id} · {order.product} · USD {order.amount_usd:.2f} · "
        f"{order.status.value} · compra {order.purchase_date.isoformat()} · entrega {delivered}"
    )


def present(case: Case, position: int, total: int) -> str:
    """What the annotator sees: the situation, the order and the blind transcript."""
    return "\n".join(
        [
            f"=== Caso {position} de {total} ===",
            f"Situación: {case.card.text}",
            f"Pedido en la base: {_order_facts(case.card)}",
            "",
            render_transcript(case.trace),
            "",
        ]
    )


_DECISIONS = {"p": "procede", "n": "no procede", "e": "escalamiento", "x": None}

app = typer.Typer(help="Anotación manual a ciegas de los casos que las reglas no resuelven.")
DATA = typer.Option(Path("."), "--data", help="Carpeta que contiene corpus/ y results/.")


@app.command()
def main(data: Path = DATA):
    """Presenta cada caso pendiente y guarda la anotación en results/oracle/annotations.json."""
    store = Store(data)
    queue = pending(store, store.runs())
    if not queue:
        typer.echo("No hay casos pendientes de anotación.")
        return
    for position, case in enumerate(queue, start=1):
        typer.echo(present(case, position, len(queue)))
        key = ""
        while key not in _DECISIONS:
            key = typer.prompt(
                "Decisión comunicada [p]rocede, [n]o procede, [e]scalamiento, ninguna [x]"
            ).strip()
        annotation = Annotation(
            run_id=case.run_id,
            trace_id=case.trace.trace_id,
            decision=_DECISIONS[key],
            contradicts_base=typer.confirm("¿Algún importe, fecha o estado contradice la base?"),
            answers_card=typer.confirm("¿El agente entregó lo que la situación pedía?"),
            annotated_at=datetime.now(UTC),
        )
        save_annotation(store, annotation)
    typer.echo(f"Anotados {len(queue)} casos.")


if __name__ == "__main__":
    app()
