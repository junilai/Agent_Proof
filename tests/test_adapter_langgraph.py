import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agentproof.adapters.langgraph import turn_from_messages
from agentproof.models import TARGET_BASELINE_MODEL

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
