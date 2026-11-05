"""LangGraph adapter: turns the messages a graph adds in a turn into an agent turn.

The only module of AgentProof that imports ``langgraph`` or ``langchain_core``.
LangChain reports tokens but not cost, so the turn is priced with the dated
table in ``agentproof.pricing``, using the model the graph requested, never the
id the response carries. Hitting the step limit is a ``step_limit`` turn, not
an error.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from agentproof.pricing import PRICES
from agentproof.schema import Usage
from agentproof.session import AgentEvent, AgentTurn


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
