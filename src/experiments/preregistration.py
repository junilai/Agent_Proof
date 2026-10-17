"""Section 9 of the pre-registration, generated from the corpus (§5.4, D-008, D-010).

The exposed scenarios of each operator come from the rules of the oracle applied
to the seed traces, and the scenarios of the pilot and of the oracle validation
are drawn with seeds fixed beforehand. The document is never written by hand: a
test compares it with what this module prints.

    python -m experiments.preregistration --data .
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

import typer

from agentproof.store import Store
from experiments.cards import CARDS_BY_ID, Card
from experiments.oracle.exposure import is_exposed

PILOT_SEED = 20261017
PILOT_SIZE = 5
VALIDATION_SEED = 20261019
OPERATORS = ("d1", "d2", "d4", "d5", "d6")
VALIDATION = (("baseline", 10), ("d1", 10), ("d2", 10), ("d4", 10), ("d5", 10))
"""Conversations of each condition in the oracle validation (D-010)."""


@dataclass(frozen=True)
class Row:
    card: Card
    scenario_id: str
    exposed: frozenset[str]


def rows(store: Store) -> list[Row]:
    """One row per induced scenario, ordered by card."""
    seeds = {seed.trace_id: seed for seed in store.seeds()}
    found = []
    for scenario in store.scenarios():
        seed = seeds[scenario.seed_trace_id]
        card = CARDS_BY_ID[seed.card_id or ""]
        exposed = frozenset(op for op in OPERATORS if is_exposed(op, card, seed))
        found.append(Row(card, scenario.scenario_id, exposed))
    return sorted(found, key=lambda row: row.card.card_id)


def pilot(table: list[Row]) -> list[Row]:
    drawn = random.Random(PILOT_SEED).sample(table, PILOT_SIZE)
    return sorted(drawn, key=lambda row: row.card.card_id)


def validation(table: list[Row]) -> dict[str, list[Row]]:
    """Each condition draws from its own pool, in the order of ``VALIDATION``.

    A pool smaller than the number of conversations is taken whole and repeated:
    D5 has 5 exposed scenarios and 10 conversations, two repetitions each.
    """
    rng = random.Random(VALIDATION_SEED)
    drawn = {}
    for condition, size in VALIDATION:
        pool = [r for r in table if condition == "baseline" or condition in r.exposed]
        chosen = rng.sample(pool, size) if len(pool) >= size else pool
        drawn[condition] = sorted(chosen, key=lambda row: row.card.card_id)
    return drawn


def _cards(chosen: list[Row]) -> str:
    return ", ".join(row.card.card_id for row in chosen)


def render(store: Store) -> str:
    table = rows(store)
    lines = [
        "Generada con `python -m experiments.preregistration --data .`. Una prueba exige que "
        "esta sección coincida con lo que imprime el comando. D3 no define conjunto expuesto.",
        "",
        "| Tarjeta | Escenario | " + " | ".join(op.upper() for op in OPERATORS) + " |",
        "|---|---|" + "---|" * len(OPERATORS),
    ]
    for row in table:
        marks = " | ".join("✓" if op in row.exposed else "" for op in OPERATORS)
        lines.append(f"| {row.card.card_id} | `{row.scenario_id}` | {marks} |")
    totals = " | ".join(str(sum(op in r.exposed for r in table)) for op in OPERATORS)
    lines += [f"| **expuestos** | de {len(table)} | {totals} |", ""]
    lines.append(
        f"**Piloto** ([D-008](decisiones.md)): semilla `{PILOT_SEED}`, "
        f"{PILOT_SIZE} escenarios: {_cards(pilot(table))}."
    )
    lines += [
        "",
        f"**Validación del oráculo** ([D-010](decisiones.md)): semilla "
        f"`{VALIDATION_SEED}`, una repetición por escenario.",
        "",
    ]
    for condition, chosen in validation(table).items():
        repeat = " (dos repeticiones)" if condition == "d5" else ""
        lines.append(f"- {condition}{repeat}: {_cards(chosen)}.")
    return "\n".join(lines)


app = typer.Typer(help="Sección 9 del pre-registro, generada a partir del corpus.")
DATA = typer.Option(Path("."), "--data", help="Carpeta que contiene corpus/.")


@app.command()
def main(data: Path = DATA):
    """Imprime la sección 9 del pre-registro."""
    typer.echo(render(Store(data)))


if __name__ == "__main__":
    app()
