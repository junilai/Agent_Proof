"""Claude Agent SDK adapter: turns the SDK's message stream into agent turns.

The only module of AgentProof that imports ``claude_agent_sdk``. Tool names lose
the MCP prefix (``mcp__store__lookup_order`` -> ``lookup_order``) so traces are
comparable across frameworks, and hitting the step limit is a ``step_limit``
turn, not an error.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from agentproof.schema import Usage
from agentproof.session import AgentEvent, AgentTurn, StopReason

_INPUT_TOKEN_KEYS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def tool_name(name: str) -> str:
    if name.startswith("mcp__") and name.count("__") >= 2:
        return name.split("__", 2)[2]
    return name


def _result_value(content: Any) -> Any:
    if isinstance(content, list):
        content = "".join(b.get("text", "") for b in content if isinstance(b, dict))
    if not isinstance(content, str):
        return content
    try:
        return json.loads(content)
    except ValueError:
        return content


def _usage(result: ResultMessage) -> Usage:
    raw = result.usage or {}
    return Usage(
        input_tokens=sum(raw.get(key) or 0 for key in _INPUT_TOKEN_KEYS),
        output_tokens=raw.get("output_tokens") or 0,
        cost_usd=result.total_cost_usd,
    )


def turn_from_messages(messages: Sequence[Any]) -> AgentTurn:
    events: list[AgentEvent] = []
    texts: list[str] = []
    pending: dict[str, int] = {}
    stop: StopReason | None = None
    usage: Usage | None = None
    for message in messages:
        if isinstance(message, AssistantMessage):
            if message.error:
                events.append(
                    AgentEvent(kind="error", text=f"error del asistente: {message.error}")
                )
            for block in message.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    texts.append(block.text)
                    events.append(AgentEvent(kind="agent_message", text=block.text))
                elif isinstance(block, ToolUseBlock):
                    pending[block.id] = len(events)
                    call = AgentEvent(
                        kind="tool_call", tool=tool_name(block.name), arguments=dict(block.input)
                    )
                    events.append(call)
        elif isinstance(message, UserMessage) and isinstance(message.content, list):
            for block in message.content:
                if isinstance(block, ToolResultBlock) and block.tool_use_id in pending:
                    index = pending.pop(block.tool_use_id)
                    update = {
                        "result": _result_value(block.content),
                        "is_error": bool(block.is_error),
                    }
                    events[index] = events[index].model_copy(update=update)
        elif isinstance(message, ResultMessage):
            usage = _usage(message)
            if message.subtype == "error_max_turns" or message.terminal_reason == "max_turns":
                stop = "step_limit"
            elif message.is_error:
                stop = "error"
                detail = message.errors or [message.subtype]
                if message.api_error_status:
                    detail = [*detail, f"HTTP {message.api_error_status}"]
                events.append(AgentEvent(kind="error", text="; ".join(detail)))
            else:
                stop = "completed"
    if stop is None:
        stop = "error"
        events.append(AgentEvent(kind="error", text="la sesión terminó sin mensaje de resultado"))
    return AgentTurn(reply="\n".join(texts), events=events, stop_reason=stop, usage=usage)
