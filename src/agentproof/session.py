"""Contract between the AgentProof core and the framework adapters (§5.7).

An adapter only translates: for each user message it returns the agent's turn.
It never numbers events, builds traces or stores anything; ``converse`` does,
in one place, for every framework.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from agentproof.schema import Usage

StopReason = Literal["completed", "step_limit", "error"]


class AgentEvent(BaseModel):
    """Something the agent did during a turn, as the adapter observed it."""

    kind: Literal["agent_message", "tool_call", "error"]
    text: str | None = None
    tool: str | None = None
    arguments: dict[str, Any] | None = None
    result: Any = None
    is_error: bool = False


class AgentTurn(BaseModel):
    """The agent's answer to one user message; ``reply`` is what the user sees."""

    reply: str
    events: list[AgentEvent] = Field(default_factory=list)
    stop_reason: StopReason = "completed"
    usage: Usage | None = None


@runtime_checkable
class AgentSession(Protocol):
    async def __aenter__(self) -> AgentSession: ...

    async def __aexit__(self, *exc_info: object) -> None: ...

    async def send(self, message: str) -> AgentTurn: ...


SessionFactory = Callable[[], AgentSession]
