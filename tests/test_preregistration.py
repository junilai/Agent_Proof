"""Fingerprint of the pre-registered protocol (§10 of the F3 spec, D-008).

Every frozen piece is hashed and compared with the table in section 10 of
``docs/preregistro.md``. The document is the source of truth: changing a piece
without amending the pre-registration fails the build. To amend, declare the
change in section 8 and paste the table this module prints:

    uv run python -m tests.test_preregistration
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import fields, is_dataclass
from datetime import date
from enum import Enum
from fractions import Fraction
from pathlib import Path
from typing import Any

from agentproof import models, retries
from agentproof.induction import INDUCTION_SYSTEM
from agentproof.judge import JUDGE_RUBRIC
from agentproof.report import MIN_DROP
from agentproof.simulator import SIM_USER_SYSTEM
from agentproof.stats import ALPHA
from casestudy.domain.catalog import ORDERS
from casestudy.domain.mutations import MUTATIONS
from casestudy.domain.orders import DOMAIN_TODAY
from casestudy.domain.policy_text import policy_text
from casestudy.domain.prompt import system_prompt
from casestudy.editions import claude_sdk
from experiments.cards import CARDS
from experiments.oracle.annotation import QUEUE_SEED
from experiments.oracle.manifested import SENSITIVITY, THRESHOLD

ROOT = Path(__file__).resolve().parent.parent
PREREGISTRATION = ROOT / "docs" / "preregistro.md"
ORACLE = ROOT / "src" / "experiments" / "oracle"
SEEDS = ROOT / "corpus" / "seeds"
SCENARIOS = ROOT / "corpus" / "scenarios"
ROW = re.compile(r"^\| (.+?) \| `([0-9a-f]{16})` \|$")


def _plain(value: Any) -> Any:
    """A form of the value whose JSON never depends on the run (sets are sorted)."""
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, frozenset | set):
        return sorted(_plain(v) for v in value)
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, date | Fraction):
        return str(value)
    return value


def _digest(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(_plain(value), sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _files(folder: Path, pattern: str) -> str:
    """The text of every file, in name order, so the digest never depends on how it is read."""
    return "".join(
        f"{p.name}\n{p.read_text(encoding='utf-8')}" for p in sorted(folder.glob(pattern))
    )


def protocol() -> dict[str, str]:
    """Every frozen piece of the protocol, by the name the pre-registration gives it."""
    oracle_source = "".join(p.read_text() for p in sorted(ORACLE.glob("*.py")))
    return {
        "Modelos de los componentes": _digest(models.snapshot()),
        "Instrucciones del inductor": _digest(INDUCTION_SYSTEM),
        "Instrucciones del usuario simulado": _digest(SIM_USER_SYSTEM),
        "Rúbrica del evaluador": _digest(JUDGE_RUBRIC),
        "Prompt del agente en cada variante": _digest(
            {name: system_prompt(m) for name, m in MUTATIONS.items()}
        ),
        "Herramientas y límite de pasos de la edición Claude Agent SDK": _digest(
            {
                "tools": [claude_sdk._LOOKUP, claude_sdk._POLICY, claude_sdk._TICKET],
                "step_limit": claude_sdk.STEP_LIMIT,
            }
        ),
        "Mutaciones": _digest(MUTATIONS),
        "Base de conocimiento": _digest(
            {"orders": ORDERS, "today": DOMAIN_TODAY, "policy": policy_text()}
        ),
        "Tarjetas de situación": _digest(CARDS),
        "Criterio de regresión y reintentos": _digest(
            {
                "min_drop": MIN_DROP,
                "alpha": ALPHA,
                "per_repetition": retries.PER_REPETITION,
                "per_scenario": retries.PER_SCENARIO,
            }
        ),
        "Umbrales y semilla del oráculo": _digest(
            {"threshold": THRESHOLD, "sensitivity": SENSITIVITY, "queue_seed": QUEUE_SEED}
        ),
        "Reglas del oráculo (código fuente)": _digest(oracle_source),
        "Corpus semilla": _digest(_files(SEEDS, "*.json")),
        "Escenarios inducidos": _digest(_files(SCENARIOS, "*.json")),
    }


def declared() -> dict[str, str]:
    rows = (ROW.match(line) for line in PREREGISTRATION.read_text().splitlines())
    return {m.group(1): m.group(2) for m in rows if m}


def table() -> str:
    return "\n".join(f"| {name} | `{digest}` |" for name, digest in protocol().items())


def test_the_code_matches_the_preregistered_protocol():
    changed = {
        name: digest for name, digest in protocol().items() if declared().get(name) != digest
    }
    assert not changed, (
        f"El protocolo cambió respecto del pre-registro: {sorted(changed)}. "
        "Declare la enmienda en la sección 8 y actualice la tabla de la sección 10:\n" + table()
    )
    assert set(declared()) == set(protocol()), "la tabla nombra piezas que ya no existen"


def test_the_frozen_corpus_has_one_scenario_per_seed():
    seeds = {p.stem for p in SEEDS.glob("*.json")}
    scenarios = {p.stem for p in SCENARIOS.glob("*.json")}
    assert len(seeds) == len(scenarios) == 20
    assert scenarios == {f"sc-{seed}" for seed in seeds}


def test_the_fingerprint_is_stable_and_sensitive():
    assert _digest({"a": frozenset({"x", "y"})}) == _digest({"a": frozenset({"y", "x"})})
    assert _digest(MUTATIONS) != _digest({**MUTATIONS, "d6": MUTATIONS["d5"]})


if __name__ == "__main__":
    print(table())
