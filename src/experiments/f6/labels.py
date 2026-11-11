"""The label files the annotators return, checked against what each item asked.

Each annotator downloads one file per session from the page of
``experiments.annotators``, named ``etiquetas-<anotador>-sesion-<n>.json``. The
keys from opaque items to traces (session 1) and to scenarios (session 2) are
the ones that module wrote apart. A session without any file is left empty; a
session with files needs the three annotators, every item and every field the
item asked, or nothing is loaded and every gap is named.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from agentproof.store import Store
from experiments.annotators import session_one, session_two

ANNOTATORS = 3
DECISIONS = ("procede", "no procede", "escalamiento", "sin resolver", "ninguna")
FACTS = ("decision", "contradicts_base", "answers_card")
_NAME = re.compile(r"etiquetas-(?P<annotator>.+)-sesion-(?P<session>[12])\.json")


@dataclass(frozen=True)
class TraceLabel:
    """What one annotator read in one trace; None where the item did not ask."""

    decision: str | None = None
    contradicts_base: bool | None = None
    answers_card: bool | None = None
    criteria: tuple[bool, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class Rating:
    """One annotator's rating of one induced scenario (E3)."""

    likert: int
    correction: bool
    note: str = ""


@dataclass
class Labels:
    """Labels by annotator: of each trace ("run_id/trace_id") and of each scenario."""

    traces: dict[str, dict[str, TraceLabel]] = field(default_factory=dict)
    scenarios: dict[str, dict[str, Rating]] = field(default_factory=dict)

    @property
    def annotators(self) -> list[str]:
        return sorted(self.traces or self.scenarios)


def _check_fact(name: str, value: object) -> str | None:
    if value is None:
        return f"falta {name}"
    if name == "decision":
        return None if value in DECISIONS else f"decision no es una de {', '.join(DECISIONS)}"
    return None if isinstance(value, bool) else f"{name} debe ser true o false"


def _trace_label(row: dict, spec: dict, gaps: list[str]) -> TraceLabel:
    item, found = row["item"], {}
    for name in spec["facts"]:
        problem = _check_fact(name, row.get(name))
        if problem:
            gaps.append(f"{item}: {problem}")
        found[name] = row.get(name)
    criteria = row.get("criteria") or []
    for n in range(1, len(spec["criteria"]) + 1):
        value = criteria[n - 1] if n <= len(criteria) else None
        if not isinstance(value, bool):
            gaps.append(f"{item}: falta el criterio {n}")
    if len(criteria) > len(spec["criteria"]):
        gaps.append(f"{item}: sobran criterios")
    return TraceLabel(**found, criteria=tuple(criteria), note=row.get("nota") or "")


def _rating(row: dict, gaps: list[str]) -> Rating | None:
    item, likert, correction = row["item"], row.get("likert"), row.get("correction")
    if isinstance(likert, bool) or likert not in range(1, 6):
        gaps.append(f"{item}: likert debe ser un entero de 1 a 5")
    if not isinstance(correction, bool):
        gaps.append(f"{item}: falta correction (true o false)")
    return Rating(likert, correction, row.get("nota") or "")  # type: ignore[arg-type]


def _read(path: Path, session: int, key: dict[str, str], specs: dict[str, dict], gaps: list[str]):
    data = json.loads(path.read_text(encoding="utf-8"))
    annotator = _NAME.fullmatch(path.name)["annotator"]  # type: ignore[index]
    if data.get("annotator") != annotator or data.get("session") != session:
        claimed = f"{data.get('annotator')}, sesión {data.get('session')}"
        gaps.append(f"el archivo dice ser de {claimed}")
    rows: dict[str, dict] = {}
    for row in data.get("labels", []):
        if row.get("item") not in key:
            gaps.append(f"ítem desconocido {row.get('item')}")
        elif row["item"] in rows:
            gaps.append(f"ítem repetido {row['item']}")
        else:
            rows[row["item"]] = row
    gaps += [f"falta el ítem {item}" for item in key if item not in rows]
    if session == 1:
        return {key[item]: _trace_label(row, specs[key[item]], gaps) for item, row in rows.items()}
    return {key[item]: _rating(row, gaps) for item, row in rows.items()}


def _key(keys: Path, session: int, specs: dict[str, dict]) -> dict[str, str]:
    key = json.loads((keys / f"sesion-{session}.json").read_text(encoding="utf-8"))
    if sorted(key.values()) != sorted(specs) or any(
        specs[target]["item"] != item for item, target in key.items()
    ):
        raise ValueError(f"la clave de la sesión {session} no corresponde a los paquetes")
    return key


def load(store: Store, labels: Path, keys: Path) -> Labels:
    """The labels of both sessions, or a ValueError naming every gap in Spanish."""
    found = Labels()
    errors: list[str] = []
    for session in (1, 2):
        paths = sorted(p for p in labels.glob(f"etiquetas-*-sesion-{session}.json"))
        if not paths:
            continue
        if len(paths) != ANNOTATORS:
            errors.append(f"sesión {session}: se esperan {ANNOTATORS} anotadores, hay {len(paths)}")
            continue
        items = session_one(store) if session == 1 else session_two(store)
        specs = {item["key"]: item for item in items}
        key = _key(keys, session, specs)
        for path in paths:
            gaps: list[str] = []
            read = _read(path, session, key, specs, gaps)
            errors += [f"{path.name}: {gap}" for gap in gaps]
            annotator = _NAME.fullmatch(path.name)["annotator"]  # type: ignore[index]
            (found.traces if session == 1 else found.scenarios)[annotator] = read
    if found.traces and found.scenarios and set(found.traces) != set(found.scenarios):
        errors.append("las dos sesiones no son los mismos anotadores")
    if errors:
        raise ValueError("Etiquetas incompletas o inválidas:\n- " + "\n- ".join(errors))
    return found
