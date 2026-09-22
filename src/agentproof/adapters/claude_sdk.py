"""Claude Agent SDK adapter: turns the SDK's message stream into agent turns.

The only module of AgentProof that imports ``claude_agent_sdk``. Tool names lose
the MCP prefix (``mcp__store__lookup_order`` -> ``lookup_order``) so traces are
comparable across frameworks, and hitting the step limit is a ``step_limit``
turn, not an error.

Each session runs in a fresh working directory with its own empty SDK
configuration directory, so nothing from the machine (settings, instruction files,
memory, plugins, account connectors) reaches the agent under test.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
import tempfile
from collections.abc import Callable, Sequence
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from agentproof.schema import Usage
from agentproof.session import AgentEvent, AgentTurn, SessionFactory, StopReason

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


class ClaudeSDKSession:
    """One conversation with a Claude Agent SDK agent, isolated from the machine."""

    def __init__(
        self,
        options: ClaudeAgentOptions,
        client_factory: Callable[[ClaudeAgentOptions], Any] = ClaudeSDKClient,
    ) -> None:
        self.options = options
        self.client_factory = client_factory
        self._client: Any = None
        self._dirs: list[str] = []

    async def __aenter__(self) -> ClaudeSDKSession:
        workdir = tempfile.mkdtemp(prefix="agentproof-agent-")
        config = tempfile.mkdtemp(prefix="agentproof-claude-config-")
        self._dirs = [workdir, config]
        env = {**self.options.env, "CLAUDE_CONFIG_DIR": config}
        try:
            self._client = self.client_factory(
                dataclasses.replace(self.options, cwd=workdir, env=env)
            )
            await self._client.connect()
        except BaseException:
            self._cleanup()
            raise
        return self

    async def send(self, message: str) -> AgentTurn:
        await self._client.query(message)
        return turn_from_messages([m async for m in self._client.receive_response()])

    async def __aexit__(self, *exc_info: object) -> None:
        try:
            await self._client.disconnect()
        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        for path in self._dirs:
            shutil.rmtree(path, ignore_errors=True)


def session_factory(agent: Callable[[str], ClaudeAgentOptions], variant: str) -> SessionFactory:
    """The adapter convention: a fresh isolated session per conversation."""
    return lambda: ClaudeSDKSession(agent(variant))
