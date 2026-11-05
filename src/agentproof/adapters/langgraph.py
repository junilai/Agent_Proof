"""LangGraph adapter: turns the messages a graph adds in a turn into an agent turn.

The only module of AgentProof that imports ``langgraph`` or ``langchain_core``.
LangChain reports tokens but not cost, so the turn is priced with the dated
table in ``agentproof.pricing``, using the model the graph requested, never the
id the response carries. Hitting the step limit is a ``step_limit`` turn, not
an error.

Each session compiles the graph with its own in-memory checkpointer and thread,
so a conversation starts empty, and it refuses to open while LangChain would
send traces to a third-party service.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph

from agentproof.pricing import PRICES
from agentproof.schema import Usage
from agentproof.session import AgentEvent, AgentTurn, SessionFactory

TRACING_VARS = ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING")
STEP_LIMIT_KEY = "step_limit_reached"


class TracingEnabledError(RuntimeError):
    pass


def ensure_no_tracing(env: Mapping[str, str] = os.environ) -> None:
    enabled = [var for var in TRACING_VARS if env.get(var, "").strip().lower() in ("true", "1")]
    if enabled:
        raise TracingEnabledError(
            f"el envío de trazas de LangChain está activo ({', '.join(enabled)}): "
            f"defina {enabled[0]}=false antes de correr"
        )


def _texts(message: AIMessage) -> list[str]:
    content = message.content
    if isinstance(content, str):
        return [content] if content.strip() else []
    blocks = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
    return [text for text in blocks if text.strip()]


def _result_value(content: Any) -> Any:
    if isinstance(content, list):
        content = "".join(b.get("text", "") for b in content if isinstance(b, dict))
    if not isinstance(content, str):
        return content
    try:
        return json.loads(content)
    except ValueError:
        return content


def _usage(messages: Sequence[AIMessage], model: str | None) -> Usage:
    tokens_in = sum((m.usage_metadata or {}).get("input_tokens", 0) for m in messages)
    tokens_out = sum((m.usage_metadata or {}).get("output_tokens", 0) for m in messages)
    cost = None
    if model in PRICES:
        per_input, per_output = PRICES[model]
        cost = (tokens_in * per_input + tokens_out * per_output) / 1e6
    return Usage(input_tokens=tokens_in, output_tokens=tokens_out, cost_usd=cost)


def turn_from_messages(
    new: Sequence[BaseMessage], *, step_limit_reached: bool, model: str | None
) -> AgentTurn:
    events: list[AgentEvent] = []
    texts: list[str] = []
    pending: dict[str, int] = {}
    replies = [m for m in new if isinstance(m, AIMessage)]
    for message in new:
        if isinstance(message, AIMessage):
            for text in _texts(message):
                texts.append(text)
                events.append(AgentEvent(kind="agent_message", text=text))
            for call in message.tool_calls:
                pending[call["id"]] = len(events)
                events.append(
                    AgentEvent(kind="tool_call", tool=call["name"], arguments=call["args"])
                )
        elif isinstance(message, ToolMessage) and message.tool_call_id in pending:
            index = pending.pop(message.tool_call_id)
            update = {
                "result": _result_value(message.content),
                "is_error": message.status == "error",
            }
            events[index] = events[index].model_copy(update=update)
    return AgentTurn(
        reply="\n".join(texts),
        events=events,
        stop_reason="step_limit" if step_limit_reached else "completed",
        usage=_usage(replies, model),
    )


class _RequestedModel(BaseCallbackHandler):
    """Remembers the model the graph asked for, which is the variant's model."""

    run_inline = True

    def __init__(self) -> None:
        self.model: str | None = None

    def on_chat_model_start(self, serialized: Any, messages: Any, **kwargs: Any) -> None:
        self.model = (kwargs.get("invocation_params") or {}).get("model") or self.model


class LangGraphSession:
    """One conversation with a LangGraph agent, with memory of its own."""

    def __init__(self, graph: StateGraph) -> None:
        self.graph = graph
        self._app: Any = None
        self._thread = ""

    async def __aenter__(self) -> LangGraphSession:
        ensure_no_tracing()
        self._app = self.graph.compile(checkpointer=InMemorySaver())
        self._thread = uuid.uuid4().hex
        return self

    async def send(self, message: str) -> AgentTurn:
        requested = _RequestedModel()
        config = {"configurable": {"thread_id": self._thread}, "callbacks": [requested]}
        before = len((await self._app.aget_state(config)).values.get("messages", []))
        try:
            state = await self._app.ainvoke({"messages": [HumanMessage(message)]}, config)
        except Exception as exc:
            error = AgentEvent(kind="error", text=f"{type(exc).__name__}: {exc}")
            return AgentTurn(reply="", events=[error], stop_reason="error")
        return turn_from_messages(
            state["messages"][before:],
            step_limit_reached=bool(state.get(STEP_LIMIT_KEY)),
            model=requested.model,
        )

    async def __aexit__(self, *exc_info: object) -> None:
        self._app = None


def session_factory(agent: Callable[[str], StateGraph], variant: str) -> SessionFactory:
    """The adapter convention: a fresh session, with an empty memory, per conversation."""
    return lambda: LangGraphSession(agent(variant))
