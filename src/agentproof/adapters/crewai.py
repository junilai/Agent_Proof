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

import json
import os
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from crewai import Agent
from crewai.events.listeners.tracing.utils import should_enable_tracing
from crewai.telemetry.telemetry import Telemetry
from crewai.types.usage_metrics import UsageMetrics

from agentproof.pricing import PRICES
from agentproof.schema import Usage
from agentproof.session import AgentEvent, AgentTurn, SessionFactory

TELEMETRY_VARS = ("CREWAI_DISABLE_TELEMETRY", "OTEL_SDK_DISABLED", "CREWAI_DISABLE_TRACKING")
TRACING_VAR = "CREWAI_TRACING_ENABLED"
TOOL_ERROR_PREFIX = "Error executing tool:"
"""What CrewAI writes as the result of a tool that raised; no domain tool returns it."""


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


def _value(content: Any) -> Any:
    if not isinstance(content, str):
        return content
    try:
        return json.loads(content)
    except ValueError:
        return content


def _usage(metrics: UsageMetrics, model: str | None) -> Usage:
    tokens_in, tokens_out = metrics.prompt_tokens, metrics.completion_tokens
    cost = None
    if model in PRICES:
        per_input, per_output = PRICES[model]
        cost = (tokens_in * per_input + tokens_out * per_output) / 1e6
    return Usage(input_tokens=tokens_in, output_tokens=tokens_out, cost_usd=cost)


def _ends_with_text(messages: Sequence[Mapping[str, Any]]) -> bool:
    """Whether CrewAI stored the final answer; it never stores a forced one."""
    return bool(messages) and messages[-1]["role"] == "assistant" and bool(messages[-1]["content"])


def turn_from_messages(
    new: Sequence[Mapping[str, Any]],
    *,
    reply: str,
    step_limit_reached: bool,
    metrics: UsageMetrics,
    model: str | None,
) -> AgentTurn:
    """``new`` holds the messages after this turn's request, in CrewAI's OpenAI-style dicts.

    A reply CrewAI did not store, such as the forced answer after a cut, is added last.
    """
    events: list[AgentEvent] = []
    pending: dict[str, int] = {}
    for message in new:
        if message["role"] == "assistant":
            if isinstance(message.get("content"), str) and message["content"].strip():
                events.append(AgentEvent(kind="agent_message", text=message["content"]))
            for call in message.get("tool_calls") or []:
                pending[call["id"]] = len(events)
                function = call["function"]
                events.append(
                    AgentEvent(
                        kind="tool_call",
                        tool=function["name"],
                        arguments=_value(function["arguments"]) or {},
                    )
                )
        elif message["role"] == "tool" and message.get("tool_call_id") in pending:
            index = pending.pop(message["tool_call_id"])
            content = message.get("content")
            update = {
                "result": _value(content),
                "is_error": isinstance(content, str) and content.startswith(TOOL_ERROR_PREFIX),
            }
            events[index] = events[index].model_copy(update=update)
    if reply.strip() and not _ends_with_text(new):
        events.append(AgentEvent(kind="agent_message", text=reply))
    return AgentTurn(
        reply=reply,
        events=events,
        stop_reason="step_limit" if step_limit_reached else "completed",
        usage=_usage(metrics, model),
    )


def _without_system(messages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The history to pass back: CrewAI rebuilds the system message on every kickoff."""
    return [
        {k: v for k, v in m.items() if k != "cache_breakpoint"}
        for m in messages
        if m["role"] != "system"
    ]


class CrewAISession:
    """One conversation with a CrewAI agent: one kickoff per customer message.

    The session keeps the history (without the system message) and passes it on
    every kickoff.
    """

    def __init__(self, agent: Agent) -> None:
        self.agent = agent
        self.history: list[dict[str, Any]] = []

    async def __aenter__(self) -> CrewAISession:
        ensure_no_telemetry()
        return self

    async def send(self, message: str) -> AgentTurn:
        request = [*self.history, {"role": "user", "content": message}]
        start = len(self.history) + 2  # system + history + this turn's request
        before = self.agent.llm.get_token_usage_summary()
        model = self.agent.llm.model
        try:
            output = await self.agent.kickoff_async(request)
        except Exception as exc:
            self.history = request
            metrics = self.agent.llm.get_token_usage_summary().delta_since(before)
            turn = turn_from_messages(
                [], reply="", step_limit_reached=False, metrics=metrics, model=model
            )
            error = AgentEvent(kind="error", text=f"{type(exc).__name__}: {exc}")
            return turn.model_copy(update={"events": [*turn.events, error], "stop_reason": "error"})
        new = output.messages[start:]
        rounds = sum(1 for m in new if m["role"] == "assistant" and m.get("tool_calls"))
        cut = rounds >= self.agent.max_iter
        self.history = _without_system(output.messages)
        if not _ends_with_text(new):
            self.history.append({"role": "assistant", "content": output.raw})
        metrics = self.agent.llm.get_token_usage_summary().delta_since(before)
        return turn_from_messages(
            new, reply=output.raw, step_limit_reached=cut, metrics=metrics, model=model
        )

    async def __aexit__(self, *exc_info: object) -> None:
        return None


def session_factory(agent: Callable[[str], Agent], variant: str) -> SessionFactory:
    """The adapter convention: a fresh agent and session, with an empty history, per conversation.

    Checks telemetry here too, so a batch fails before its first conversation.
    """
    ensure_no_telemetry()
    return lambda: CrewAISession(agent(variant))
