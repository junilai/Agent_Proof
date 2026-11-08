import asyncio
import json
from typing import Annotated, TypedDict

import pytest
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from agentproof.adapters.langgraph import (
    RECURSION_LIMIT,
    TRACING_VARS,
    LangGraphSession,
    TracingEnabledError,
    ensure_no_tracing,
    session_factory,
    turn_from_messages,
)
from agentproof.models import TARGET_BASELINE_MODEL, TARGET_DOWNGRADED_MODEL
from tests.fakes_langchain import ScriptedChatModel, ask_tools, say

LOOKUP_RESULT = {"pedido": "AT-1001", "estado": "entregado", "dias_desde_entrega": 10}
USAGE = {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}


def _ask(name, args, call_id, text=""):
    content = [{"type": "text", "text": text}] if text else ""
    return AIMessage(
        content=content,
        tool_calls=[{"name": name, "args": args, "id": call_id}],
        usage_metadata=USAGE,
    )


def _turn(*messages, step_limit_reached=False, model=TARGET_BASELINE_MODEL):
    return turn_from_messages(list(messages), step_limit_reached=step_limit_reached, model=model)


def test_a_lookup_reaches_the_trace_with_its_order_id():
    turn = _turn(
        HumanMessage("¿Dónde está mi pedido?"),
        _ask("lookup_order", {"order_id": "AT-1001"}, "c1", text="Lo reviso."),
        ToolMessage(json.dumps(LOOKUP_RESULT), tool_call_id="c1", name="lookup_order"),
        AIMessage("Tu pedido fue entregado.", usage_metadata=USAGE),
    )
    kinds = [e.kind for e in turn.events]
    assert kinds == ["agent_message", "tool_call", "agent_message"]
    call = turn.events[1]
    assert call.tool == "lookup_order"
    assert call.arguments == {"order_id": "AT-1001"}
    assert call.result["estado"] == "entregado"
    assert call.is_error is False
    assert turn.reply == "Lo reviso.\nTu pedido fue entregado."
    assert turn.stop_reason == "completed"


def test_a_failed_tool_is_recorded_as_error():
    turn = _turn(
        _ask("create_ticket", {"summary": "x", "order_id": "AT-1"}, "c1"),
        ToolMessage("Error: boom", tool_call_id="c1", name="create_ticket", status="error"),
        AIMessage("No pude crear el ticket.", usage_metadata=USAGE),
    )
    assert turn.events[0].is_error is True
    assert turn.events[0].result == "Error: boom"
    assert turn.stop_reason == "completed"


def test_text_blocks_and_plain_text_both_make_the_reply():
    blocks = AIMessage(
        content=[{"type": "text", "text": "Hola."}, {"type": "text", "text": "  "}],
        usage_metadata=USAGE,
    )
    plain = AIMessage("¿En qué te ayudo?", usage_metadata=USAGE)
    turn = _turn(blocks, plain)
    assert turn.reply == "Hola.\n¿En qué te ayudo?"
    assert [e.text for e in turn.events] == ["Hola.", "¿En qué te ayudo?"]


def test_the_cut_is_step_limit_not_error():
    turn = _turn(
        _ask("get_refund_policy", {}, "c1"),
        ToolMessage("Política…", tool_call_id="c1", name="get_refund_policy"),
        step_limit_reached=True,
    )
    assert turn.stop_reason == "step_limit"
    assert all(e.kind != "error" for e in turn.events)
    assert turn.events[0].result == "Política…"


def test_usage_is_priced_with_the_dated_table():
    turn = _turn(AIMessage("a", usage_metadata=USAGE), AIMessage("b", usage_metadata=USAGE))
    assert (turn.usage.input_tokens, turn.usage.output_tokens) == (200, 40)
    assert turn.usage.cost_usd == pytest.approx(2 * (100 * 2 / 1e6 + 20 * 10 / 1e6))


def test_the_price_comes_from_the_requested_model_not_the_response():
    dated = AIMessage(
        "a", usage_metadata=USAGE, response_metadata={"model_name": "claude-sonnet-5-20261001"}
    )
    turn = _turn(dated, model="claude-sonnet-5")
    assert turn.usage.cost_usd == pytest.approx(100 * 2 / 1e6 + 20 * 10 / 1e6)


def test_an_unpriced_model_has_no_cost():
    turn = _turn(AIMessage("a", usage_metadata=USAGE), model="claude-unknown")
    assert turn.usage.input_tokens == 100
    assert turn.usage.cost_usd is None
    assert _turn(AIMessage("a", usage_metadata=USAGE), model=None).usage.cost_usd is None


class _State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    step_limit_reached: bool


def _graph(model, cut=False):
    """A one-node graph: enough to test the session without any edition."""

    def call(state):
        return {"messages": [model.invoke(state["messages"])], "step_limit_reached": cut}

    graph = StateGraph(_State)
    graph.add_node("model", call)
    graph.add_edge(START, "model")
    graph.add_edge("model", END)
    return graph


@pytest.fixture(autouse=True)
def _no_tracing(monkeypatch):
    for var in TRACING_VARS:
        monkeypatch.delenv(var, raising=False)


def _talk(graph, *messages):
    async def run():
        async with LangGraphSession(graph) as session:
            return [await session.send(m) for m in messages]

    return asyncio.run(run())


@pytest.mark.parametrize("var", TRACING_VARS)
@pytest.mark.parametrize("value", ["true", "1", "True"])
def test_refuses_to_open_with_tracing_enabled(monkeypatch, var, value):
    monkeypatch.setenv(var, value)
    with pytest.raises(TracingEnabledError, match=var):
        _talk(_graph(ScriptedChatModel(responses=[say("x")])), "hola")


def test_tracing_explicitly_off_is_fine():
    ensure_no_tracing({var: "false" for var in TRACING_VARS})


def test_every_variable_langsmith_reads_is_guarded():
    names = [
        f"{ns}_{name}" for ns in ("LANGSMITH", "LANGCHAIN") for name in ("TRACING_V2", "TRACING")
    ]
    assert set(names) <= set(TRACING_VARS)


def test_refuses_when_langsmith_itself_would_trace(monkeypatch):
    monkeypatch.setattr("langsmith.utils.tracing_is_enabled", lambda *a, **k: True)
    with pytest.raises(TracingEnabledError, match="LangSmith"):
        ensure_no_tracing({})


def test_the_session_keeps_memory_between_turns():
    model = ScriptedChatModel(responses=[say("Hola."), say("Sigo aquí.")])
    first, second = _talk(_graph(model), "hola", "¿sigues?")
    assert (first.reply, second.reply) == ("Hola.", "Sigo aquí.")
    assert [m.content for m in model.calls[1]] == ["hola", "Hola.", "¿sigues?"]
    assert [e.kind for e in second.events] == ["agent_message"]


def test_the_cut_flag_becomes_step_limit():
    [turn] = _talk(_graph(ScriptedChatModel(responses=[say("x")]), cut=True), "hola")
    assert turn.stop_reason == "step_limit"


def test_a_model_error_ends_the_turn_as_error():
    model = ScriptedChatModel(responses=[RuntimeError("overloaded"), say("De nuevo.")])
    failed, recovered = _talk(_graph(model), "hola", "otra vez")
    assert failed.stop_reason == "error"
    assert failed.reply == ""
    assert [e.kind for e in failed.events] == ["error"]
    assert "overloaded" in failed.events[0].text
    assert recovered.stop_reason == "completed"
    assert recovered.reply == "De nuevo."


def test_each_session_has_its_own_thread():
    model = ScriptedChatModel(responses=[say("a"), say("b")])
    factory = session_factory(lambda variant: _graph(model), "baseline")

    async def run():
        for text in ("primera", "segunda"):
            async with factory() as session:
                await session.send(text)

    asyncio.run(run())
    assert [[m.content for m in call] for call in model.calls] == [["primera"], ["segunda"]]


def test_the_factory_builds_the_graph_of_its_variant():
    asked = []
    session_factory(lambda variant: asked.append(variant) or _graph(None), "d4")()
    assert asked == ["d4"]


def test_the_session_prices_with_the_model_the_graph_requested():
    model = ScriptedChatModel(model=TARGET_DOWNGRADED_MODEL, responses=[say("x")])
    [turn] = _talk(_graph(model), "hola")
    assert turn.usage.cost_usd == pytest.approx(100 * 1 / 1e6 + 20 * 5 / 1e6)


@tool
def create_ticket(summary: str, order_id: str) -> dict:
    """Escalates a case."""
    return {"ticket": "TCK-1", "pedido": order_id}


def test_an_error_keeps_what_the_agent_already_did_in_the_turn():
    ticket = ask_tools(("create_ticket", {"summary": "s", "order_id": "AT-1"}))
    model = ScriptedChatModel(responses=[ticket, RuntimeError("overloaded")])
    bound = model.bind_tools([create_ticket])
    graph = StateGraph(_State)
    graph.add_node("model", lambda state: {"messages": [bound.invoke(state["messages"])]})
    graph.add_node("tools", ToolNode([create_ticket]))
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", tools_condition)
    graph.add_edge("tools", "model")
    [turn] = _talk(graph, "crea un ticket")
    assert turn.stop_reason == "error"
    assert [(e.kind, e.tool) for e in turn.events] == [
        ("tool_call", "create_ticket"),
        ("error", None),
    ]
    assert turn.events[0].result["ticket"] == "TCK-1"
    assert "overloaded" in turn.events[1].text
    assert turn.usage.input_tokens == 100
    assert turn.usage.cost_usd == pytest.approx(100 * 2 / 1e6 + 20 * 10 / 1e6)


def test_a_runaway_loop_is_stopped_as_an_error():
    """A graph whose own counter never cuts still ends, after a bounded number of calls."""
    loop = ask_tools(("create_ticket", {"summary": "s", "order_id": "AT-1"}))
    model = ScriptedChatModel(responses=[loop], repeat_last=True)
    bound = model.bind_tools([create_ticket])
    graph = StateGraph(_State)
    graph.add_node("model", lambda state: {"messages": [bound.invoke(state["messages"])]})
    graph.add_node("tools", ToolNode([create_ticket]))
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", tools_condition)
    graph.add_edge("tools", "model")
    [turn] = _talk(graph, "hola")
    assert turn.stop_reason == "error"
    assert "GraphRecursionError" in turn.events[-1].text
    assert len(model.calls) == RECURSION_LIMIT // 2


def test_the_factory_refuses_before_any_conversation(monkeypatch):
    """A batch must fail at once, not leave one error trace per conversation."""
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    built = []
    with pytest.raises(TracingEnabledError, match="LANGSMITH_TRACING"):
        session_factory(lambda variant: built.append(variant), "baseline")
    assert built == []
