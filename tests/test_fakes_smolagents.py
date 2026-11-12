import pytest
from smolagents import Tool
from smolagents.models import ChatMessage, MessageRole

from agentproof.models import TARGET_BASELINE_MODEL, TARGET_DOWNGRADED_MODEL
from tests.fakes_smolagents import ScriptedModel, ask_tools, plain, say, text_of


class LookupOrder(Tool):
    name = "lookup_order"
    description = "Looks up an order."
    inputs = {"order_id": {"type": "string", "description": ""}}
    output_type = "string"

    def forward(self, order_id: str) -> str:
        return order_id


def _user(text):
    return ChatMessage(role=MessageRole.USER, content=[{"type": "text", "text": text}])


def test_reports_the_requested_model():
    assert ScriptedModel(responses=[]).model_id == TARGET_BASELINE_MODEL
    assert ScriptedModel(responses=[], model_id=TARGET_DOWNGRADED_MODEL).model_id == (
        TARGET_DOWNGRADED_MODEL
    )


def test_responds_in_order_and_records_what_it_received():
    model = ScriptedModel(responses=[say("uno"), ask_tools(("lookup_order", {"order_id": "AT-1"}))])
    first = model.generate([_user("hola")], tools_to_call_from=[LookupOrder()])
    second = model.generate([_user("otra")])
    assert first.tool_calls[0].function.name == "final_answer"
    assert first.tool_calls[0].function.arguments == {"answer": "uno"}
    assert second.tool_calls[0].function.arguments == {"order_id": "AT-1"}
    assert [[text_of(m) for m in call] for call in model.calls] == [["hola"], ["otra"]]
    assert model.tools == [["lookup_order"], []]


def test_plain_text_has_no_tool_calls():
    reply = ScriptedModel(responses=[plain("Respuesta")]).generate([_user("hola")])
    assert (reply.content, reply.tool_calls) == ("Respuesta", None)


def test_responses_carry_usage_and_a_dated_model_name():
    reply = ScriptedModel(responses=[say("x")]).generate([_user("hola")])
    assert (reply.token_usage.input_tokens, reply.token_usage.output_tokens) == (100, 20)
    assert reply.raw["model"] == TARGET_BASELINE_MODEL + "-20261001"


def test_repeat_last_repeats_with_fresh_ids():
    model = ScriptedModel(responses=[ask_tools(("get_refund_policy", {}))], repeat_last=True)
    replies = [model.generate([_user("hola")]) for _ in range(3)]
    assert [r.tool_calls[0].function.name for r in replies] == ["get_refund_policy"] * 3
    assert len({r.tool_calls[0].id for r in replies}) == 3


def test_running_out_of_responses_fails():
    model = ScriptedModel(responses=[say("x")])
    model.generate([_user("hola")])
    with pytest.raises(AssertionError):
        model.generate([_user("otra")])


def test_an_exception_response_is_raised():
    model = ScriptedModel(responses=[RuntimeError("overloaded")])
    with pytest.raises(RuntimeError, match="overloaded"):
        model.generate([_user("hola")])
