import socket

import pytest
from crewai import Agent
from crewai.tools import tool

from agentproof.models import TARGET_BASELINE_MODEL, TARGET_DOWNGRADED_MODEL
from tests.fakes_crewai import ScriptedLLM, ask_tools, offline, say


@pytest.fixture(autouse=True)
def network(monkeypatch):
    return offline(monkeypatch)


@tool("lookup_order")
def lookup_order(order_id: str) -> str:
    """Looks up an order."""
    return f"pedido {order_id}"


def test_responds_in_order_and_records_what_it_received():
    llm = ScriptedLLM(responses=[say("uno"), ask_tools(("lookup_order", {"order_id": "AT-1"}))])
    first = llm.call([{"role": "system", "content": "sys"}, {"role": "user", "content": "hola"}])
    second = llm.call("otra", tools=[{"function": {"name": "lookup_order"}}])
    assert first == "uno"
    assert [(c["name"], c["input"]) for c in second] == [("lookup_order", {"order_id": "AT-1"})]
    assert [[m["content"] for m in call["messages"]] for call in llm.calls] == [
        ["sys", "hola"],
        ["otra"],
    ]
    assert [call["tools"] for call in llm.calls] == [[], ["lookup_order"]]


def test_every_answer_reports_the_same_usage():
    llm = ScriptedLLM(responses=[say("a"), say("b")])
    llm.call("hola")
    llm.call("otra")
    usage = llm.get_token_usage_summary()
    assert (usage.prompt_tokens, usage.completion_tokens, usage.successful_requests) == (200, 40, 2)


def test_the_model_is_the_requested_one():
    assert ScriptedLLM().model == TARGET_BASELINE_MODEL
    assert ScriptedLLM(model=TARGET_DOWNGRADED_MODEL).model == TARGET_DOWNGRADED_MODEL
    assert ScriptedLLM().supports_function_calling() is True


def test_repeat_last_repeats_with_fresh_ids():
    llm = ScriptedLLM(responses=[ask_tools(("get_refund_policy", {}))], repeat_last=True)
    replies = [llm.call("hola") for _ in range(3)]
    assert [r[0]["name"] for r in replies] == ["get_refund_policy"] * 3
    assert len({r[0]["id"] for r in replies}) == 3


def test_running_out_of_responses_fails():
    llm = ScriptedLLM(responses=[say("x")])
    llm.call("hola")
    with pytest.raises(AssertionError):
        llm.call("otra")


def test_an_exception_response_is_raised():
    llm = ScriptedLLM(responses=[RuntimeError("overloaded")])
    with pytest.raises(RuntimeError, match="overloaded"):
        llm.call("hola")


def test_a_crewai_agent_calls_tools_natively_through_it(network):
    lookup = ask_tools(("lookup_order", {"order_id": "AT-1"}))
    llm = ScriptedLLM(responses=[lookup, say("Entregado.")])
    agent = Agent(role="r", goal="g", backstory="b", llm=llm, tools=[lookup_order])
    output = agent.kickoff("¿Y mi pedido?")
    assert output.raw == "Entregado."
    assert [m["content"] for m in output.messages if m["role"] == "tool"] == ["pedido AT-1"]
    assert network == []


def test_the_network_is_blocked():
    with pytest.raises(OSError, match="blocked"):
        socket.create_connection(("127.0.0.1", 9))
