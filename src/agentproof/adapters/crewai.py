"""CrewAI adapter: turns the messages an agent's kickoff adds in a turn into an agent turn.

The only module of AgentProof that imports ``crewai``. CrewAI reports tokens but
not cost, so the turn is priced with the dated table in ``agentproof.pricing``,
using the model the agent requested (CrewAI strips the ``anthropic/`` prefix),
never the id the response carries. Hitting ``max_iter`` is a ``step_limit``
turn, not an error, and the forced final answer CrewAI then asks for is the reply.

CrewAI's Anthropic provider always marks prompt-cache breakpoints, and its input
tokens include the cached ones, which the table prices as plain input: the
thesis takes this edition's cost from the billing console, as for the agent of
the Claude Agent SDK edition (D-007).

Each session talks to its own agent and keeps the conversation history itself,
so a conversation starts empty. It refuses to open while CrewAI would send
telemetry or execution traces out.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from crewai.events.listeners.tracing.utils import should_enable_tracing
from crewai.telemetry.telemetry import Telemetry

TELEMETRY_VARS = ("CREWAI_DISABLE_TELEMETRY", "OTEL_SDK_DISABLED", "CREWAI_DISABLE_TRACKING")
TRACING_VAR = "CREWAI_TRACING_ENABLED"


class TelemetryEnabledError(RuntimeError):
    pass


def _flag(env: Mapping[str, str], var: str) -> str:
    return env.get(var, "").strip().lower()


def ensure_no_telemetry(env: Mapping[str, str] = os.environ) -> None:
    """Fails unless both of CrewAI's channels are off: telemetry and execution traces."""
    telemetry_off = any(_flag(env, var) in ("true", "1", "yes", "on") for var in TELEMETRY_VARS)
    if not telemetry_off or not Telemetry._is_telemetry_disabled():
        raise TelemetryEnabledError(
            "la telemetría de CrewAI está activa: defina CREWAI_DISABLE_TELEMETRY=true "
            "antes de correr"
        )
    if _flag(env, TRACING_VAR) in ("true", "1") or should_enable_tracing():
        raise TelemetryEnabledError(
            "CrewAI enviaría las trazas del agente: defina CREWAI_TRACING_ENABLED=false "
            "antes de correr"
        )
