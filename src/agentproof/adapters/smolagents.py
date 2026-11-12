"""smolagents adapter: turns what an agent run yields in a turn into an agent turn.

The only module of AgentProof that imports ``smolagents``. The tool calls, their
results and the reply come from the run's event stream; the step limit and the
tokens come from the memory steps the run added, because the stream does not
yield the step of the forced answer. ``final_answer`` is how the agent replies,
so it is the turn's reply and never a tool call.

smolagents reports tokens but not cost, so the turn is priced with the dated
table in ``agentproof.pricing``, using the model the agent requests, never the id
the response carries. Hitting the step limit is a ``step_limit`` turn, not an
error, and the answer smolagents forces then is the turn's reply.

Each session runs its own agent, built for that conversation, so a conversation
starts empty, and every turn keeps the agent's memory with ``reset=False``. It
refuses to open while litellm would reach a third-party service: its cost map
download at import, a logging callback, or the OpenTelemetry instrumentation.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from smolagents import LogLevel, MultiStepAgent
from smolagents.agents import ToolOutput
from smolagents.memory import ActionStep, FinalAnswerStep, ToolCall
from smolagents.utils import AgentMaxStepsError

from agentproof.pricing import PRICES
from agentproof.schema import Usage
from agentproof.session import AgentEvent, AgentTurn, SessionFactory

COST_MAP_VAR = "LITELLM_LOCAL_MODEL_COST_MAP"
LITELLM_HOOKS = (
    "callbacks",
    "input_callback",
    "success_callback",
    "failure_callback",
    "service_callback",
    "_async_input_callback",
    "_async_success_callback",
    "_async_failure_callback",
)
INSTRUMENTATION = "openinference.instrumentation"
FINAL_ANSWER = "final_answer"
FORCED_ANSWER_ERROR = "Error in generating final LLM output"
"""How smolagents words a model error during the forced answer, which it swallows."""


class TelemetryEnabledError(RuntimeError):
    pass


def ensure_no_telemetry(env: Mapping[str, str] = os.environ) -> None:
    """Checks without importing litellm, which would fetch its cost map on import."""
    if env.get(COST_MAP_VAR, "").strip().lower() != "true":
        raise TelemetryEnabledError(
            f"litellm descargaría su mapa de costos de GitHub: defina {COST_MAP_VAR}=True "
            "antes de correr"
        )
    if any(name.startswith(INSTRUMENTATION) for name in sys.modules):
        raise TelemetryEnabledError(
            "la instrumentación OpenTelemetry de smolagents está cargada: no la importe"
        )
    litellm = sys.modules.get("litellm")
    if litellm is None:
        return
    hooks = [name for name in LITELLM_HOOKS if getattr(litellm, name, None)]
    if hooks:
        raise TelemetryEnabledError(
            f"litellm enviaría los datos del agente a otro servicio ({', '.join(hooks)}): "
            "quite esos callbacks antes de correr"
        )
    from litellm.litellm_core_utils.get_model_cost_map import get_model_cost_map_source_info

    if not get_model_cost_map_source_info().get("is_env_forced"):
        raise TelemetryEnabledError(
            f"litellm se importó sin {COST_MAP_VAR}=True y ya buscó su mapa de costos: "
            "defínala antes de arrancar"
        )


def _arguments(arguments: Any) -> dict[str, Any]:
    return arguments if isinstance(arguments, dict) else {"input": arguments}


def _value(output: Any) -> Any:
    return str(output) if isinstance(output, str) else output


def _text(output: Any) -> str:
    if isinstance(output, list):
        return "".join(b.get("text", "") for b in output if isinstance(b, dict))
    return "" if output is None else str(output)


def _usage(steps: Sequence[ActionStep], model: str | None) -> Usage:
    usages = [s.token_usage for s in steps if s.token_usage is not None]
    tokens_in = sum(u.input_tokens for u in usages)
    tokens_out = sum(u.output_tokens for u in usages)
    cost = None
    if model in PRICES:
        per_input, per_output = PRICES[model]
        cost = (tokens_in * per_input + tokens_out * per_output) / 1e6
    return Usage(input_tokens=tokens_in, output_tokens=tokens_out, cost_usd=cost)


def turn_from_run(events: Sequence[Any], steps: Sequence[Any], *, model: str | None) -> AgentTurn:
    """``events``: what ``run(stream=True)`` yielded; ``steps``: the memory steps it added.

    When a step fails, smolagents tells the model only the error, even if some of
    its tools already ran: each of that step's calls is then ``is_error``, with its
    result if the stream yielded one and the error otherwise.
    """
    out: list[AgentEvent] = []
    in_step: list[int] = []
    answered: set[int] = set()
    by_id: dict[str, int] = {}
    reply: Any = None
    for event in events:
        if isinstance(event, ToolCall) and event.name != FINAL_ANSWER:
            by_id[event.id] = len(out)
            in_step.append(len(out))
            out.append(
                AgentEvent(kind="tool_call", tool=event.name, arguments=_arguments(event.arguments))
            )
        elif isinstance(event, ToolOutput) and event.id in by_id:
            index = by_id[event.id]
            answered.add(index)
            out[index] = out[index].model_copy(update={"result": _value(event.output)})
        elif isinstance(event, ActionStep):
            if event.error is not None:
                for index in in_step:
                    update: dict[str, Any] = {"is_error": True}
                    if index not in answered:
                        update["result"] = str(event.error)
                    out[index] = out[index].model_copy(update=update)
            in_step = []
        elif isinstance(event, FinalAnswerStep):
            reply = event.output
    actions = [s for s in steps if isinstance(s, ActionStep)]
    usage = _usage(actions, model)
    text = _text(reply)
    if isinstance(reply, list) or text.startswith(FORCED_ANSWER_ERROR):
        out.append(AgentEvent(kind="error", text=text))
        return AgentTurn(reply="", events=out, stop_reason="error", usage=usage)
    if text:
        out.append(AgentEvent(kind="agent_message", text=text))
    cut = any(isinstance(s.error, AgentMaxStepsError) for s in actions)
    return AgentTurn(
        reply=text, events=out, stop_reason="step_limit" if cut else "completed", usage=usage
    )


class SmolagentsSession:
    """One conversation with a smolagents agent, which keeps the memory itself."""

    def __init__(self, agent: MultiStepAgent) -> None:
        self.agent = agent

    async def __aenter__(self) -> SmolagentsSession:
        ensure_no_telemetry()
        self.agent.logger.level = LogLevel.OFF
        return self

    async def send(self, message: str) -> AgentTurn:
        events, steps, error = await asyncio.to_thread(self._run, message)
        model = getattr(self.agent.model, "model_id", None)
        requested = model.removeprefix("anthropic/") if model else None
        turn = turn_from_run(events, steps, model=requested)
        if error is None:
            return turn
        failure = AgentEvent(kind="error", text=f"{type(error).__name__}: {error}")
        return turn.model_copy(update={"events": [*turn.events, failure], "stop_reason": "error"})

    def _run(self, message: str) -> tuple[list[Any], list[Any], Exception | None]:
        before = len(self.agent.memory.steps)
        events: list[Any] = []
        error: Exception | None = None
        try:
            for event in self.agent.run(message, stream=True, reset=False):
                events.append(event)
        except Exception as exc:  # a failed model call ends the run
            error = exc
        return events, self.agent.memory.steps[before:], error

    async def __aexit__(self, *exc_info: object) -> None:
        return None


def session_factory(agent: Callable[[str], MultiStepAgent], variant: str) -> SessionFactory:
    """The adapter convention: a fresh agent, with an empty memory, per conversation.

    Checks telemetry here too, so a batch fails before its first conversation.
    """
    ensure_no_telemetry()
    return lambda: SmolagentsSession(agent(variant))
