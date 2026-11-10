import asyncio
from typing import Any

import pytest
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from agentproof.models import TARGET_BASELINE_MODEL, TARGET_DOWNGRADED_MODEL
from tests.fakes_langchain import ScriptedChatModel, ask_tools, say


class _Recorder(BaseCallbackHandler):
    def __init__(self) -> None:
        self.models: list[str] = []

    def on_chat_model_start(self, serialized: Any, messages: Any, **kwargs: Any) -> None:
        self.models.append(kwargs["invocation_params"]["model"])


@tool
def lookup_order(order_id: str) -> str:
    """Looks up an order."""
    return order_id


def test_invocation_params_carry_the_configured_model():
    recorder = _Recorder()
    for model in (
        ScriptedChatModel(responses=[say("a")]),
        ScriptedChatModel(model=TARGET_DOWNGRADED_MODEL, responses=[say("b")]),
    ):
        model.invoke("hola", config={"callbacks": [recorder]})
    assert recorder.models == [TARGET_BASELINE_MODEL, TARGET_DOWNGRADED_MODEL]


def test_responds_in_order_and_records_what_it_received():
    model = ScriptedChatModel(
        responses=[say("uno"), ask_tools(("lookup_order", {"order_id": "AT-1"}))]
    )
    first = model.invoke([SystemMessage("sys"), HumanMessage("hola")])
    second = asyncio.run(model.ainvoke([HumanMessage("otra")]))
    assert first.content == "uno"
    assert second.tool_calls[0]["name"] == "lookup_order"
    assert second.tool_calls[0]["args"] == {"order_id": "AT-1"}
    assert [[m.content for m in call] for call in model.calls] == [["sys", "hola"], ["otra"]]


def test_responses_carry_usage_and_a_dated_model_name():
    reply = ScriptedChatModel(responses=[say("x")]).invoke("hola")
    assert reply.usage_metadata == {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}
    assert reply.response_metadata["model_name"] == TARGET_BASELINE_MODEL + "-20261001"


def test_bind_tools_records_names_and_returns_the_model():
    model = ScriptedChatModel(responses=[say("x")])
    assert model.bind_tools([lookup_order]) is model
    assert model.bound_tools == ["lookup_order"]


def test_repeat_last_repeats_with_fresh_ids():
    model = ScriptedChatModel(responses=[ask_tools(("get_refund_policy", {}))], repeat_last=True)
    replies = [model.invoke("hola") for _ in range(3)]
    assert [r.tool_calls[0]["name"] for r in replies] == ["get_refund_policy"] * 3
    assert len({r.tool_calls[0]["id"] for r in replies}) == 3
    assert len({r.id for r in replies}) == 3


def test_running_out_of_responses_fails():
    model = ScriptedChatModel(responses=[say("x")])
    model.invoke("hola")
    with pytest.raises(AssertionError):
        model.invoke("otra")


def test_an_exception_response_is_raised():
    model = ScriptedChatModel(responses=[RuntimeError("overloaded")])
    with pytest.raises(RuntimeError, match="overloaded"):
        model.invoke("hola")
