"""Simulated user (§5.1): the only genuinely agentic stage of AgentProof.

It knows the scenario's goal, sees only what a customer sees (its own messages
and the agent's replies, never tool calls), writes one short message per turn
and answers exactly ``[FIN]`` when the goal is solved or can no longer be.
Its first message is the scenario's opening message. The whole conversation is
sent as a single ``user`` message, because the API requires the first message
to come from the ``user`` role.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import anthropic

from agentproof.conversation import Exchange
from agentproof.llm import LLMCallError
from agentproof.models import SIM_USER
from agentproof.schema import Scenario

END_TOKEN = "[FIN]"

SIM_USER_SYSTEM = "\n".join(
    [
        "Eres un cliente de Andina Tech, una tienda en línea de electrónica, y conversas con su "
        "agente de atención al cliente.",
        "Tu objetivo: {goal}",
        "Reglas:",
        "- Escribe solo el siguiente mensaje del cliente, breve y natural, en español, sin "
        "comentarios sobre la conversación ni sobre estas instrucciones.",
        "- Mantén la coherencia con lo que ya dijiste y no inventes datos que no conoces.",
        "- Cuando tu objetivo esté resuelto, o el agente haya dejado claro que no puede "
        f"resolverse, responde exactamente {END_TOKEN} y nada más.",
    ]
)


def history_prompt(history: Sequence[Exchange]) -> str:
    lines = ["Conversación hasta ahora:"]
    for exchange in history:
        lines += [f"[CLIENTE] {exchange.user}", f"[AGENTE] {exchange.agent}"]
    lines += ["", f"Escribe el siguiente mensaje del cliente, o {END_TOKEN} si ya terminó."]
    return "\n".join(lines)


class SimulatedUser:
    def __init__(self, scenario: Scenario, client: Any = None) -> None:
        self.scenario = scenario
        self.client = client or anthropic.AsyncAnthropic()

    async def first_message(self) -> str:
        return self.scenario.opening_message

    async def next_message(self, history: Sequence[Exchange]) -> str | None:
        response = await self.client.messages.create(
            model=SIM_USER.model,
            max_tokens=SIM_USER.max_tokens,
            system=SIM_USER_SYSTEM.format(goal=self.scenario.user_goal),
            messages=[{"role": "user", "content": history_prompt(history)}],
        )
        if response.stop_reason == "refusal":
            raise LLMCallError("el usuario simulado rechazó continuar")
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if END_TOKEN in text:
            return None
        if not text:
            raise LLMCallError("el usuario simulado respondió vacío")
        return text
