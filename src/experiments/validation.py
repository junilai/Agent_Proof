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
from casestudy.domain.catalog import ORDERS_BY_ID
from casestudy.domain.policy import Decision
from casestudy.domain.policy_text import policy_text
from experiments.oracle.annotation import Case, cases, operators_for, present
from experiments.oracle.attributes import attribute_discrepancies, states_status
from experiments.oracle.exposure import is_exposed
from experiments.oracle.outcome import UNRESOLVED, Extracted, communicated_decision
from experiments.oracle.predicates import Evidence, asks_for_status, fails
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


def _conversation(case: Case, position: int, total: int) -> str:
    """The case without the tool calls: their results would reveal a mutated policy (D4)
    or the missing lookups of D1. The order in the base and the true policy stand in."""
    shown = present(case, position, total).splitlines()
    return "\n".join(line for line in shown if not line.startswith("[HERRAMIENTA]"))


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
        "La política verdadera, contra la que se juzga cada conversación:",
        "",
        *(f"> {line}" for line in policy_text().splitlines()),
        "",
    ]
    for item, case in chosen.items():
        parts += [f"## {item}", f"Campos: {fields_for(case)}", ""]
        parts.append(_conversation(case, int(item[1:]), len(chosen)))
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


FIELDS = ("decision", "contradicts_base", "answers_card")


def load_labels(path: Path, store: Store) -> dict[str, Label]:
    """An annotator's labels, refused while a field its card asks for is empty."""
    labels = {label.item: label for label in LABELS.validate_json(path.read_bytes())}
    chosen = items(store)
    if set(labels) != set(chosen):
        raise ValueError(f"{path.name}: los ítems no coinciden con la planilla")
    empty = [
        f"{item}.{name}"
        for item, case in chosen.items()
        for name in fields_for(case).split(", ")
        if getattr(labels[item], name) is None
    ]
    if empty:
        raise ValueError(f"{path.name}: faltan {', '.join(empty)}")
    return labels


def cohen_kappa(pairs: list[tuple[object, object]]) -> float | None:
    """Agreement beyond chance; None when chance alone explains every pair."""
    if not pairs:
        return None
    observed = sum(a == b for a, b in pairs) / len(pairs)
    categories = {value for pair in pairs for value in pair}
    chance = sum(
        (sum(a == c for a, _ in pairs) / len(pairs)) * (sum(b == c for _, b in pairs) / len(pairs))
        for c in categories
    )
    return None if chance == 1 else (observed - chance) / (1 - chance)


def agreement(first: dict[str, Label], second: dict[str, Label]) -> str:
    lines = ["campo | ítems | acuerdo | κ de Cohen", "---|---|---|---"]
    disagreements = []
    for name in FIELDS:
        pairs = [
            (getattr(first[i], name), getattr(second[i], name))
            for i in first
            if getattr(first[i], name) is not None
        ]
        agreed = sum(a == b for a, b in pairs)
        kappa = cohen_kappa(pairs)
        shown = "—" if kappa is None else f"{kappa:.2f}"
        lines.append(f"{name} | {len(pairs)} | {agreed}/{len(pairs)} | {shown}")
        disagreements += [
            f"- {i}.{name}: {getattr(first[i], name)} / {getattr(second[i], name)}"
            for i in first
            if getattr(first[i], name) is not None
            and getattr(first[i], name) != getattr(second[i], name)
        ]
    return "\n".join([*lines, "", "Desacuerdos:", *(disagreements or ["- ninguno"])])


def _as_label(found: Extracted) -> str:
    if found is UNRESOLVED:
        return "sin resolver"
    return found.value if isinstance(found, Decision) else "ninguna"


def _as_extracted(label: DecisionLabel | None) -> Extracted:
    if label == "sin resolver":
        return UNRESOLVED
    return None if label in (None, "ninguna") else Decision(label)


def decision_outcome(label: str, found: str) -> str:
    decisions = {d.value for d in Decision}
    if label == found:
        return "exacta"
    if label in decisions and found in decisions:
        return "al revés"
    if found in decisions:
        return "de más"
    return "a la cola" if found == "sin resolver" else "omitida"


def score(store: Store, labels: dict[str, Label]) -> dict[str, dict[str, int]]:
    """The oracle against the reconciled labels (D-010)."""
    table: dict[str, dict[str, int]] = {"decisión": {}, "atributos": {}, "estado": {}}
    table["predicados"] = {}

    def count(group: str, key: str) -> None:
        table[group][key] = table[group].get(key, 0) + 1

    for item, case in items(store).items():
        label, trace, card = labels[item], case.trace, case.card
        if card.has_decision:
            found = _as_label(communicated_decision(trace))
            count("decisión", decision_outcome(label.decision or "ninguna", found))
        if card.orders:
            said = bool(attribute_discrepancies(trace, ORDERS_BY_ID[card.orders[0]]))
            truth = {(True, True): "VP", (True, False): "FP", (False, True): "FN"}
            count("atributos", truth.get((said, bool(label.contradicts_base)), "VN"))
            if asks_for_status(card):
                agrees = states_status(trace, ORDERS_BY_ID[card.orders[0]]) == label.answers_card
                count("estado", "coincide" if agrees else "difiere")
        annotated = Evidence(
            _as_extracted(label.decision),
            bool(label.contradicts_base),
            label.answers_card,
            manual=True,
        )
        for op in operators_for(trace.condition or ""):
            if is_exposed(op, card, case.seed):
                oracle, truth_value = fails(op, card, trace), fails(op, card, trace, annotated)
                key = (
                    "a la cola"
                    if oracle is None
                    else "coincide"
                    if oracle == truth_value
                    else "difiere"
                )
                count("predicados", f"{op} {key}")
    return table


def render_score(table: dict[str, dict[str, int]]) -> str:
    lines = []
    for group, counts in table.items():
        lines.append(f"{group}: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    return "\n".join(lines)


app = typer.Typer(help="Validación del oráculo con etiquetas a ciegas (D-010).")
DATA = typer.Option(..., "--data", help="Carpeta de la validación, con corpus/ y results/.")
ANNOTATORS = typer.Option(..., "--annotator", help="Nombre de un anotador; se repite.")


@app.command("sheet")
def sheet_command(data: Path = DATA, annotator: list[str] = ANNOTATORS):
    """Escribe la planilla ciega, la clave y una plantilla de etiquetas por anotador."""
    for path in write_sheet(Store(data), annotator):
        typer.echo(f"escrito: {path}")


FIRST = typer.Option(..., "--first", help="Etiquetas de un anotador.")
SECOND = typer.Option(..., "--second", help="Etiquetas del otro anotador.")
LABELLED = typer.Option(..., "--labels", help="Etiquetas conciliadas.")


@app.command("agree")
def agree_command(data: Path = DATA, first: Path = FIRST, second: Path = SECOND):
    """Acuerdo entre los dos anotadores por campo, con κ de Cohen, y sus desacuerdos."""
    store = Store(data)
    typer.echo(agreement(load_labels(first, store), load_labels(second, store)))


@app.command("score")
def score_command(data: Path = DATA, labels: Path = LABELLED):
    """El oráculo contra las etiquetas conciliadas: decisión, atributos, estado y predicados."""
    store = Store(data)
    typer.echo(render_score(score(store, load_labels(labels, store))))


_DECISION_KEYS = {
    "p": "procede",
    "n": "no procede",
    "e": "escalamiento",
    "s": "sin resolver",
    "x": "ninguna",
}
_QUIT = "q"


def _ask(question: str, keys: dict[str, object]) -> object:
    """One key per answer; ``q`` stops and keeps what was already saved."""
    options = "/".join([*keys, _QUIT])
    while True:
        key = typer.prompt(f"{question} [{options}]").strip().lower()
        if key == _QUIT:
            raise typer.Exit(0)
        if key in keys:
            return keys[key]


def label_interactively(store: Store, annotator: str) -> int:
    """Asks the fields of each unlabelled item and saves after every one; returns how many."""
    path = folder(store) / f"etiquetas-{annotator}.json"
    labels = {label.item: label for label in LABELS.validate_json(path.read_bytes())}
    chosen = items(store)
    todo = [
        item
        for item, case in chosen.items()
        if any(getattr(labels[item], name) is None for name in fields_for(case).split(", "))
    ]
    typer.echo(f"{len(chosen) - len(todo)} de {len(chosen)} ítems ya etiquetados.")
    yes_no = {"s": True, "n": False}
    for done, item in enumerate(todo, start=1):
        case = chosen[item]
        typer.echo(f"\n{'=' * 72}\n{item} ({done} de {len(todo)} pendientes)")
        typer.echo(_conversation(case, int(item[1:]), len(chosen)))
        asked = fields_for(case)
        label = Label(item=item)
        if "decision" in asked:
            choices = ", ".join(f"[{k}] {v}" for k, v in _DECISION_KEYS.items())
            typer.echo(f"Decisión comunicada: {choices}")
            label.decision = _ask("decisión", _DECISION_KEYS)  # type: ignore[assignment]
        label.contradicts_base = _ask(  # type: ignore[assignment]
            "¿Algún importe, fecha o estado contradice la base? s/n", yes_no
        )
        if "answers_card" in asked:
            label.answers_card = _ask(  # type: ignore[assignment]
                "¿Le dio al cliente el estado del pedido? s/n", yes_no
            )
        labels[item] = label
        path.write_bytes(LABELS.dump_json(list(labels.values()), indent=2) + b"\n")
    return len(todo)


@app.command("label")
def label_command(data: Path = DATA, annotator: str = typer.Option(..., "--annotator")):
    """Etiqueta en la terminal, ítem por ítem; guarda tras cada uno y se puede retomar."""
    count = label_interactively(Store(data), annotator)
    typer.echo(f"\nListo: {count} ítems etiquetados en esta sesión.")


if __name__ == "__main__":
    app()
