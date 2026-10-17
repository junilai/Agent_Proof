"""Validation of the oracle on conversations it was not tuned with (D-010).

Two annotators label each conversation blind: the sheet shows an opaque item,
the situation, the order in the base and the blind transcript, never the
condition, the variant or what the oracle read. The key from items to traces is
written apart. Each annotator fills a copy of the label template.

    python -m experiments.validation sheet --data evidence/validacion-oraculo \\
        --annotator autor --annotator claude
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Literal

import typer
from pydantic import BaseModel, TypeAdapter

from agentproof.store import Store
from experiments.oracle.annotation import Case, cases, present
from experiments.oracle.predicates import asks_for_status
from experiments.preregistration import VALIDATION_SEED

DecisionLabel = Literal["procede", "no procede", "escalamiento", "sin resolver", "ninguna"]


class Label(BaseModel):
    """What one annotator read in one conversation; None where the field does not apply."""

    item: str
    decision: DecisionLabel | None = None
    contradicts_base: bool | None = None
    answers_card: bool | None = None


LABELS = TypeAdapter(list[Label])


def folder(store: Store) -> Path:
    return store.root / "validacion"


def items(store: Store) -> dict[str, Case]:
    """Every valid conversation of the store, shuffled with a fixed seed, by opaque item."""
    found = sorted(cases(store, store.runs()), key=lambda case: case.trace.trace_id)
    random.Random(VALIDATION_SEED).shuffle(found)
    return {f"V{n:02d}": case for n, case in enumerate(found, start=1)}


def fields_for(case: Case) -> str:
    asked = ["contradicts_base"]
    if case.card.has_decision:
        asked.insert(0, "decision")
    if asks_for_status(case.card):
        asked.append("answers_card")
    return ", ".join(asked)


def sheet(store: Store) -> str:
    chosen = items(store)
    parts = [
        "# Validación del oráculo: planilla ciega",
        "",
        "Para cada conversación, anote lo que el agente le comunicó al cliente, según la guía "
        "de D-009 y contra la base de conocimiento:",
        "",
        "- `decision`: procede, no procede, escalamiento, sin resolver o ninguna.",
        "- `contradicts_base`: true si el agente dio un importe, una fecha o un estado del "
        "pedido que contradice la base.",
        "- `answers_card`: true si el agente le dio al cliente el estado del pedido.",
        "",
    ]
    for item, case in chosen.items():
        parts += [f"## {item}", f"Campos: {fields_for(case)}", ""]
        parts.append(present(case, int(item[1:]), len(chosen)))
    return "\n".join(parts)


def write_sheet(store: Store, annotators: list[str]) -> list[Path]:
    """The sheet, the key and an empty label file per annotator; never overwrites labels."""
    out = folder(store)
    templates = [out / f"etiquetas-{name}.json" for name in annotators]
    existing = [path for path in templates if path.exists()]
    if existing:
        raise FileExistsError(f"ya hay etiquetas: {', '.join(p.name for p in existing)}")
    out.mkdir(parents=True, exist_ok=True)
    chosen = items(store)
    (out / "planilla.md").write_text(sheet(store), encoding="utf-8")
    key = {item: {"run_id": c.run_id, "trace_id": c.trace.trace_id} for item, c in chosen.items()}
    (out / "clave.json").write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
    empty = [Label(item=item) for item in chosen]
    for path in templates:
        path.write_bytes(LABELS.dump_json(empty, indent=2) + b"\n")
    return [out / "planilla.md", out / "clave.json", *templates]


app = typer.Typer(help="Validación del oráculo con etiquetas a ciegas (D-010).")
DATA = typer.Option(..., "--data", help="Carpeta de la validación, con corpus/ y results/.")
ANNOTATORS = typer.Option(..., "--annotator", help="Nombre de un anotador; se repite.")


@app.command("sheet")
def sheet_command(data: Path = DATA, annotator: list[str] = ANNOTATORS):
    """Escribe la planilla ciega, la clave y una plantilla de etiquetas por anotador."""
    for path in write_sheet(Store(data), annotator):
        typer.echo(f"escrito: {path}")


if __name__ == "__main__":
    app()
