"""The single place where a conversation becomes a trace.

Recording a conversation with a person and replaying a scenario with the
simulated user are the same loop: user message, agent turn, next user message.
Only who writes the user side changes, so both implement ``UserDriver``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from agentproof.schema import TraceKind


@dataclass(frozen=True)
class Exchange:
    """One round as the user sees it: what they wrote and what the agent answered."""

    user: str
    agent: str


class UserDriver(Protocol):
    async def first_message(self) -> str: ...

    async def next_message(self, history: Sequence[Exchange]) -> str | None:
        """The next user message, or ``None`` when the user ends the conversation."""
        ...


@dataclass(frozen=True)
class TraceContext:
    """What the conversation belongs to; copied as-is into the trace."""

    kind: TraceKind
    adapter: str
    agent: str
    variant: str
    condition: str | None = None
    run_id: str | None = None
    scenario_id: str | None = None
    repetition: int | None = None


def utc_now() -> datetime:
    return datetime.now(UTC)
