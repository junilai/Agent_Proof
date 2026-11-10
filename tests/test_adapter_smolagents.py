import pytest
from smolagents.agents import ActionOutput, ToolOutput
from smolagents.memory import ActionStep, FinalAnswerStep, TaskStep, ToolCall
from smolagents.monitoring import AgentLogger, LogLevel, Timing, TokenUsage
from smolagents.utils import AgentExecutionError, AgentMaxStepsError

from agentproof.adapters.smolagents import turn_from_run
from agentproof.models import TARGET_BASELINE_MODEL

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
