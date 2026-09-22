"""Builders of valid schema objects for the tests."""

from datetime import UTC, datetime

from agentproof.schema import CriterionResult, RunManifest, Scenario, Trace, TraceEvent, Verdict

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


def scenario(**overrides) -> Scenario:
    fields = {
        "scenario_id": "sc-tr-000000000001",
        "seed_trace_id": "tr-000000000001",
        "user_goal": "Obtener el reembolso de unos audífonos que llegaron dañados",
        "opening_message": "Hola, mis audífonos del pedido AT-1001 llegaron dañados",
        "success_criteria": [
            "El agente informa que el reembolso procede",
            "El agente se refiere al pedido AT-1001",
        ],
        "induced_by": "claude-opus-5",
        "created_at": T0,
    }
    fields.update(overrides)
    return Scenario(**fields)


def verdict(results: list[bool], **overrides) -> Verdict:
    fields = {
        "trace_id": "tr-000000000002",
        "scenario_id": "sc-tr-000000000001",
        "run_id": RUN_FIELDS["run_id"],
        "criteria": [
            CriterionResult(
                criterion=f"criterio {i}", met=met, justification="según la transcripción"
            )
            for i, met in enumerate(results, start=1)
        ],
        "judged_by": "claude-opus-5",
        "created_at": T0,
    }
    fields.update(overrides)
    return Verdict(**fields)


def manifest(**overrides) -> RunManifest:
    fields = {
        "run_id": RUN_FIELDS["run_id"],
        "condition": "baseline-a",
        "variant": "baseline",
        "adapter": "fake",
        "agent": "tests:fake",
        "repetitions": 2,
        "turn_budget": 10,
        "models": {"judge": "claude-opus-5"},
        "created_at": T0,
    }
    fields.update(overrides)
    return RunManifest(**fields)
