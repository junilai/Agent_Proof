"""Blind packages for the three annotators of F6 (pre-registration §4 and §6, D-016).

Session 1 gathers every E1 trace of the three samples, each labelled once: the
criteria of its scenario for E2 and the disagreements, with the judge's rubric
and the transcript the judge read; the facts for the audit and the
disagreements, with the guide of D-010. A trace only in the audit hides its tool
calls, as the D-010 sheet does, because their results would reveal the mutation.
An audit trace of a card without a decision or an order (tc-18 to tc-20) is left
out: the oracle reads nothing there, so there is nothing to audit.
Session 2 is E3: each scenario next to the conversation it was induced from.

Items get opaque identifiers in an order drawn with a fixed seed. The key from
items to traces is written apart and never goes to the annotators.

    python -m experiments.annotators --data . --out <folder> --annotator X1 ...
"""

from __future__ import annotations

import json
import random
from importlib import resources
from pathlib import Path

import typer

from agentproof.judge import JUDGE_RUBRIC
from agentproof.schema import Trace
from agentproof.store import Store
from agentproof.transcript import _LABELS, _json, _mask_models
from casestudy.domain.policy_text import policy_text
from experiments.oracle.annotation import _order_facts, seed_and_card
from experiments.oracle.predicates import asks_for_status

ORDER_SEED = 20261111
SAMPLES = Path("results") / "samples"
LIKERT = {
    1: "el escenario no corresponde a la conversación",
    3: "corresponde parcialmente, con omisiones o criterios no verificables",
    5: (
        "recoge fielmente el objetivo del usuario y criterios verificables "
        "a partir de la conversación"
    ),
}


def _sample(data: Path, name: str, key: str) -> list[tuple[str, str]]:
    found = json.loads((data / SAMPLES / f"{name}.json").read_text(encoding="utf-8"))[key]
    return [(t["run_id"], t["trace_id"]) for t in found]


def _messages(trace: Trace, tools: bool) -> list[dict[str, str]]:
    """The blind transcript the judge reads, one entry per event; tool calls only if asked."""
    shown = []
    for event in trace.events:
        if event.kind == "tool_call":
            if not tools:
                continue
            text = f"{event.tool}({_json(event.arguments or {})}) -> {_json(event.result)}"
            shown.append(
                {"who": "HERRAMIENTA", "text": text + (" (error)" if event.is_error else "")}
            )
        else:
            shown.append({"who": _LABELS[event.kind], "text": event.text or ""})
    return [{**m, "text": _mask_models(m["text"])} for m in shown]


def _shuffled(items: list[dict]) -> list[dict]:
    items = sorted(items, key=lambda item: item["key"])
    random.Random(ORDER_SEED).shuffle(items)
    width = len(str(len(items)))
    for position, item in enumerate(items, start=1):
        item["item"] = f"c{position:0{width}d}"
    return items


def session_one(store: Store) -> list[dict]:
    """One item per trace of E2, the audit and the disagreements, with what each sample asks."""
    criteria = set(_sample(store.root, "e2", "pairs")) | set(
        _sample(store.root, "desacuerdos", "to_annotate")
    )
    facts = set(_sample(store.root, "auditoria", "traces")) | set(
        _sample(store.root, "desacuerdos", "to_annotate")
    )
    seeds = {seed.trace_id: seed for seed in store.seeds()}
    items = []
    for run_id, trace_id in sorted(criteria | facts):
        trace = next(t for t in store.run_traces(run_id) if t.trace_id == trace_id)
        scenario_id = trace.scenario_id or ""
        _, card = seed_and_card(seeds, scenario_id)
        asked = []
        if (run_id, trace_id) in facts:
            asked += ["decision"] if card.has_decision else []
            asked += ["contradicts_base"] if card.orders else []
            asked += ["answers_card"] if asks_for_status(card) else []
        has_criteria = (run_id, trace_id) in criteria
        if not asked and not has_criteria:
            continue  # a card without decision or order: the oracle reads nothing to audit
        items.append(
            {
                "key": f"{run_id}/{trace_id}",
                "facts": asked,
                "criteria": store.scenario(scenario_id).success_criteria if has_criteria else [],
                "situation": card.text if asked else "",
                "order": _order_facts(card) if asked else "",
                "messages": _messages(trace, tools=has_criteria),
            }
        )
    return _shuffled(items)


def session_two(store: Store) -> list[dict]:
    """E3: every scenario of the suite next to its seed conversation."""
    seeds = {seed.trace_id: seed for seed in store.seeds()}
    items = []
    for scenario in store.scenarios():
        items.append(
            {
                "key": scenario.scenario_id,
                "goal": scenario.user_goal,
                "opening": scenario.opening_message,
                "criteria": scenario.success_criteria,
                "messages": _messages(seeds[scenario.seed_trace_id], tools=True),
            }
        )
    return _shuffled(items)


def page(session: int, annotator: str, items: list[dict]) -> str:
    data = {
        "session": session,
        "annotator": annotator,
        "rubric": JUDGE_RUBRIC.splitlines(),
        "policy": policy_text().splitlines(),
        "likert": LIKERT,
        "items": [{k: v for k, v in item.items() if k != "key"} for item in items],
    }
    template = resources.files("experiments").joinpath("annotators.html").read_text("utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return template.replace("__DATA__", payload)


def write_packages(store: Store, out: Path, annotators: list[str]) -> list[Path]:
    """A page per annotator and session, and the key of each session, kept apart."""
    sessions = {1: session_one(store), 2: session_two(store)}
    written = []
    (out / "clave").mkdir(parents=True, exist_ok=True)
    for session, items in sessions.items():
        key = {item["item"]: item["key"] for item in items}
        path = out / "clave" / f"sesion-{session}.json"
        path.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        written.append(path)
        for annotator in annotators:
            path = out / annotator / f"sesion-{session}.html"
            path.parent.mkdir(exist_ok=True)
            path.write_text(page(session, annotator, items), encoding="utf-8")
            written.append(path)
    return written


app = typer.Typer(help="Paquetes ciegos para los anotadores de F6.")
DATA = typer.Option(Path("."), "--data", help="Carpeta con corpus/ y results/.")
OUT = typer.Option(..., "--out", help="Carpeta de salida, fuera del repositorio.")
ANNOTATORS = typer.Option(..., "--annotator", help="Nombre del anotador; se repite.")


@app.command()
def main(data: Path = DATA, out: Path = OUT, annotator: list[str] = ANNOTATORS):
    """Escribe una página por anotador y sesión, y la clave de cada sesión aparte."""
    for path in write_packages(Store(data), out, annotator):
        typer.echo(f"escrito: {path}")


if __name__ == "__main__":
    app()
