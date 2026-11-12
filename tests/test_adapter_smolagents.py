import asyncio
import sys
import types

import pytest
from smolagents import Tool, ToolCallingAgent
from smolagents.agents import ActionOutput, ToolOutput
from smolagents.memory import ActionStep, FinalAnswerStep, TaskStep, ToolCall
from smolagents.monitoring import AgentLogger, LogLevel, Timing, TokenUsage
from smolagents.utils import AgentExecutionError, AgentMaxStepsError

from agentproof.adapters.smolagents import (
    COST_MAP_VAR,
    SmolagentsSession,
    TelemetryEnabledError,
    ensure_no_telemetry,
    session_factory,
    turn_from_run,
)
from agentproof.models import TARGET_BASELINE_MODEL, TARGET_DOWNGRADED_MODEL
from tests.fakes_smolagents import ScriptedModel, ask_tools, say, text_of

LOOKUP_RESULT = {"pedido": "AT-1001", "estado": "entregado", "dias_desde_entrega": 10}
QUIET = AgentLogger(LogLevel.OFF)


def _call(name, args, call_id):
    return ToolCall(name=name, arguments=args, id=call_id)


def _output(call, value):
    return ToolOutput(
        id=call.id,
        output=value,
        is_final_answer=call.name == "final_answer",
        observation=str(value),
        tool_call=call,
    )


def _step(number, error=None, usage=True):
    return ActionStep(
        step_number=number,
        timing=Timing(start_time=0.0),
        error=error,
        token_usage=TokenUsage(input_tokens=100, output_tokens=20) if usage else None,
    )


def _answer(call_id, text):
    call = _call("final_answer", {"answer": text}, call_id)
    return [call, _output(call, text), ActionOutput(output=text, is_final_answer=True)]


def _turn(events, steps=None, model=TARGET_BASELINE_MODEL):
    if steps is None:
        steps = [e for e in events if isinstance(e, ActionStep)]
    return turn_from_run(events, [TaskStep(task="hola"), *steps], model=model)


def test_a_lookup_reaches_the_trace_with_its_order_id():
    lookup = _call("lookup_order", {"order_id": "AT-1001"}, "c1")
    events = [lookup, _output(lookup, LOOKUP_RESULT), _step(1)]
    events += [*_answer("c2", "Tu pedido fue entregado."), _step(2)]
    events.append(FinalAnswerStep(output="Tu pedido fue entregado."))
    turn = _turn(events)
    assert [e.kind for e in turn.events] == ["tool_call", "agent_message"]
    call = turn.events[0]
    assert (call.tool, call.arguments, call.result) == (
        "lookup_order",
        {"order_id": "AT-1001"},
        LOOKUP_RESULT,
    )
    assert call.is_error is False
    assert turn.reply == "Tu pedido fue entregado."
    assert turn.events[1].text == turn.reply
    assert turn.stop_reason == "completed"


def test_final_answer_is_the_reply_never_a_tool_call():
    events = [*_answer("c1", "Hola."), _step(1), FinalAnswerStep(output="Hola.")]
    turn = _turn(events)
    assert [(e.kind, e.tool) for e in turn.events] == [("agent_message", None)]
    assert turn.reply == "Hola."


def test_a_text_subclass_result_is_kept_as_plain_text():
    class AgentText(str):
        pass

    policy = _call("get_refund_policy", {}, "c1")
    turn = _turn([policy, _output(policy, AgentText("Política…")), _step(1)])
    assert type(turn.events[0].result) is str
    assert turn.events[0].result == "Política…"


def test_arguments_that_are_not_an_object_are_kept():
    call = _call("lookup_order", "AT-1001", "c1")
    turn = _turn([call, _output(call, LOOKUP_RESULT), _step(1)])
    assert turn.events[0].arguments == {"input": "AT-1001"}


def test_calls_of_a_failed_step_are_errors_in_the_order_they_were_made():
    """The model is told the whole step failed, even when some of its tools ran."""
    ticket = _call("create_ticket", {"summary": "s", "order_id": "AT-1"}, "c1")
    policy = _call("get_refund_policy", {}, "c2")
    answer = _call("final_answer", {"answer": "Listo."}, "c3")
    error = AgentExecutionError("please do not perform any other tool calls", QUIET)
    events = [ticket, policy, answer, _output(policy, "Política…"), _step(1, error=error)]
    turn = _turn(events)
    assert [(e.tool, e.is_error) for e in turn.events] == [
        ("create_ticket", True),
        ("get_refund_policy", True),
    ]
    assert "other tool calls" in turn.events[0].result
    assert turn.events[1].result == "Política…"
    assert turn.stop_reason == "completed"


def test_the_forced_answer_is_step_limit_and_is_the_reply():
    policy = _call("get_refund_policy", {}, "c1")
    forced = _step(2, error=AgentMaxStepsError("Reached max steps.", QUIET))
    events = [policy, _output(policy, "Política…"), _step(1), FinalAnswerStep(output="Forzada")]
    turn = _turn(events, steps=[_step(1), forced])
    assert turn.stop_reason == "step_limit"
    assert all(e.kind != "error" for e in turn.events)
    assert turn.reply == "Forzada"
    assert turn.events[0].result == "Política…"


def test_a_failed_forced_answer_is_an_error():
    forced = _step(2, error=AgentMaxStepsError("Reached max steps.", QUIET), usage=False)
    output = [{"type": "text", "text": "Error in generating final LLM output: overloaded"}]
    turn = _turn([FinalAnswerStep(output=output)], steps=[_step(1), forced])
    assert turn.stop_reason == "error"
    assert turn.reply == ""
    assert [e.kind for e in turn.events] == ["error"]
    assert "overloaded" in turn.events[0].text


def test_usage_is_the_turn_s_own_priced_with_the_dated_table():
    turn = _turn([], steps=[_step(1), _step(2), _step(3, usage=False)])
    assert (turn.usage.input_tokens, turn.usage.output_tokens) == (200, 40)
    assert turn.usage.cost_usd == pytest.approx(2 * (100 * 2 / 1e6 + 20 * 10 / 1e6))


def test_an_unpriced_model_has_no_cost():
    turn = _turn([], steps=[_step(1)], model="claude-unknown")
    assert turn.usage.input_tokens == 100
    assert turn.usage.cost_usd is None
    assert _turn([], steps=[_step(1)], model=None).usage.cost_usd is None


class CreateTicket(Tool):
    name = "create_ticket"
    description = "Escalates a case."
    inputs = {
        "summary": {"type": "string", "description": ""},
        "order_id": {"type": "string", "description": ""},
    }
    output_type = "object"

    def forward(self, summary: str, order_id: str) -> dict:
        return {"ticket": "TCK-1", "pedido": order_id}


def _agent(model, max_steps=5):
    """A bare agent: enough to test the session without any edition."""
    return ToolCallingAgent(tools=[CreateTicket()], model=model, max_steps=max_steps)


def _talk(agent, *messages):
    async def run():
        async with SmolagentsSession(agent) as session:
            return [await session.send(m) for m in messages]

    return asyncio.run(run())


def _history(call):
    """Everything the model was sent but the system prompt."""
    return "\n".join(text_of(m) for m in call if m.role != "system")


def test_the_session_keeps_memory_between_turns():
    model = ScriptedModel(responses=[say("Hola."), say("Sigo aquí.")])
    first, second = _talk(_agent(model), "hola", "¿sigues?")
    assert (first.reply, second.reply) == ("Hola.", "Sigo aquí.")
    seen = _history(model.calls[1])
    assert "hola" in seen and "¿sigues?" in seen and "Hola." in seen
    assert [e.kind for e in second.events] == ["agent_message"]


def test_usage_is_per_turn_not_cumulative():
    model = ScriptedModel(responses=[say("a"), say("b")])
    first, second = _talk(_agent(model), "hola", "otra")
    assert (first.usage.input_tokens, second.usage.input_tokens) == (100, 100)


def test_the_session_prices_with_the_model_the_agent_requested():
    model = ScriptedModel(model_id=f"anthropic/{TARGET_DOWNGRADED_MODEL}", responses=[say("x")])
    [turn] = _talk(_agent(model), "hola")
    assert turn.usage.cost_usd == pytest.approx(100 * 1 / 1e6 + 20 * 5 / 1e6)


def test_a_model_error_ends_the_turn_as_error():
    model = ScriptedModel(responses=[RuntimeError("overloaded"), say("De nuevo.")])
    failed, recovered = _talk(_agent(model), "hola", "otra vez")
    assert failed.stop_reason == "error"
    assert failed.reply == ""
    assert [e.kind for e in failed.events] == ["error"]
    assert "overloaded" in failed.events[0].text
    assert (recovered.stop_reason, recovered.reply) == ("completed", "De nuevo.")


def test_an_error_keeps_what_the_agent_already_did_in_the_turn():
    ticket = ask_tools(("create_ticket", {"summary": "s", "order_id": "AT-1"}))
    model = ScriptedModel(responses=[ticket, RuntimeError("overloaded")])
    [turn] = _talk(_agent(model), "crea un ticket")
    assert turn.stop_reason == "error"
    assert [(e.kind, e.tool) for e in turn.events] == [
        ("tool_call", "create_ticket"),
        ("error", None),
    ]
    assert turn.events[0].result["ticket"] == "TCK-1"
    assert "overloaded" in turn.events[1].text
    assert turn.usage.input_tokens == 100
    assert turn.usage.cost_usd == pytest.approx(100 * 2 / 1e6 + 20 * 10 / 1e6)


def test_the_session_silences_the_framework_console():
    agent = _agent(ScriptedModel(responses=[say("x")]))
    _talk(agent, "hola")
    assert agent.logger.level == LogLevel.OFF


def test_each_session_has_its_own_memory():
    model = ScriptedModel(responses=[say("a"), say("b")])
    factory = session_factory(lambda variant: _agent(model), "baseline")

    async def run():
        for text in ("primera", "segunda"):
            async with factory() as session:
                await session.send(text)

    asyncio.run(run())
    assert "primera" in _history(model.calls[0])
    assert "primera" not in _history(model.calls[1])


def test_the_factory_builds_the_agent_of_its_variant():
    asked = []
    session_factory(lambda variant: asked.append(variant) or _agent(ScriptedModel([])), "d4")()
    assert asked == ["d4"]


@pytest.mark.parametrize("value", [None, "", "false", "1"])
def test_refuses_to_open_unless_litellm_uses_its_local_cost_map(monkeypatch, value):
    if value is None:
        monkeypatch.delenv(COST_MAP_VAR, raising=False)
    else:
        monkeypatch.setenv(COST_MAP_VAR, value)
    with pytest.raises(TelemetryEnabledError, match=COST_MAP_VAR):
        _talk(_agent(ScriptedModel(responses=[say("x")])), "hola")


@pytest.mark.parametrize("value", ["True", "true", " TRUE "])
def test_the_local_cost_map_is_fine(value):
    ensure_no_telemetry({COST_MAP_VAR: value})


def test_refuses_when_litellm_would_send_data_to_a_callback(monkeypatch):
    import litellm

    monkeypatch.setattr(litellm, "success_callback", ["langfuse"])
    with pytest.raises(TelemetryEnabledError, match="success_callback"):
        ensure_no_telemetry({COST_MAP_VAR: "True"})


def test_refuses_when_litellm_already_fetched_its_cost_map(monkeypatch):
    import litellm.litellm_core_utils.get_model_cost_map as cost_map

    monkeypatch.setattr(
        cost_map, "get_model_cost_map_source_info", lambda: {"is_env_forced": False}
    )
    with pytest.raises(TelemetryEnabledError, match=COST_MAP_VAR):
        ensure_no_telemetry({COST_MAP_VAR: "True"})


def test_refuses_when_the_opentelemetry_instrumentation_is_loaded(monkeypatch):
    name = "openinference.instrumentation.smolagents"
    monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    with pytest.raises(TelemetryEnabledError, match="OpenTelemetry"):
        ensure_no_telemetry({COST_MAP_VAR: "True"})


def test_the_factory_refuses_before_any_conversation(monkeypatch):
    """A batch must fail at once, not leave one error trace per conversation."""
    monkeypatch.delenv(COST_MAP_VAR, raising=False)
    built = []
    with pytest.raises(TelemetryEnabledError, match=COST_MAP_VAR):
        session_factory(lambda variant: built.append(variant), "baseline")
    assert built == []
