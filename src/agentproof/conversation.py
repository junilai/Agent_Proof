"""The single place where a conversation becomes a trace.

Recording a conversation with a person and replaying a scenario with the
simulated user are the same loop: user message, agent turn, next user message.
Only who writes the user side changes, so both implement ``UserDriver``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from agentproof import models
from agentproof.schema import Termination, Trace, TraceEvent, TraceKind, Usage, new_trace_id
from agentproof.session import AgentTurn, SessionFactory


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


class _Recorder:
    def __init__(self, clock: Callable[[], datetime]) -> None:
        self.clock = clock
        self.events: list[TraceEvent] = []

    def add(self, kind: str, **fields: Any) -> None:
        step = len(self.events) + 1
        self.events.append(TraceEvent(step=step, kind=kind, ts=self.clock(), **fields))

    def add_turn(self, turn: AgentTurn) -> None:
        for event in turn.events:
            self.add(**event.model_dump())


async def converse(
    session_factory: SessionFactory,
    user: UserDriver,
    context: TraceContext,
    *,
    turn_budget: int | None = None,
    model_config: dict[str, Any] | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> Trace:
    """Run one conversation and return its trace; ``turn_budget=None`` means no limit."""
    recorder = _Recorder(clock)
    usage = Usage()
    history: list[Exchange] = []
    started_at = clock()
    termination: Termination = "user_ended"
    message = await user.first_message()
    async with session_factory() as session:
        while True:
            recorder.add("user_message", text=message)
            turn = await session.send(message)
            recorder.add_turn(turn)
            if turn.usage is not None:
                usage += turn.usage
            history.append(Exchange(message, turn.reply))
            next_message = await user.next_message(history)
            if next_message is None:
                break
            if turn_budget is not None and len(history) >= turn_budget:
                termination = "turn_budget"
                break
            message = next_message
    return Trace(
        trace_id=new_trace_id(),
        **asdict(context),
        termination=termination,
        events=recorder.events,
        models=model_config if model_config is not None else models.snapshot(),
        usage=usage,
        started_at=started_at,
        ended_at=clock(),
    )
