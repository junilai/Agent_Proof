"""Coverage report of the seed corpus (§5.2).

Answers, while the sessions are being run, which cards still have no conversation,
which recordings lost their card, and how the exposed and control sets of the
operators that depend on the trace are filling up (§5.4). It only reads: an empty
control set is what triggers eliciting a replacement conversation, and that is a
decision for a person, not for this module.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import typer

from agentproof.schema import Trace
from agentproof.store import Store
from experiments.cards import CARDS, CARDS_BY_ID, Card

TRACE_OPERATORS = {
    "D1": "llama a lookup_order",
    "D4": "llama a get_refund_policy",
    "D6": "tres o más llamadas a herramientas",
}


def _tool_calls(seed: Trace) -> list[str]:
    return [e.tool or "" for e in seed.events if e.kind == "tool_call"]


def _is_exposed(operator: str, seed: Trace) -> bool:
    calls = _tool_calls(seed)
    if operator == "D1":
        return "lookup_order" in calls
    if operator == "D4":
        return "get_refund_policy" in calls
    return len(calls) >= 3


@dataclass
class CoverageReport:
    recorded: dict[str, int] = field(default_factory=dict)
    pending: list[str] = field(default_factory=list)
    problems: dict[str, str] = field(default_factory=dict)
    exposed: dict[str, list[str]] = field(default_factory=dict)
    control: dict[str, list[str]] = field(default_factory=dict)

    @property
    def conversations(self) -> int:
        return sum(self.recorded.values())


def coverage(store: Store) -> CoverageReport:
    report = CoverageReport(recorded=defaultdict(int))
    usable: list[Trace] = []
    for seed in store.seeds():
        if seed.card_id is None:
            report.problems[seed.trace_id] = "sin tarjeta"
        elif seed.card_id not in CARDS_BY_ID:
            report.problems[seed.trace_id] = f"tarjeta desconocida: {seed.card_id}"
        else:
            report.recorded[seed.card_id] += 1
            usable.append(seed)
    report.recorded = dict(report.recorded)
    report.pending = [card.card_id for card in CARDS if card.card_id not in report.recorded]
    for operator in TRACE_OPERATORS:
        report.exposed[operator] = [s.trace_id for s in usable if _is_exposed(operator, s)]
        report.control[operator] = [s.trace_id for s in usable if not _is_exposed(operator, s)]
    return report


def _matrix(report: CoverageReport) -> list[str]:
    tones = ("directo", "confundido", "insistente")
    lines = [f"{'resultado esperado':<20} " + " ".join(f"{tone:>12}" for tone in tones)]
    for expected in ("procede", "no_procede", "escalamiento", "sin_decision"):
        cells = []
        for tone in tones:
            group = [c for c in CARDS if c.expected == expected and c.tone == tone]
            done = sum(1 for c in group if c.card_id in report.recorded)
            cells.append(f"{done}/{len(group)}".rjust(12))
        lines.append(f"{expected:<20} " + " ".join(cells))
    return lines


def render_coverage(report: CoverageReport) -> str:
    lines = [f"Corpus: {report.conversations} de 20 conversaciones", ""]
    lines += _matrix(report)
    lines += [
        "",
        f"tarjetas pendientes ({len(report.pending)}): {', '.join(report.pending) or '—'}",
    ]
    for operator, rule in TRACE_OPERATORS.items():
        exposed, control = len(report.exposed[operator]), len(report.control[operator])
        aviso = " <- conjunto vacío" if not exposed or not control else ""
        lines.append(f"{operator} ({rule}): expuesto {exposed} · control {control}{aviso}")
    for trace_id, problem in report.problems.items():
        lines.append(f"revisar {trace_id}: {problem}")
    return "\n".join(lines)


app = typer.Typer(help="Cobertura del corpus semilla.", no_args_is_help=False)
DATA = typer.Option(Path("."), "--data", help="Carpeta que contiene corpus/.")


@app.command()
def main(data: Path = DATA):
    """Imprime qué falta grabar y cómo van los conjuntos expuesto y de control."""
    typer.echo(render_coverage(coverage(Store(data))))


def card_of(seed: Trace) -> Card | None:
    """The card a seed was recorded with, when it is one of the twenty."""
    return CARDS_BY_ID.get(seed.card_id or "")


if __name__ == "__main__":
    app()
