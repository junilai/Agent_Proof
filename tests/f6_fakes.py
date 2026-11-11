"""Synthetic label files of F6, built on the real samples and keys of the repository."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable
from functools import cache
from pathlib import Path

from agentproof.store import Store
from experiments.annotators import session_one, session_two, write_packages

ROOT = Path(__file__).resolve().parents[1]
ANNOTATORS = ("X1", "X2", "X3")

Fill = Callable[[str, str, dict], dict]
"""(annotator, key of the item, what the item asks) -> the fields of its row."""


@cache
def store() -> Store:
    return Store(ROOT)


@cache
def keys() -> Path:
    """The keys as experiments.annotators writes them, in a folder of their own."""
    out = Path(tempfile.mkdtemp(prefix="f6-"))
    write_packages(store(), out, list(ANNOTATORS))
    return out / "clave"


@cache
def asked(session: int) -> dict[str, dict]:
    items = session_one(store()) if session == 1 else session_two(store())
    return {item["key"]: item for item in items}


def write_labels(folder: Path, annotator: str, session: int, fill: Fill) -> Path:
    key = json.loads((keys() / f"sesion-{session}.json").read_text(encoding="utf-8"))
    rows = []
    for item, target in key.items():
        spec = asked(session)[target]
        if session == 1:
            row = {
                "item": item,
                "decision": None,
                "contradicts_base": None,
                "answers_card": None,
                "criteria": [None] * len(spec["criteria"]),
            }
        else:
            row = {"item": item, "likert": None, "correction": None}
        rows.append(row | fill(annotator, target, spec))
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"etiquetas-{annotator}-sesion-{session}.json"
    data = {"annotator": annotator, "session": session, "labels": rows}
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def constant(decision="procede", contradicts=False, answers=True, met=True) -> Fill:
    """Every asked field with the same answer."""

    def fill(annotator: str, key: str, spec: dict) -> dict:
        row: dict = {"criteria": [met] * len(spec["criteria"])}
        if "decision" in spec["facts"]:
            row["decision"] = decision
        if "contradicts_base" in spec["facts"]:
            row["contradicts_base"] = contradicts
        if "answers_card" in spec["facts"]:
            row["answers_card"] = answers
        return row

    return fill


def rating(likert: int = 5, correction: bool = False) -> Fill:
    return lambda annotator, key, spec: {"likert": likert, "correction": correction}


def write_all(folder: Path, one: Fill | None = None, two: Fill | None = None) -> Path:
    """A complete set of label files of the three annotators for each session given."""
    for annotator in ANNOTATORS:
        if one:
            write_labels(folder, annotator, 1, one)
        if two:
            write_labels(folder, annotator, 2, two)
    return folder


@cache
def judge_criteria() -> dict[str, tuple[bool, ...]]:
    """What the judge said of each criterion, per trace of the store."""
    return {
        f"{run_id}/{v.trace_id}": tuple(c.met for c in v.criteria)
        for run_id in store().runs()
        for v in store().verdicts(run_id)
    }


def like_the_judge(inverted: frozenset[str] = frozenset(), **facts) -> Fill:
    """The judge's criteria, every one inverted for the annotators named."""
    base = constant(**facts)

    def fill(annotator: str, key: str, spec: dict) -> dict:
        row = base(annotator, key, spec)
        if spec["criteria"]:
            row["criteria"] = [met != (annotator in inverted) for met in judge_criteria()[key]]
        return row

    return fill


def trace_of(key: str):
    run_id, trace_id = key.split("/")
    return next(t for t in store().run_traces(run_id) if t.trace_id == trace_id)


@cache
def oracle_reading(key: str) -> dict:
    """What the installed oracle's rules read in a trace, as an annotator would write it."""
    from casestudy.domain.catalog import ORDERS_BY_ID
    from experiments.oracle.annotation import seed_and_card
    from experiments.oracle.attributes import attribute_discrepancies, states_status
    from experiments.oracle.outcome import communicated_decision
    from experiments.validation import _as_label

    trace = trace_of(key)
    seeds = {s.trace_id: s for s in store().seeds()}
    _, card = seed_and_card(seeds, trace.scenario_id or "")
    order = ORDERS_BY_ID[card.orders[0]] if card.orders else None
    return {
        "decision": _as_label(communicated_decision(trace)),
        "contradicts_base": bool(order and attribute_discrepancies(trace, order)),
        "answers_card": bool(order and states_status(trace, order)),
    }


def like_the_oracle(decisions: dict[str, str] | None = None, **overrides) -> Fill:
    """The oracle's reading of every asked fact and the judge's criteria.

    ``decisions`` gives an annotator a fixed decision; ``overrides`` maps an annotator
    to fields it always answers the same way.
    """
    criteria = like_the_judge()

    def fill(annotator: str, key: str, spec: dict) -> dict:
        row = criteria(annotator, key, spec)
        read = oracle_reading(key) | overrides.get(annotator, {})
        if decisions and annotator in decisions:
            read = read | {"decision": decisions[annotator]}
        return row | {name: read[name] for name in spec["facts"]}

    return fill
