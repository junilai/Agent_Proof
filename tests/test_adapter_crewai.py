import asyncio
import json

import pytest
from crewai import Agent
from crewai.hooks import get_before_llm_call_hooks
from crewai.tools import tool
from crewai.types.usage_metrics import UsageMetrics

from agentproof.adapters.crewai import (
    TELEMETRY_VARS,
    CrewAISession,
    TelemetryEnabledError,
    ensure_no_telemetry,
    session_factory,
    turn_from_messages,
)
from agentproof.models import TARGET_BASELINE_MODEL, TARGET_DOWNGRADED_MODEL
from tests.fakes_crewai import TELEMETRY_OFF, ScriptedLLM, ask_tools, offline, say

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


def _agent(llm, max_iter=10, tools=()):
    """A bare CrewAI agent: enough to test the session without any edition."""
    return Agent(role="r", goal="g", backstory="b", llm=llm, tools=list(tools), max_iter=max_iter)


@tool("create_ticket")
def create_ticket(summary: str, order_id: str) -> str:
    """Escalates a case."""
    return json.dumps({"ticket": "TCK-1", "pedido": order_id})


def _talk(agent, *messages):
    async def run():
        async with CrewAISession(agent) as session:
            return [await session.send(m) for m in messages]

    return asyncio.run(run())


def _contents(call):
    return [m.get("content") for m in call["messages"]]


def test_refuses_to_open_with_telemetry_on(monkeypatch):
    monkeypatch.delenv("CREWAI_DISABLE_TELEMETRY")
    monkeypatch.delenv("CREWAI_DISABLE_TRACKING")
    monkeypatch.delenv("OTEL_SDK_DISABLED")
    llm = ScriptedLLM(responses=[say("x")])
    with pytest.raises(TelemetryEnabledError, match="CREWAI_DISABLE_TELEMETRY"):
        _talk(_agent(llm), "hola")
    assert llm.calls == []


def test_the_session_keeps_memory_between_turns(network):
    llm = ScriptedLLM(responses=[say("Hola."), say("Sigo aquí.")])
    first, second = _talk(_agent(llm), "hola", "¿sigues?")
    assert (first.reply, second.reply) == ("Hola.", "Sigo aquí.")
    assert [e.kind for e in second.events] == ["agent_message"]
    second_call = _contents(llm.calls[1])
    assert "Hola." in second_call and "¿sigues?" in second_call[-1]
    assert [m["role"] for m in llm.calls[1]["messages"]].count("system") == 1
    assert network == []


def test_the_cut_is_step_limit_and_the_next_turn_sees_the_forced_answer():
    loop = ask_tools(("create_ticket", {"summary": "s", "order_id": "AT-1"}))
    llm = ScriptedLLM(responses=[loop, say("Creé tu ticket."), say("De nada.")])
    cut, after = _talk(_agent(llm, max_iter=1, tools=[create_ticket]), "ticket", "gracias")
    assert cut.stop_reason == "step_limit"
    assert cut.reply == "Creé tu ticket."
    assert [e.kind for e in cut.events] == ["tool_call", "agent_message"]
    assert llm.calls[1]["tools"] == []
    assert "Creé tu ticket." in _contents(llm.calls[2])
    assert (after.stop_reason, after.reply) == ("completed", "De nada.")


def test_a_model_error_ends_the_turn_as_error():
    llm = ScriptedLLM(responses=[RuntimeError("overloaded"), say("De nuevo.")])
    failed, recovered = _talk(_agent(llm), "hola", "otra vez")
    assert failed.stop_reason == "error"
    assert failed.reply == ""
    assert [e.kind for e in failed.events] == ["error"]
    assert "overloaded" in failed.events[0].text
    assert (recovered.stop_reason, recovered.reply) == ("completed", "De nuevo.")


def test_an_empty_final_answer_is_an_error():
    """CrewAI raises on an empty answer, where other frameworks return an empty reply."""
    [turn] = _talk(_agent(ScriptedLLM(responses=[say("")])), "hola")
    assert turn.stop_reason == "error"


def test_an_error_keeps_what_the_agent_already_did_in_the_turn():
    ticket = ask_tools(("create_ticket", {"summary": "s", "order_id": "AT-1"}))
    llm = ScriptedLLM(responses=[ticket, RuntimeError("overloaded"), say("Listo.")])
    failed, after = _talk(_agent(llm, tools=[create_ticket]), "crea un ticket", "¿y?")
    assert failed.stop_reason == "error"
    assert [(e.kind, e.tool) for e in failed.events] == [
        ("tool_call", "create_ticket"),
        ("error", None),
    ]
    assert failed.events[0].result["ticket"] == "TCK-1"
    assert failed.usage.input_tokens == 100
    assert failed.usage.cost_usd == pytest.approx(100 * 2 / 1e6 + 20 * 10 / 1e6)
    roles = [m["role"] for m in llm.calls[2]["messages"]]
    assert roles == ["system", "user", "assistant", "tool", "user"]
    assert after.reply == "Listo."


def test_usage_is_the_turn_s_own():
    lookup = ask_tools(("create_ticket", {"summary": "s", "order_id": "AT-1"}))
    llm = ScriptedLLM(responses=[lookup, say("a"), say("b")])
    first, second = _talk(_agent(llm, tools=[create_ticket]), "uno", "dos")
    assert (first.usage.input_tokens, first.usage.output_tokens) == (200, 40)
    assert (second.usage.input_tokens, second.usage.output_tokens) == (100, 20)


def test_the_session_prices_with_the_model_the_agent_requested():
    llm = ScriptedLLM(model=TARGET_DOWNGRADED_MODEL, responses=[say("x")])
    [turn] = _talk(_agent(llm), "hola")
    assert turn.usage.cost_usd == pytest.approx(100 * 1 / 1e6 + 20 * 5 / 1e6)


def test_the_hook_is_removed_when_the_session_closes():
    before = list(get_before_llm_call_hooks())
    _talk(_agent(ScriptedLLM(responses=[say("x")])), "hola")
    assert get_before_llm_call_hooks() == before


def test_each_conversation_has_its_own_agent_and_history():
    llm = ScriptedLLM(responses=[say("a"), say("b")])
    built = []
    factory = session_factory(lambda variant: built.append(variant) or _agent(llm), "d4")

    async def run():
        for text in ("primera", "segunda"):
            async with factory() as session:
                await session.send(text)

    asyncio.run(run())
    assert built == ["d4", "d4"]
    assert [m["role"] for m in llm.calls[1]["messages"]] == ["system", "user"]
    assert "primera" not in str(llm.calls[1]["messages"])


def test_the_factory_refuses_before_any_conversation(monkeypatch):
    """A batch must fail at once, not leave one error trace per conversation."""
    monkeypatch.setenv("CREWAI_TRACING_ENABLED", "true")
    built = []
    with pytest.raises(TelemetryEnabledError, match="CREWAI_TRACING_ENABLED"):
        session_factory(lambda variant: built.append(variant), "baseline")
    assert built == []
