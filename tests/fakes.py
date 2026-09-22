"""Fake users and sessions for testing the core without any API."""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Self

from pydantic import BaseModel, ValidationError

from agentproof.conversation import Exchange, TraceContext
from agentproof.schema import Usage
from agentproof.session import AgentEvent, AgentTurn

SEED = TraceContext(kind="seed", adapter="fake", agent="tests:fake", variant="baseline")
RUN = TraceContext(
    kind="run",
    adapter="fake",
    agent="tests:fake",
    variant="baseline",
    condition="baseline-a",
    run_id="baseline-a-20261001-120000",
    scenario_id="sc-tr-000000000001",
    repetition=3,
)


class ScriptedUser:
    def __init__(self, *messages: str) -> None:
        self.messages = list(messages)
        self.seen: list[list[Exchange]] = []

    async def first_message(self) -> str:
        return self.messages.pop(0)

    async def next_message(self, history: Sequence[Exchange]) -> str | None:
        self.seen.append(list(history))
        return self.messages.pop(0) if self.messages else None


class EchoSession:
    """Looks up an order, answers with an echo and reports some usage."""

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.closed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self.closed = True

    async def send(self, message: str) -> AgentTurn:
        self.sent.append(message)
        reply = f"eco: {message}"
        lookup = AgentEvent(
            kind="tool_call",
            tool="lookup_order",
            arguments={"order_id": "AT-1001"},
            result={"estado": "entregado"},
        )
        return AgentTurn(
            reply=reply,
            events=[lookup, AgentEvent(kind="agent_message", text=reply)],
            usage=Usage(input_tokens=10, output_tokens=5, cost_usd=0.25),
        )


class CrashingSession(EchoSession):
    """Its agent fails on every message."""

    async def send(self, message: str) -> AgentTurn:
        raise RuntimeError("se cayó la conexión")


def ticking_clock(start: datetime = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)) -> Callable:
    current = [start]

    def tick() -> datetime:
        current[0] += timedelta(seconds=1)
        return current[0]

    return tick


class _FakeParseMessages:
    def __init__(self, outcomes: list) -> None:
        self.outcomes = outcomes
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeLLM:
    """Stands in for ``anthropic.Anthropic``: each call returns the next scripted outcome."""

    def __init__(self, *outcomes) -> None:
        self.messages = _FakeParseMessages(list(outcomes))


def parsed(value, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(parsed_output=value, stop_reason=stop_reason)


class _Anything(BaseModel):
    required: int


def validation_error() -> ValidationError:
    try:
        _Anything.model_validate_json("{}")
    except ValidationError as exc:
        return exc
    raise AssertionError("unreachable")


class _FakeCreateMessages:
    def __init__(self, replies: list) -> None:
        self.replies = replies
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.replies.pop(0)


class FakeAsyncLLM:
    """Stands in for ``anthropic.AsyncAnthropic`` in the simulated user."""

    def __init__(self, *replies) -> None:
        self.messages = _FakeCreateMessages(list(replies))


def reply(text: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    content = [SimpleNamespace(type="text", text=text)]
    return SimpleNamespace(content=content, stop_reason=stop_reason)
