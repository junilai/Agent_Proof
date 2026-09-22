"""The single place where a conversation becomes a trace.

Recording a conversation with a person and replaying a scenario with the
simulated user are the same loop: user message, agent turn, next user message.
Only who writes the user side changes, so both implement ``UserDriver``.

Whatever happens, ``converse`` returns exactly one trace: failures become error
events and a termination reason, never ordinary exceptions.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
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


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


@dataclass
class _Outcome:
    """How the conversation ended; ``agent_error`` until something decides otherwise."""

    termination: Termination = "agent_error"
    usage: Usage = field(default_factory=Usage)

    def end(self, termination: Termination) -> None:
        self.termination = termination


async def _dialogue(
    session: Any,
    user: UserDriver,
    message: str,
    recorder: _Recorder,
    outcome: _Outcome,
    turn_budget: int | None,
) -> None:
    history: list[Exchange] = []
    while True:
        recorder.add("user_message", text=message)
        try:
            turn = await session.send(message)
        except Exception as exc:
            recorder.add("error", text=_describe(exc))
            return outcome.end("agent_error")
        recorder.add_turn(turn)
        if turn.usage is not None:
            outcome.usage += turn.usage
        history.append(Exchange(message, turn.reply))
        if turn.stop_reason != "completed":
            return outcome.end("step_limit" if turn.stop_reason == "step_limit" else "agent_error")
        try:
            next_message = await user.next_message(history)
        except Exception as exc:
            recorder.add("error", text=_describe(exc))
            return outcome.end("simulator_error")
        if next_message is None:
            return outcome.end("user_ended")
        if turn_budget is not None and len(history) >= turn_budget:
            return outcome.end("turn_budget")
        message = next_message


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
    outcome = _Outcome()
    started_at = clock()
    try:
        message = await user.first_message()
    except Exception as exc:
        recorder.add("error", text=_describe(exc))
        outcome.end("simulator_error")
    else:
        try:
            async with session_factory() as session:
                await _dialogue(session, user, message, recorder, outcome, turn_budget)
        except Exception as exc:  # opening or closing the session failed, or a malformed turn
            recorder.add("error", text=_describe(exc))
    return Trace(
        trace_id=new_trace_id(),
        **asdict(context),
        termination=outcome.termination,
        events=recorder.events,
        models=model_config if model_config is not None else models.snapshot(),
        usage=outcome.usage,
        started_at=started_at,
        ended_at=clock(),
    )
