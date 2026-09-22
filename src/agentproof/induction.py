"""Scenario inducer (§5.1): one seed trace in, one conversational scenario out.

A single structured pass with the pinned inducer model. The criteria describe
the outcome communicated to the user, never which tool to call or in which
order: the thesis separates a conversational scenario from a trajectory
contract.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import anthropic
from pydantic import BaseModel

from agentproof.conversation import utc_now
from agentproof.llm import structured_call
from agentproof.models import INDUCER
from agentproof.schema import Scenario, Trace, scenario_id_for
from agentproof.store import Store
from agentproof.transcript import render_transcript

INDUCTION_SYSTEM = "\n".join(
    [
        "Construyes una suite de pruebas de regresión para un agente de atención al cliente.",
        "Recibirás la transcripción de una conversación real entre un cliente y el agente. "
        "A partir de ella, induce un escenario de prueba:",
        "- user_goal: qué quería lograr el cliente, en una oración, con los datos concretos que "
        "aportó (por ejemplo, el número de pedido y el motivo).",
        "- opening_message: el primer mensaje natural con el que un cliente iniciaría una "
        "conversación equivalente. Conserva la intención y los identificadores concretos, pero "
        "no copies el mensaje original palabra por palabra.",
        "- success_criteria: entre 2 y 5 afirmaciones verificables sobre el desenlace que el "
        "agente debe comunicar al cliente para resolver bien el caso, según los datos del pedido "
        "y la política que aparecen en la transcripción. Cada criterio debe poder comprobarse "
        "leyendo solo una transcripción. Describe qué debe saber o recibir el cliente al final, "
        "nunca qué herramienta debe usar el agente ni en qué orden.",
        "Escribe todo en español.",
    ]
)


class ScenarioDraft(BaseModel):
    """What the inducer model returns; identifiers and dates are added by the code."""

    user_goal: str
    opening_message: str
    success_criteria: list[str]


def induction_prompt(seed: Trace) -> str:
    return "TRANSCRIPCIÓN DE LA CONVERSACIÓN:\n" + render_transcript(seed)


def induce_scenario(
    seed: Trace,
    client: Any = None,
    clock: Callable[[], datetime] = utc_now,
) -> Scenario:
    if seed.kind != "seed":
        raise ValueError(f"only seed traces are induced: {seed.trace_id}")

    def to_scenario(draft: ScenarioDraft) -> Scenario:
        return Scenario(
            scenario_id=scenario_id_for(seed.trace_id),
            seed_trace_id=seed.trace_id,
            user_goal=draft.user_goal.strip(),
            opening_message=draft.opening_message.strip(),
            success_criteria=[c.strip() for c in draft.success_criteria if c.strip()],
            induced_by=INDUCER.model,
            created_at=clock(),
        )

    return structured_call(
        client or anthropic.Anthropic(),
        INDUCER,
        system=INDUCTION_SYSTEM,
        prompt=induction_prompt(seed),
        output_type=ScenarioDraft,
        validate=to_scenario,
    )


@dataclass
class InductionSummary:
    created: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)


def induce_missing(
    store: Store, induce: Callable[[Trace], Scenario] = induce_scenario
) -> InductionSummary:
    """Induce the scenario of every seed that does not have one yet; never twice."""
    summary = InductionSummary()
    for seed in store.seeds():
        scenario_id = scenario_id_for(seed.trace_id)
        if store.has_scenario(scenario_id):
            summary.kept.append(scenario_id)
            continue
        try:
            store.save_scenario(induce(seed))
        except Exception as exc:
            summary.failed[scenario_id] = f"{type(exc).__name__}: {exc}"
        else:
            summary.created.append(scenario_id)
    return summary
