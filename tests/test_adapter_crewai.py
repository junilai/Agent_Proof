import json

import pytest
from crewai.types.usage_metrics import UsageMetrics

from agentproof.adapters.crewai import (
    TELEMETRY_VARS,
    TelemetryEnabledError,
    ensure_no_telemetry,
    turn_from_messages,
)
from agentproof.models import TARGET_BASELINE_MODEL
from tests.fakes_crewai import TELEMETRY_OFF, offline

LOOKUP_RESULT = {"pedido": "AT-1001", "estado": "entregado", "dias_desde_entrega": 10}
ONE_CALL = UsageMetrics(prompt_tokens=100, completion_tokens=20, successful_requests=1)


@pytest.fixture(autouse=True)
def network(monkeypatch):
    return offline(monkeypatch)


def _ask(*calls):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
            for name, args, call_id in calls
        ],
    }


def _result(call_id, name, content):
    return {"role": "tool", "tool_call_id": call_id, "name": name, "content": content}


def _say(text):
    return {"role": "assistant", "content": text}


def _turn(*messages, reply="", step_limit_reached=False, metrics=ONE_CALL, model=None):
    return turn_from_messages(
        list(messages),
        reply=reply,
        step_limit_reached=step_limit_reached,
        metrics=metrics,
        model=model or TARGET_BASELINE_MODEL,
    )


def test_a_lookup_reaches_the_trace_with_its_order_id():
    turn = _turn(
        _ask(("lookup_order", {"order_id": "AT-1001"}, "c1")),
        _result("c1", "lookup_order", json.dumps(LOOKUP_RESULT)),
        _say("Tu pedido fue entregado."),
        reply="Tu pedido fue entregado.",
    )
    assert [e.kind for e in turn.events] == ["tool_call", "agent_message"]
    call = turn.events[0]
    assert (call.tool, call.arguments, call.result) == (
        "lookup_order",
        {"order_id": "AT-1001"},
        LOOKUP_RESULT,
    )
    assert call.is_error is False
    assert turn.reply == "Tu pedido fue entregado."
    assert turn.stop_reason == "completed"


def test_parallel_calls_keep_the_order_the_model_asked_for():
    turn = _turn(
        _ask(("lookup_order", {"order_id": "AT-1"}, "c1"), ("get_refund_policy", {}, "c2")),
        _result("c2", "get_refund_policy", "Política…"),
        _result("c1", "lookup_order", json.dumps(LOOKUP_RESULT)),
    )
    assert [(e.tool, e.result) for e in turn.events] == [
        ("lookup_order", LOOKUP_RESULT),
        ("get_refund_policy", "Política…"),
    ]


def test_a_tool_that_raised_is_recorded_as_error():
    turn = _turn(
        _ask(("create_ticket", {"summary": "x", "order_id": "AT-1"}, "c1")),
        _result("c1", "create_ticket", "Error executing tool: boom"),
        _say("No pude crear el ticket."),
        reply="No pude crear el ticket.",
    )
    assert turn.events[0].is_error is True
    assert turn.events[0].result == "Error executing tool: boom"
    assert turn.stop_reason == "completed"


def test_the_cut_is_step_limit_and_the_forced_answer_is_the_reply():
    """CrewAI never stores the forced answer among the messages."""
    turn = _turn(
        _ask(("get_refund_policy", {}, "c1")),
        _result("c1", "get_refund_policy", "Política…"),
        reply="Te escribo la política.",
        step_limit_reached=True,
    )
    assert turn.stop_reason == "step_limit"
    assert [e.kind for e in turn.events] == ["tool_call", "agent_message"]
    assert turn.events[1].text == turn.reply == "Te escribo la política."


def test_usage_is_priced_with_the_dated_table():
    metrics = UsageMetrics(prompt_tokens=200, completion_tokens=40, successful_requests=2)
    turn = _turn(_say("a"), reply="a", metrics=metrics)
    assert (turn.usage.input_tokens, turn.usage.output_tokens) == (200, 40)
    assert turn.usage.cost_usd == pytest.approx(200 * 2 / 1e6 + 40 * 10 / 1e6)


def test_an_unpriced_model_has_no_cost():
    turn = _turn(_say("a"), reply="a", model="claude-unknown")
    assert turn.usage.input_tokens == 100
    assert turn.usage.cost_usd is None


@pytest.mark.parametrize("var", TELEMETRY_VARS)
@pytest.mark.parametrize("value", ["true", "1", "yes", "on", "True"])
def test_any_crewai_switch_turns_telemetry_off(var, value):
    ensure_no_telemetry({var: value, "CREWAI_TRACING_ENABLED": "false"})


def test_refuses_with_telemetry_on():
    with pytest.raises(TelemetryEnabledError, match="CREWAI_DISABLE_TELEMETRY=true"):
        ensure_no_telemetry({"CREWAI_TRACING_ENABLED": "false"})
    with pytest.raises(TelemetryEnabledError, match="CREWAI_DISABLE_TELEMETRY"):
        ensure_no_telemetry({"CREWAI_DISABLE_TELEMETRY": "false"})


@pytest.mark.parametrize("value", ["true", "1"])
def test_refuses_with_tracing_on(value):
    env = {**TELEMETRY_OFF, "CREWAI_TRACING_ENABLED": value}
    with pytest.raises(TelemetryEnabledError, match="CREWAI_TRACING_ENABLED=false"):
        ensure_no_telemetry(env)


def test_refuses_when_crewai_itself_would_send_traces(monkeypatch):
    """A consent stored by ``crewai traces enable`` turns tracing on without any variable."""
    monkeypatch.setattr("agentproof.adapters.crewai.should_enable_tracing", lambda *a, **k: True)
    with pytest.raises(TelemetryEnabledError, match="CREWAI_TRACING_ENABLED=false"):
        ensure_no_telemetry(TELEMETRY_OFF)


def test_refuses_when_crewai_itself_reads_telemetry_on(monkeypatch):
    monkeypatch.delenv("CREWAI_DISABLE_TELEMETRY")
    monkeypatch.delenv("CREWAI_DISABLE_TRACKING")
    monkeypatch.delenv("OTEL_SDK_DISABLED")
    with pytest.raises(TelemetryEnabledError, match="CREWAI_DISABLE_TELEMETRY"):
        ensure_no_telemetry(TELEMETRY_OFF)


def test_telemetry_and_tracing_off_is_fine():
    ensure_no_telemetry(TELEMETRY_OFF)
