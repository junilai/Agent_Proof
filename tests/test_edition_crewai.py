"""The CrewAI edition: the contract of spec §4, without the API.

Each test names the rule it checks. Those that converse drive the edition through
``CrewAISession`` with a scripted LLM, the way AgentProof runs it.
"""

import asyncio
import json

import pytest

from agentproof.adapters.crewai import CrewAISession, session_factory
from agentproof.conversation import converse
from agentproof.models import TARGET_DOWNGRADED_MODEL
from casestudy.domain.mutations import BASELINE, CORRUPT_POLICY, MUTATIONS
from casestudy.domain.policy import Decision
from casestudy.domain.policy_text import policy_text
from casestudy.domain.prompt import system_prompt
from casestudy.domain.tools import TOOL_DESCRIPTIONS, get_refund_policy, lookup_order
from casestudy.editions.crewai import (
    D6_STEP_LIMIT,
    GOAL,
    MAX_TOKENS,
    REQUEST_TIMEOUT,
    ROLE,
    STEP_LIMIT,
    VARIANTS,
    builder,
    default_model,
    step_limit,
    tools_for,
)
from experiments.oracle.outcome import communicated_decision
from tests.fakes import SEED, ScriptedUser
from tests.fakes_crewai import ScriptedLLM, ask_tools, offline, say


@pytest.fixture(autouse=True)
def network(monkeypatch):
    return offline(monkeypatch)


def _tools(variant="baseline"):
    return {t.name: t for t in tools_for(MUTATIONS[variant])}


# Rule 1: the tools are the domain ones.


def test_baseline_tools_are_the_domain_ones():
    tools = _tools()
    assert list(tools) == list(TOOL_DESCRIPTIONS)
    assert {name: t.description for name, t in tools.items()} == TOOL_DESCRIPTIONS
    assert set(tools["lookup_order"].args_schema.model_fields) == {"order_id"}
    assert set(tools["get_refund_policy"].args_schema.model_fields) == set()
    assert set(tools["create_ticket"].args_schema.model_fields) == {"summary", "order_id"}


def test_tools_wrap_the_domain_and_return_json():
    """Like the other editions, the model reads JSON, not a Python repr."""
    tools = _tools()
    looked_up = tools["lookup_order"].run(order_id="at-1001")
    assert json.loads(looked_up) == lookup_order("AT-1001")
    assert "fecha_entrega" in looked_up and "None" not in looked_up
    assert json.loads(tools["get_refund_policy"].run()) == get_refund_policy()
    ticket = json.loads(tools["create_ticket"].run(summary="Laptop", order_id="AT-1002"))
    assert ticket["estado"] == "escalado" and ticket["pedido"] == "AT-1002"


def test_the_agent_carries_the_variant_tools():
    agent = builder("baseline", model=ScriptedLLM())
    assert [t.name for t in agent.tools] == list(TOOL_DESCRIPTIONS)


# Rule 2: the six mutations, with the same definition.


def test_every_mutation_is_a_variant():
    assert VARIANTS == tuple(MUTATIONS)


def test_unknown_variants_are_rejected():
    with pytest.raises(ValueError):
        builder("d9")


def test_d1_has_no_lookup_order():
    assert list(_tools("d1")) == ["get_refund_policy", "create_ticket"]
    assert [t.name for t in builder("d1", model=ScriptedLLM()).tools] == [
        "get_refund_policy",
        "create_ticket",
    ]


def test_d4_returns_the_corrupt_policy():
    assert json.loads(_tools("d4")["get_refund_policy"].run()) == policy_text(CORRUPT_POLICY)
    assert json.loads(_tools("baseline")["get_refund_policy"].run()) == get_refund_policy()


@pytest.mark.parametrize("variant", list(MUTATIONS))
def test_the_backstory_is_the_domain_prompt_verbatim(variant):
    agent = builder(variant, model=ScriptedLLM())
    assert agent.backstory == system_prompt(MUTATIONS[variant])
    assert agent.role and agent.goal


def test_d3_uses_the_downgraded_model():
    assert default_model(MUTATIONS["d3"]).model == TARGET_DOWNGRADED_MODEL


@pytest.mark.parametrize("variant", list(MUTATIONS))
def test_every_variant_requests_its_mutation_model_natively(variant):
    model = default_model(MUTATIONS[variant])
    assert type(model).__name__ == "AnthropicCompletion"
    assert model.is_litellm is False
    assert model.model == MUTATIONS[variant].model
    assert model.max_tokens == MAX_TOKENS


def test_every_call_has_a_timeout():
    """CrewAI's default builds a client without one, and a hung call would stall a batch."""
    assert 0 < REQUEST_TIMEOUT <= 600
    assert default_model(BASELINE).timeout == REQUEST_TIMEOUT


def test_the_builder_uses_the_variant_model_by_default():
    assert builder("d3").llm.model == TARGET_DOWNGRADED_MODEL


def test_step_limits():
    """``max_iter`` counts tool rounds; the cut adds one forced, tool-less answer."""
    assert STEP_LIMIT == 10
    assert 0 < D6_STEP_LIMIT < STEP_LIMIT
    assert step_limit(MUTATIONS["d6"]) == D6_STEP_LIMIT
    for name in ("baseline", "d1", "d2", "d3", "d4", "d5"):
        assert step_limit(MUTATIONS[name]) == STEP_LIMIT
    assert builder("d6", model=ScriptedLLM()).max_iter == D6_STEP_LIMIT
    assert builder("baseline", model=ScriptedLLM()).max_iter == STEP_LIMIT


def test_nothing_that_would_change_the_loop_is_on():
    """No tool cache, usage cap, memory, planning, delegation or history summaries."""
    agent = builder("baseline", model=ScriptedLLM())
    assert agent.cache is False
    assert agent.allow_delegation is False
    assert agent.respect_context_window is False
    assert agent.memory in (None, False)
    assert not agent.knowledge_sources
    assert not agent.planning
    assert agent.guardrail is None
    for tool in agent.tools:
        assert tool.max_usage_count is None
        assert tool.result_as_answer is False


POLICY = ask_tools(("get_refund_policy", {}))


def _llm(variant="baseline", *responses):
    return ScriptedLLM(model=MUTATIONS[variant].model, responses=list(responses))


def _talk(variant, llm, *messages):
    async def run():
        async with CrewAISession(builder(variant, model=llm)) as session:
            return [await session.send(m) for m in messages]

    return asyncio.run(run())


def _system(call):
    [system] = [m["content"] for m in call["messages"] if m["role"] == "system"]
    return system


def _unanswered(messages):
    """Tool calls without a result by the time the customer speaks again or the model is called."""
    pending = set()
    for message in messages:
        if message["role"] == "user" and pending:
            return pending
        pending |= {call["id"] for call in message.get("tool_calls") or []}
        if message["role"] == "tool":
            pending.discard(message["tool_call_id"])
    return pending


# Rule 1, conversing: the model is offered the variant's tools, and a lookup is traced.


@pytest.mark.parametrize("variant", ["baseline", "d1"])
def test_the_model_is_offered_the_variant_tools(variant):
    llm = _llm(variant, say("Hola."))
    _talk(variant, llm, "hola")
    assert llm.calls[0]["tools"] == list(_tools(variant))


def test_a_lookup_reaches_the_trace():
    lookup = ask_tools(("lookup_order", {"order_id": "AT-1001"}))
    [turn] = _talk("baseline", _llm("baseline", lookup, say("Fue entregado.")), "¿Y mi pedido?")
    call = turn.events[0]
    assert (call.kind, call.tool, call.arguments) == (
        "tool_call",
        "lookup_order",
        {"order_id": "AT-1001"},
    )
    assert call.result == lookup_order("AT-1001")
    assert turn.reply == "Fue entregado."


@pytest.mark.parametrize("variant", ["baseline", "d1", "d2", "d5"])
def test_the_system_message_carries_the_domain_prompt_verbatim(variant):
    """CrewAI wraps it in its own English frame, which is the framework's native use."""
    llm = _llm(variant, say("Hola."))
    _talk(variant, llm, "hola")
    prompt = system_prompt(MUTATIONS[variant])
    assert _system(llm.calls[0]) == f"You are {ROLE}. {prompt}\nYour personal goal is: {GOAL}"


# Rule 3: the step limit cuts, it is not an error, and the forced answer is the reply.


@pytest.mark.parametrize(("variant", "limit"), [("d6", D6_STEP_LIMIT), ("baseline", STEP_LIMIT)])
def test_the_step_limit_cuts_and_is_not_an_error(variant, limit):
    llm = _llm(variant, *[POLICY] * limit, say("Te cuento la política."))
    [turn] = _talk(variant, llm, "¿Cuál es la política?")
    assert turn.stop_reason == "step_limit"
    assert len(llm.calls) == limit + 1
    assert llm.calls[-1]["tools"] == []
    assert all(e.kind != "error" for e in turn.events)
    assert [e.result is not None for e in turn.events if e.kind == "tool_call"] == [True] * limit
    assert turn.reply == turn.events[-1].text == "Te cuento la política."


def test_the_counter_restarts_every_turn():
    one_turn = [POLICY] * D6_STEP_LIMIT + [say("Listo.")]
    llm = _llm("d6", *one_turn, *one_turn)
    turns = _talk("d6", llm, "primera", "segunda")
    assert [t.stop_reason for t in turns] == ["step_limit", "step_limit"]
    assert len(llm.calls) == 2 * (D6_STEP_LIMIT + 1)


def test_one_round_less_than_the_limit_completes():
    llm = _llm("d6", *[POLICY] * (D6_STEP_LIMIT - 1), say("Listo."))
    [turn] = _talk("d6", llm, "hola")
    assert (turn.stop_reason, turn.reply) == ("completed", "Listo.")


# Rule 4: the history stays valid after a cut, and keeps what the customer was told.


def test_history_is_valid_after_a_cut():
    llm = _llm("d6", *[POLICY] * D6_STEP_LIMIT, say("Forzada."), say("Sigo aquí."))
    cut, after = _talk("d6", llm, "¿Cuál es la política?", "¿Sigues?")
    assert cut.stop_reason == "step_limit"
    assert (after.stop_reason, after.reply) == ("completed", "Sigo aquí.")
    for call in llm.calls:
        assert _unanswered(call["messages"]) == set()
    assert "Forzada." in [m.get("content") for m in llm.calls[-1]["messages"]]


# Rule 5: memory between turns, and none between conversations.


def test_system_prompt_is_sent_once_per_call():
    lookup = ask_tools(("lookup_order", {"order_id": "AT-1001"}))
    llm = _llm("baseline", lookup, say("Entregado."), say("De nada."))
    _talk("baseline", llm, "¿Y mi pedido?", "Gracias")
    for call in llm.calls:
        assert [m["role"] for m in call["messages"]].count("system") == 1
        assert system_prompt(BASELINE) in _system(call)
    last = [m.get("content") or "" for m in llm.calls[-1]["messages"]]
    assert any("¿Y mi pedido?" in content for content in last)
    assert "Entregado." in last


def test_a_new_conversation_starts_empty():
    llm = _llm("baseline", say("a"), say("b"))
    _talk("baseline", llm, "primera")
    _talk("baseline", llm, "segunda")
    assert [m["role"] for m in llm.calls[1]["messages"]] == ["system", "user"]
    assert "primera" not in str(llm.calls[1]["messages"])


# Rule 6: a failing tool keeps the conversation going.


def test_a_failing_tool_keeps_the_conversation_going():
    unknown = ask_tools(("lookup_order", {"order_id": "AT-9999"}))
    broken = ask_tools(("create_ticket", {"summary": "sin pedido"}))
    llm = _llm("baseline", unknown, broken, say("No encontré tu pedido."))
    [turn] = _talk("baseline", llm, "¿Y mi pedido AT-9999?")
    missing, failed = turn.events[0], turn.events[1]
    assert missing.result == lookup_order("AT-9999") and missing.is_error is False
    assert failed.tool == "create_ticket" and failed.is_error is True
    assert (turn.stop_reason, turn.reply) == ("completed", "No encontré tu pedido.")


def test_a_tool_that_raises_is_an_error_result_not_a_crash(monkeypatch):
    def down(summary, order_id):
        raise RuntimeError("sistema de tickets caído")

    monkeypatch.setattr("casestudy.editions.crewai.create_ticket", down)
    ticket = ask_tools(("create_ticket", {"summary": "Laptop", "order_id": "AT-1002"}))
    llm = _llm("baseline", ticket, say("No pude crear el ticket."))
    [turn] = _talk("baseline", llm, "Quiero escalar mi caso.")
    assert turn.events[0].is_error is True
    assert "sistema de tickets caído" in str(turn.events[0].result)
    assert (turn.stop_reason, turn.reply) == ("completed", "No pude crear el ticket.")


def test_identical_calls_run_the_tool_each_time():
    """No tool cache: two tickets asked for in one turn are two tickets."""
    ticket = ("create_ticket", {"summary": "Laptop", "order_id": "AT-1002"})
    llm = _llm("baseline", ask_tools(ticket, ticket), say("Listo."))
    [turn] = _talk("baseline", llm, "Escala dos veces.")
    tickets = [e.result["ticket"] for e in turn.events if e.kind == "tool_call"]
    assert len(tickets) == 2 and tickets[0] != tickets[1]


# Rule 8: end to end without the API, read by the oracle.


def test_converse_end_to_end_and_the_oracle_reads_it(network):
    lookup = ask_tools(("lookup_order", {"order_id": "AT-1001"}), ("get_refund_policy", {}))
    llm = _llm("baseline", lookup, say("Tu solicitud de reembolso fue aprobada."))
    factory = session_factory(lambda variant: builder(variant, model=llm), "baseline")
    user = ScriptedUser("Quiero devolver el pedido AT-1001.")
    trace = asyncio.run(converse(factory, user, SEED))
    assert trace.termination == "user_ended"
    tools = [e.tool for e in trace.events if e.kind == "tool_call"]
    assert tools == ["lookup_order", "get_refund_policy"]
    assert communicated_decision(trace) == Decision.APPROVED
    assert network == []
