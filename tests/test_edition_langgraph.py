"""The LangGraph edition: the contract of spec §4, without the API.

Each test names the rule it checks. Those that converse drive the edition through
``LangGraphSession`` with a scripted model, the way AgentProof runs it.
"""

import asyncio
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agentproof.adapters.langgraph import LangGraphSession, session_factory
from agentproof.conversation import converse
from agentproof.models import TARGET_DOWNGRADED_MODEL
from casestudy.domain.mutations import BASELINE, CORRUPT_POLICY, MUTATIONS
from casestudy.domain.policy import Decision
from casestudy.domain.policy_text import policy_text
from casestudy.domain.prompt import system_prompt
from casestudy.domain.tools import TOOL_DESCRIPTIONS, get_refund_policy, lookup_order
from casestudy.editions.langgraph import (
    D6_STEP_LIMIT,
    MAX_TOKENS,
    REQUEST_TIMEOUT,
    STEP_LIMIT,
    VARIANTS,
    builder,
    default_model,
    step_limit,
    tools_for,
)
from experiments.oracle.outcome import communicated_decision
from tests.fakes import SEED, ScriptedUser
from tests.fakes_langchain import ScriptedChatModel, ask_tools, say

POLICY_FOREVER = ask_tools(("get_refund_policy", {}))


def _model(variant="baseline", *responses, repeat_last=False):
    return ScriptedChatModel(
        model=MUTATIONS[variant].model, responses=list(responses), repeat_last=repeat_last
    )


def _talk(variant, model, *messages):
    async def run():
        async with LangGraphSession(builder(variant, model=model)) as session:
            return [await session.send(m) for m in messages]

    return asyncio.run(run())


def _value(result):
    if isinstance(result, str):
        try:
            return json.loads(result)
        except ValueError:
            return result
    return result


def _tools(variant="baseline"):
    return {t.name: t for t in tools_for(MUTATIONS[variant])}


def _unanswered(messages):
    """Tool calls without a result by the time the customer speaks again or the model is called."""
    pending = set()
    for message in messages:
        if isinstance(message, HumanMessage) and pending:
            return pending
        if isinstance(message, AIMessage):
            pending |= {call["id"] for call in message.tool_calls}
        elif isinstance(message, ToolMessage):
            pending.discard(message.tool_call_id)
    return pending


# Rule 1: the tools are the domain ones.


def test_baseline_tools_are_the_domain_ones():
    tools = _tools()
    assert list(tools) == list(TOOL_DESCRIPTIONS)
    assert {name: t.description for name, t in tools.items()} == TOOL_DESCRIPTIONS
    assert set(tools["lookup_order"].args) == {"order_id"}
    assert set(tools["get_refund_policy"].args) == set()
    assert set(tools["create_ticket"].args) == {"summary", "order_id"}


def test_the_graph_binds_the_variant_tools():
    model = _model("baseline", say("Hola."))
    _talk("baseline", model, "hola")
    assert model.bound_tools == list(TOOL_DESCRIPTIONS)


def test_tools_wrap_the_domain():
    tools = _tools()
    assert _value(tools["lookup_order"].invoke({"order_id": "at-1001"})) == lookup_order("AT-1001")
    assert _value(tools["get_refund_policy"].invoke({})) == get_refund_policy()
    ticket = _value(tools["create_ticket"].invoke({"summary": "Laptop", "order_id": "AT-1002"}))
    assert ticket["estado"] == "escalado" and ticket["pedido"] == "AT-1002"


def test_a_lookup_reaches_the_trace():
    lookup = ask_tools(("lookup_order", {"order_id": "AT-1001"}))
    [turn] = _talk("baseline", _model("baseline", lookup, say("Fue entregado.")), "¿Y mi pedido?")
    call = turn.events[0]
    assert (call.kind, call.tool, call.arguments) == (
        "tool_call",
        "lookup_order",
        {"order_id": "AT-1001"},
    )
    assert call.result == lookup_order("AT-1001")
    assert turn.reply == "Fue entregado."


# Rule 2: the six mutations, with the same definition.


def test_every_mutation_is_a_variant():
    assert VARIANTS == tuple(MUTATIONS)


def test_unknown_variants_are_rejected():
    with pytest.raises(ValueError):
        builder("d9")


def test_d1_has_no_lookup_order():
    assert list(_tools("d1")) == ["get_refund_policy", "create_ticket"]
    model = _model("d1", say("Hola."))
    _talk("d1", model, "hola")
    assert model.bound_tools == ["get_refund_policy", "create_ticket"]
    assert model.calls[0][0].content == system_prompt(MUTATIONS["d1"])


def test_d4_returns_the_corrupt_policy():
    assert _value(_tools("d4")["get_refund_policy"].invoke({})) == policy_text(CORRUPT_POLICY)
    assert _value(_tools("baseline")["get_refund_policy"].invoke({})) == get_refund_policy()


@pytest.mark.parametrize("variant", ["baseline", "d2", "d5"])
def test_prompt_variants(variant):
    model = _model(variant, say("Hola."))
    _talk(variant, model, "hola")
    assert model.calls[0][0] == SystemMessage(system_prompt(MUTATIONS[variant]))


def test_d3_uses_the_downgraded_model():
    assert default_model(MUTATIONS["d3"]).model == TARGET_DOWNGRADED_MODEL


@pytest.mark.parametrize("variant", list(MUTATIONS))
def test_every_variant_requests_its_mutation_model(variant):
    model = default_model(MUTATIONS[variant])
    assert model.model == MUTATIONS[variant].model
    assert model.max_tokens == MAX_TOKENS


def test_every_call_has_a_timeout():
    """ChatAnthropic leaves the client without one, and a hung call would stall a batch."""
    assert 0 < REQUEST_TIMEOUT <= 600
    assert default_model(BASELINE).default_request_timeout == REQUEST_TIMEOUT


def test_step_limits():
    assert STEP_LIMIT == 10
    assert 0 < D6_STEP_LIMIT < STEP_LIMIT
    assert step_limit(MUTATIONS["d6"]) == D6_STEP_LIMIT
    for name in ("baseline", "d1", "d2", "d3", "d4", "d5"):
        assert step_limit(MUTATIONS[name]) == STEP_LIMIT


# Rule 3: the step limit cuts, and it is not an error.


@pytest.mark.parametrize(("variant", "limit"), [("d6", D6_STEP_LIMIT), ("baseline", STEP_LIMIT)])
def test_the_step_limit_cuts_and_is_not_an_error(variant, limit):
    model = _model(variant, POLICY_FOREVER, repeat_last=True)
    [turn] = _talk(variant, model, "¿Cuál es la política?")
    assert turn.stop_reason == "step_limit"
    assert len(model.calls) == limit
    assert all(e.kind != "error" for e in turn.events)
    assert [e.result is not None for e in turn.events] == [True] * limit


def test_the_counter_restarts_every_turn():
    one_turn = [POLICY_FOREVER] * (D6_STEP_LIMIT - 1) + [say("Listo.")]
    model = _model("d6", *one_turn, *one_turn)
    turns = _talk("d6", model, "primera", "segunda")
    assert [t.stop_reason for t in turns] == ["completed", "completed"]
    assert len(model.calls) == 2 * D6_STEP_LIMIT


# Rule 4: the history stays valid after a cut.


def test_history_is_valid_after_a_cut():
    model = _model("d6", *[POLICY_FOREVER] * D6_STEP_LIMIT, say("Sigo aquí."))
    cut, after = _talk("d6", model, "¿Cuál es la política?", "¿Sigues?")
    assert cut.stop_reason == "step_limit"
    assert (after.stop_reason, after.reply) == ("completed", "Sigo aquí.")
    for call in model.calls:
        assert _unanswered(call) == set()


# Rule 5: memory between turns, and none between conversations.


def test_system_prompt_is_sent_once_per_call():
    lookup = ask_tools(("lookup_order", {"order_id": "AT-1001"}))
    model = _model("baseline", lookup, say("Entregado."), say("De nada."))
    _talk("baseline", model, "¿Y mi pedido?", "Gracias")
    for call in model.calls:
        assert [type(m) for m in call].count(SystemMessage) == 1
        assert call[0] == SystemMessage(system_prompt(BASELINE))
    assert "¿Y mi pedido?" in [m.content for m in model.calls[-1]]
    assert "Entregado." in [m.content for m in model.calls[-1]]


def test_a_new_conversation_starts_empty():
    model = _model("baseline", say("a"), say("b"))
    _talk("baseline", model, "primera")
    _talk("baseline", model, "segunda")
    assert [m.content for m in model.calls[1]] == [system_prompt(BASELINE), "segunda"]


# Rule 6: a failing tool keeps the conversation going.


def test_a_failing_tool_keeps_the_conversation_going():
    unknown = ask_tools(("lookup_order", {"order_id": "AT-9999"}))
    broken = ask_tools(("create_ticket", {"summary": "sin pedido"}))
    model = _model("baseline", unknown, broken, say("No encontré tu pedido."))
    [turn] = _talk("baseline", model, "¿Y mi pedido AT-9999?")
    missing, failed = turn.events[0], turn.events[1]
    assert missing.result == lookup_order("AT-9999") and missing.is_error is False
    assert failed.tool == "create_ticket" and failed.is_error is True
    assert (turn.stop_reason, turn.reply) == ("completed", "No encontré tu pedido.")


def test_a_tool_that_raises_is_an_error_result_not_a_crash(monkeypatch):
    def down(summary, order_id):
        raise RuntimeError("sistema de tickets caído")

    monkeypatch.setattr("casestudy.editions.langgraph.create_ticket", down)
    ticket = ask_tools(("create_ticket", {"summary": "Laptop", "order_id": "AT-1002"}))
    model = _model("baseline", ticket, say("No pude crear el ticket."))
    [turn] = _talk("baseline", model, "Quiero escalar mi caso.")
    assert turn.events[0].is_error is True
    assert "sistema de tickets caído" in str(turn.events[0].result)
    assert (turn.stop_reason, turn.reply) == ("completed", "No pude crear el ticket.")


# Rule 8: end to end without the API, read by the oracle.


def test_converse_end_to_end_and_the_oracle_reads_it():
    lookup = ask_tools(("lookup_order", {"order_id": "AT-1001"}), ("get_refund_policy", {}))
    model = _model("baseline", lookup, say("Tu solicitud de reembolso fue aprobada."))
    factory = session_factory(lambda variant: builder(variant, model=model), "baseline")
    user = ScriptedUser("Quiero devolver el pedido AT-1001.")
    trace = asyncio.run(converse(factory, user, SEED))
    assert trace.termination == "user_ended"
    tools = [e.tool for e in trace.events if e.kind == "tool_call"]
    assert tools == ["lookup_order", "get_refund_policy"]
    assert communicated_decision(trace) == Decision.APPROVED
