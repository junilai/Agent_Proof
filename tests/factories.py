"""Builders of valid schema objects for the tests."""

from datetime import UTC, datetime

from agentproof.schema import Trace, TraceEvent

T0 = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)

RUN_FIELDS = {
    "condition": "baseline-a",
    "run_id": "baseline-a-20261001-120000",
    "scenario_id": "sc-tr-000000000001",
    "repetition": 1,
}


def event(step: int, kind: str, **fields) -> TraceEvent:
    return TraceEvent(step=step, kind=kind, ts=T0, **fields)


def trace(kind: str = "seed", events: list[TraceEvent] | None = None, **overrides) -> Trace:
    fields = {
        "trace_id": "tr-000000000001",
        "kind": kind,
        "adapter": "fake",
        "agent": "tests:fake",
        "variant": "baseline",
        "termination": "user_ended",
        "events": events
        if events is not None
        else [
            event(1, "user_message", text="Hola"),
            event(2, "agent_message", text="¿En qué le ayudo?"),
        ],
        "models": {"judge": "claude-opus-5"},
        "started_at": T0,
        "ended_at": T0,
    }
    if kind == "run":
        fields.update(RUN_FIELDS)
    fields.update(overrides)
    return Trace(**fields)
