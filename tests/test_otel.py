"""OpenTelemetry GenAI mapping of AgentProof traces (spec F4, §9; D-015)."""

import json
import re
from datetime import timedelta
from pathlib import Path

import pytest

from agentproof import otel
from agentproof.schema import Trace, Usage
from tests.factories import T0, event, trace

# Pinned source of the GenAI semantic conventions: every standard attribute the
# mapping emits, with its stability at that commit. Kept apart from the module
# on purpose, so renaming an attribute in the code fails here.
SEMCONV_COMMIT = "e6658f14c9d9ea0760825f029cb82e7673f48fab"
STANDARD_ATTRIBUTES = {
    "gen_ai.operation.name": "development",
    "gen_ai.conversation.id": "development",
    "gen_ai.agent.name": "development",
    "gen_ai.agent.version": "development",
    "gen_ai.input.messages": "development",
    "gen_ai.output.messages": "development",
    "gen_ai.tool.name": "development",
    "gen_ai.tool.type": "development",
    "gen_ai.tool.call.arguments": "development",
    "gen_ai.tool.call.result": "development",
    "gen_ai.usage.input_tokens": "development",
    "gen_ai.usage.output_tokens": "development",
    "error.type": "stable",
}
INTERNAL = 1
STATUS_UNSET, STATUS_ERROR = 0, 2


def spans(document: dict) -> list[dict]:
    return document["resourceSpans"][0]["scopeSpans"][0]["spans"]


def value(any_value: dict):
    """Plain Python value of an OTLP/JSON AnyValue."""
    if not any_value:
        return None
    (kind, raw), *_ = any_value.items()
    if kind == "intValue":
        return int(raw)
    if kind == "arrayValue":
        return [value(v) for v in raw.get("values", [])]
    if kind == "kvlistValue":
        return attributes({"attributes": raw.get("values", [])})
    return raw


def attributes(span: dict) -> dict:
    return {kv["key"]: value(kv["value"]) for kv in span["attributes"]}


def root(document: dict) -> dict:
    (found,) = [s for s in spans(document) if not s.get("parentSpanId")]
    return found


def run_trace(**overrides):
    return trace(
        kind="run",
        usage=Usage(input_tokens=120, output_tokens=30, cost_usd=0.01),
        simulator_usage=Usage(input_tokens=50, output_tokens=5),
        ended_at=T0 + timedelta(seconds=9),
        **overrides,
    )


def test_pins_the_convention_commit():
    assert otel.SEMCONV_REPOSITORY == "open-telemetry/semantic-conventions-genai"
    assert otel.SEMCONV_COMMIT == SEMCONV_COMMIT
    assert otel.SEMCONV_DATE == "2026-11-06"


def test_document_has_one_resource_and_one_scope_naming_the_commit():
    document = otel.trace_to_otlp(run_trace())
    (resource_spans,) = document["resourceSpans"]
    assert attributes(resource_spans["resource"]) == {"service.name": "agentproof"}
    (scope_spans,) = resource_spans["scopeSpans"]
    scope = scope_spans["scope"]
    assert scope["name"] == "agentproof.otel"
    assert attributes(scope)["agentproof.semconv.commit"] == SEMCONV_COMMIT


def test_conversation_is_one_root_span_with_the_trace_times():
    conversation = root(otel.trace_to_otlp(run_trace()))
    assert conversation["name"] == "agentproof.conversation"
    assert conversation["kind"] == INTERNAL
    assert conversation["startTimeUnixNano"] == str(int(T0.timestamp()) * 10**9)
    assert conversation["endTimeUnixNano"] == str((int(T0.timestamp()) + 9) * 10**9)


def test_root_span_carries_the_conversation_id_and_the_agent_usage():
    found = attributes(root(otel.trace_to_otlp(run_trace())))
    assert found["gen_ai.conversation.id"] == "tr-000000000001"
    assert found["gen_ai.usage.input_tokens"] == 120
    assert found["gen_ai.usage.output_tokens"] == 30
    assert found["agentproof.usage.cost_usd"] == 0.01
    assert found["agentproof.simulator.usage.input_tokens"] == 50
    assert found["agentproof.simulator.usage.output_tokens"] == 5
    assert "agentproof.simulator.usage.cost_usd" not in found


def test_fields_without_a_standard_attribute_go_under_the_agentproof_prefix():
    found = attributes(root(otel.trace_to_otlp(run_trace(attempt=2, agent_seconds=1.5))))
    assert found["agentproof.trace.kind"] == "run"
    assert found["agentproof.adapter"] == "fake"
    assert found["agentproof.agent"] == "tests:fake"
    assert found["agentproof.variant"] == "baseline"
    assert found["agentproof.condition"] == "baseline-a"
    assert found["agentproof.run_id"] == "baseline-a-20261001-120000"
    assert found["agentproof.scenario_id"] == "sc-tr-000000000001"
    assert found["agentproof.repetition"] == 1
    assert found["agentproof.attempt"] == 2
    assert found["agentproof.termination"] == "user_ended"
    assert found["agentproof.agent_seconds"] == 1.5
    assert found["agentproof.models"] == {"judge": "claude-opus-5"}


def test_absent_fields_are_omitted():
    found = attributes(root(otel.trace_to_otlp(trace())))
    for name in ("condition", "run_id", "scenario_id", "repetition", "card_id", "attempt"):
        assert f"agentproof.{name}" not in found


def test_ids_are_hex_of_the_otlp_length_and_shared_by_every_span():
    document = otel.trace_to_otlp(run_trace())
    for span in spans(document):
        assert re.fullmatch(r"[0-9a-f]{32}", span["traceId"])
        assert re.fullmatch(r"[0-9a-f]{16}", span["spanId"])
        assert span["traceId"] == root(document)["traceId"]
    assert len({s["spanId"] for s in spans(document)}) == len(spans(document))


def test_output_is_deterministic_and_depends_on_the_trace_id():
    assert otel.trace_to_otlp(run_trace()) == otel.trace_to_otlp(run_trace())
    other = otel.trace_to_otlp(run_trace(trace_id="tr-000000000002"))
    assert root(other)["traceId"] != root(otel.trace_to_otlp(run_trace()))["traceId"]


def test_every_non_prefixed_attribute_is_in_the_pinned_table():
    document = otel.trace_to_otlp(run_trace())
    for span in spans(document):
        for key in attributes(span):
            assert key.startswith("agentproof.") or key in STANDARD_ATTRIBUTES, key


def test_document_round_trips_through_json():
    document = otel.trace_to_otlp(run_trace())
    assert json.loads(json.dumps(document)) == document


def at(seconds: float):
    return T0 + timedelta(seconds=seconds)


def two_turns(**overrides):
    events = [
        event(1, "user_message", text="Hola, mi pedido AT-1001"),
        event(2, "agent_message", text="Lo reviso."),
        event(3, "agent_message", text="Llegó ayer."),
        event(4, "user_message", text="Gracias"),
        event(5, "agent_message", text="De nada."),
    ]
    events[1].ts = events[2].ts = at(2)
    events[3].ts = at(3)
    events[4].ts = at(5)
    return run_trace(events=events, **overrides)


def turns(document: dict) -> list[dict]:
    return [
        s for s in spans(document) if attributes(s).get("gen_ai.operation.name") == "invoke_agent"
    ]


def test_each_user_message_opens_one_invoke_agent_span_under_the_conversation():
    document = otel.trace_to_otlp(two_turns())
    first, second = turns(document)
    assert first["name"] == second["name"] == "invoke_agent tests:fake"
    assert first["parentSpanId"] == second["parentSpanId"] == root(document)["spanId"]
    assert first["kind"] == INTERNAL
    assert [attributes(t)["agentproof.turn"] for t in (first, second)] == [1, 2]
    assert [attributes(t)["agentproof.step"] for t in (first, second)] == [1, 4]


def test_turn_spans_name_the_agent_its_version_and_the_conversation():
    found = attributes(turns(otel.trace_to_otlp(two_turns()))[0])
    assert found["gen_ai.agent.name"] == "tests:fake"
    assert found["gen_ai.agent.version"] == "baseline"
    assert found["gen_ai.conversation.id"] == "tr-000000000001"
    assert found["agentproof.turn.stop_reason"] == "completed"


def test_turn_span_runs_from_the_user_message_to_the_last_agent_event():
    first, second = turns(otel.trace_to_otlp(two_turns()))
    assert first["startTimeUnixNano"] == otel._nanos(T0)
    assert first["endTimeUnixNano"] == otel._nanos(at(2))
    assert second["startTimeUnixNano"] == otel._nanos(at(3))
    assert second["endTimeUnixNano"] == otel._nanos(at(5))


def test_turn_messages_follow_the_convention_schema():
    found = attributes(turns(otel.trace_to_otlp(two_turns()))[0])
    assert found["gen_ai.input.messages"] == [
        {"role": "user", "parts": [{"type": "text", "content": "Hola, mi pedido AT-1001"}]}
    ]
    assert found["gen_ai.output.messages"] == [
        {
            "role": "assistant",
            "parts": [
                {"type": "text", "content": "Lo reviso."},
                {"type": "text", "content": "Llegó ayer."},
            ],
        }
    ]


def test_usage_stays_on_the_conversation_because_the_trace_has_no_usage_per_turn():
    document = otel.trace_to_otlp(two_turns())
    for turn in turns(document):
        assert "gen_ai.usage.input_tokens" not in attributes(turn)
    total = sum(attributes(s).get("gen_ai.usage.input_tokens", 0) for s in spans(document))
    assert total == 120


def test_step_limit_marks_the_last_turn_without_an_error():
    document = otel.trace_to_otlp(two_turns(termination="step_limit"))
    first, last = turns(document)
    assert attributes(first)["agentproof.turn.stop_reason"] == "completed"
    assert attributes(last)["agentproof.turn.stop_reason"] == "step_limit"
    assert "status" not in last and "error.type" not in attributes(last)


def test_an_agent_error_marks_its_turn_with_the_exception_class():
    events = [
        event(1, "user_message", text="Hola"),
        event(2, "error", text="RuntimeError: se cayó la API"),
    ]
    document = otel.trace_to_otlp(run_trace(events=events, termination="agent_error"))
    (turn,) = turns(document)
    assert turn["status"] == {"code": STATUS_ERROR, "message": "RuntimeError: se cayó la API"}
    assert attributes(turn)["error.type"] == "RuntimeError"
    assert attributes(turn)["agentproof.turn.stop_reason"] == "error"
    assert "gen_ai.output.messages" not in attributes(turn)


def test_an_agent_error_without_an_error_event_falls_back_to_other():
    document = otel.trace_to_otlp(two_turns(termination="agent_error"))
    last = turns(document)[-1]
    assert attributes(last)["error.type"] == "_OTHER"
    assert last["status"]["code"] == STATUS_ERROR


def test_a_simulated_user_error_belongs_to_the_conversation_not_to_the_turn():
    events = [
        event(1, "user_message", text="Hola"),
        event(2, "agent_message", text="¿En qué le ayudo?"),
        event(3, "error", text="TimeoutError: el simulador no respondió"),
    ]
    document = otel.trace_to_otlp(run_trace(events=events, termination="simulator_error"))
    (turn,) = turns(document)
    assert "status" not in turn
    conversation = root(document)
    assert conversation["status"]["code"] == STATUS_ERROR
    assert attributes(conversation)["error.type"] == "TimeoutError"


def test_an_error_before_any_user_message_belongs_to_the_conversation():
    events = [event(1, "error", text="no es un nombre de clase")]
    document = otel.trace_to_otlp(run_trace(events=events, termination="simulator_error"))
    assert turns(document) == []
    assert attributes(root(document))["error.type"] == "_OTHER"


def with_tools(**overrides):
    events = [
        event(1, "user_message", text="Mi pedido es AT-1010"),
        event(2, "tool_call", tool="get_refund_policy", arguments={}, result="Política..."),
        event(
            3,
            "tool_call",
            tool="lookup_order",
            arguments={"order_id": "AT-1010"},
            result={"pedido": "AT-1010", "monto_usd": 39.9, "entregado": True},
        ),
        event(4, "agent_message", text="Procede el reembolso."),
        event(5, "user_message", text="Abra un ticket"),
        event(
            6,
            "tool_call",
            tool="create_ticket",
            arguments={"summary": "x"},
            result="Error: servicio caído",
            is_error=True,
        ),
        event(7, "agent_message", text="No pude crear el ticket."),
    ]
    events[1].ts = at(1)
    return run_trace(events=events, **overrides)


def tools(document: dict) -> list[dict]:
    return [
        s for s in spans(document) if attributes(s).get("gen_ai.operation.name") == "execute_tool"
    ]


def test_every_tool_call_becomes_one_execute_tool_span_under_its_turn():
    document = otel.trace_to_otlp(with_tools())
    first_turn, second_turn = turns(document)
    found = tools(document)
    assert [s["name"] for s in found] == [
        "execute_tool get_refund_policy",
        "execute_tool lookup_order",
        "execute_tool create_ticket",
    ]
    assert [s["parentSpanId"] for s in found] == [
        first_turn["spanId"],
        first_turn["spanId"],
        second_turn["spanId"],
    ]
    assert [attributes(s)["agentproof.step"] for s in found] == [2, 3, 6]
    assert all(s["kind"] == INTERNAL for s in found)


def test_tool_span_records_name_arguments_and_result():
    found = attributes(tools(otel.trace_to_otlp(with_tools()))[1])
    assert found["gen_ai.tool.name"] == "lookup_order"
    assert found["gen_ai.tool.type"] == "function"
    assert found["gen_ai.tool.call.arguments"] == {"order_id": "AT-1010"}
    assert found["gen_ai.tool.call.result"] == {
        "pedido": "AT-1010",
        "monto_usd": 39.9,
        "entregado": True,
    }
    assert found["gen_ai.conversation.id"] == "tr-000000000001"
    assert found["gen_ai.agent.name"] == "tests:fake"


def test_text_results_and_empty_arguments_are_kept_as_they_are():
    found = attributes(tools(otel.trace_to_otlp(with_tools()))[0])
    assert found["gen_ai.tool.call.arguments"] == {}
    assert found["gen_ai.tool.call.result"] == "Política..."


def test_tool_span_has_the_instant_the_trace_recorded():
    span = tools(otel.trace_to_otlp(with_tools()))[0]
    assert span["startTimeUnixNano"] == span["endTimeUnixNano"] == otel._nanos(at(1))


def test_a_failed_tool_call_is_an_error_span_without_a_result():
    span = tools(otel.trace_to_otlp(with_tools()))[2]
    assert span["status"] == {"code": STATUS_ERROR, "message": "Error: servicio caído"}
    assert attributes(span)["error.type"] == "tool_error"
    assert "gen_ai.tool.call.result" not in attributes(span)


def test_a_tool_error_does_not_mark_its_turn():
    second_turn = turns(otel.trace_to_otlp(with_tools()))[1]
    assert "status" not in second_turn


def test_tool_call_ids_are_not_invented():
    for span in tools(otel.trace_to_otlp(with_tools())):
        assert "gen_ai.tool.call.id" not in attributes(span)


def test_a_tool_call_outside_any_turn_hangs_from_the_conversation():
    events = [event(1, "tool_call", tool="lookup_order", arguments={"order_id": "AT-1"})]
    document = otel.trace_to_otlp(run_trace(events=events, termination="agent_error"))
    (span,) = tools(document)
    assert span["parentSpanId"] == root(document)["spanId"]


def test_a_failed_tool_call_without_a_result_has_an_empty_message():
    events = [
        event(1, "user_message", text="Hola"),
        event(2, "tool_call", tool="create_ticket", arguments={"summary": "x"}, is_error=True),
    ]
    (span,) = tools(otel.trace_to_otlp(run_trace(events=events)))
    assert span["status"] == {"code": STATUS_ERROR, "message": ""}


ROOT = Path(__file__).resolve().parents[1]
STORED = sorted(
    [
        *(ROOT / "results/runs/d6-20261018-044847/traces").glob("*.json"),
        *(ROOT / "evidence/piloto-langgraph/results/runs").glob("*/traces/*.json"),
    ]
)


def test_stored_traces_are_available():
    assert len(STORED) > 100


@pytest.mark.parametrize("path", STORED, ids=lambda p: p.stem)
def test_a_stored_trace_converts_and_round_trips(path):
    stored = Trace.model_validate_json(path.read_text())
    document = otel.trace_to_otlp(stored)
    assert json.loads(json.dumps(document, ensure_ascii=False)) == document
    found = spans(document)
    tool_calls = [e for e in stored.events if e.kind == "tool_call"]
    assert len(tools(document)) == len(tool_calls)
    user_messages = [e for e in stored.events if e.kind == "user_message"]
    assert len(turns(document)) == len(user_messages)
    by_id = {s["spanId"]: s for s in found}
    for span in found:
        assert re.fullmatch(r"[0-9a-f]{32}", span["traceId"])
        assert re.fullmatch(r"[0-9a-f]{16}", span["spanId"])
        assert span.get("parentSpanId") is None or span["parentSpanId"] in by_id
        assert int(span["startTimeUnixNano"]) <= int(span["endTimeUnixNano"])
        for key in attributes(span):
            assert key.startswith("agentproof.") or key in STANDARD_ATTRIBUTES, key


def test_module_entry_point_prints_the_document_of_a_trace_file(capsys):
    path = STORED[0]
    assert otel.main([str(path)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == otel.trace_to_otlp(Trace.model_validate_json(path.read_text()))
