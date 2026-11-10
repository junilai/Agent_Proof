"""The smolagents edition: the contract of spec §4, without the API.

Each test names the rule it checks. Those that converse drive the edition through
``SmolagentsSession`` with a scripted model, the way AgentProof runs it.
"""

import asyncio

import pytest
from smolagents.models import get_clean_message_list, tool_role_conversions

from agentproof.adapters.smolagents import SmolagentsSession
from agentproof.models import TARGET_DOWNGRADED_MODEL
from agentproof.pricing import PRICES
from casestudy.domain.mutations import BASELINE, CORRUPT_POLICY, MUTATIONS
from casestudy.domain.policy_text import policy_text
from casestudy.domain.prompt import system_prompt
from casestudy.domain.tools import TOOL_DESCRIPTIONS, get_refund_policy, lookup_order
from casestudy.editions.smolagents import (
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
from tests.fakes_smolagents import ScriptedModel, ask_tools, plain, say, text_of

FINAL_ANSWER = "final_answer"
POLICY_FOREVER = ask_tools(("get_refund_policy", {}))


def _model(variant="baseline", *responses, repeat_last=False):
    return ScriptedModel(
        model_id=MUTATIONS[variant].model, responses=list(responses), repeat_last=repeat_last
    )


def _talk(variant, model, *messages):
    async def run():
        async with SmolagentsSession(builder(variant, model=model)) as session:
            return [await session.send(m) for m in messages]

    return asyncio.run(run())


def _texts(call):
    return [text_of(m) for m in call]


def _tools(variant="baseline"):
    return {t.name: t for t in tools_for(MUTATIONS[variant])}


def _agent_tools(variant):
    return [name for name in builder(variant, model=_model(variant)).tools if name != FINAL_ANSWER]


# Rule 1: the tools are the domain ones.


def test_baseline_tools_are_the_domain_ones():
    tools = _tools()
    assert list(tools) == list(TOOL_DESCRIPTIONS)
    assert {name: t.description for name, t in tools.items()} == TOOL_DESCRIPTIONS
    assert set(tools["lookup_order"].inputs) == {"order_id"}
    assert set(tools["get_refund_policy"].inputs) == set()
    assert set(tools["create_ticket"].inputs) == {"summary", "order_id"}


def test_the_agent_has_the_variant_tools_and_the_native_final_answer():
    agent = builder("baseline", model=_model())
    assert list(agent.tools) == [*TOOL_DESCRIPTIONS, FINAL_ANSWER]


def test_every_call_sends_the_variant_tools():
    model = _model("baseline", say("Hola."))
    _talk("baseline", model, "hola")
    assert model.tools == [[*TOOL_DESCRIPTIONS, FINAL_ANSWER]]


def test_tools_wrap_the_domain():
    tools = _tools()
    assert tools["lookup_order"](order_id="at-1001") == lookup_order("AT-1001")
    assert tools["get_refund_policy"]() == get_refund_policy()
    ticket = tools["create_ticket"](summary="Laptop", order_id="AT-1002")
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
    assert _agent_tools("d1") == ["get_refund_policy", "create_ticket"]
    model = _model("d1", say("Hola."))
    _talk("d1", model, "hola")
    assert model.tools == [["get_refund_policy", "create_ticket", FINAL_ANSWER]]


def test_d4_returns_the_corrupt_policy():
    assert _tools("d4")["get_refund_policy"]() == policy_text(CORRUPT_POLICY)
    assert _tools("baseline")["get_refund_policy"]() == get_refund_policy()


@pytest.mark.parametrize("variant", list(MUTATIONS))
def test_the_domain_prompt_goes_in_the_native_instructions(variant):
    agent = builder(variant, model=_model(variant))
    assert agent.instructions == system_prompt(MUTATIONS[variant])
    assert system_prompt(MUTATIONS[variant]) in agent.system_prompt
    model = _model(variant, say("Hola."))
    _talk(variant, model, "hola")
    assert model.calls[0][0].role == "system"
    assert system_prompt(MUTATIONS[variant]) in text_of(model.calls[0][0])


def test_d3_uses_the_downgraded_model():
    assert default_model(MUTATIONS["d3"]).model_id == f"anthropic/{TARGET_DOWNGRADED_MODEL}"


@pytest.mark.parametrize("variant", list(MUTATIONS))
def test_every_variant_requests_its_mutation_model(variant):
    model = default_model(MUTATIONS[variant])
    assert model.model_id == f"anthropic/{MUTATIONS[variant].model}"
    assert model.model_id.removeprefix("anthropic/") in PRICES
    assert model.kwargs == {"max_tokens": MAX_TOKENS, "timeout": REQUEST_TIMEOUT}


def test_the_builder_uses_the_variant_model_by_default():
    assert builder("d3").model.model_id == f"anthropic/{TARGET_DOWNGRADED_MODEL}"


def test_every_call_has_a_timeout():
    """Without it, a hung call would stall a batch."""
    assert MAX_TOKENS == 32000
    assert 0 < REQUEST_TIMEOUT <= 600
    assert default_model(BASELINE).kwargs["timeout"] == REQUEST_TIMEOUT


def test_step_limits():
    assert STEP_LIMIT == 10
    assert 0 < D6_STEP_LIMIT < STEP_LIMIT
    assert step_limit(MUTATIONS["d6"]) == D6_STEP_LIMIT
    for name in ("baseline", "d1", "d2", "d3", "d4", "d5"):
        assert step_limit(MUTATIONS[name]) == STEP_LIMIT
    assert builder("d6", model=_model("d6")).max_steps == D6_STEP_LIMIT
    assert builder("baseline", model=_model()).max_steps == STEP_LIMIT


def test_no_extra_model_calls_are_configured():
    """Planning and streamed outputs would add calls or change their shape."""
    agent = builder("baseline", model=_model())
    assert agent.planning_interval is None
    assert agent.stream_outputs is False
    assert agent.managed_agents == {}
    assert agent.final_answer_checks == []


# Rule 3: the step limit cuts, and it is not an error. smolagents then makes one
# more call, without tools, and that forced answer is the turn's reply.


@pytest.mark.parametrize(("variant", "limit"), [("d6", D6_STEP_LIMIT), ("baseline", STEP_LIMIT)])
def test_the_step_limit_cuts_and_is_not_an_error(variant, limit):
    model = _model(variant, *[POLICY_FOREVER] * limit, plain("Respuesta forzada."))
    [turn] = _talk(variant, model, "¿Cuál es la política?")
    assert turn.stop_reason == "step_limit"
    assert len(model.calls) == limit + 1
    assert all(e.kind != "error" for e in turn.events)
    calls = [e for e in turn.events if e.kind == "tool_call"]
    assert [e.result is not None and not e.is_error for e in calls] == [True] * limit
    assert turn.reply == "Respuesta forzada."
    assert turn.events[-1].text == "Respuesta forzada."


def test_the_forced_answer_is_asked_without_tools_or_the_domain_prompt():
    """Framework behaviour to declare (D-012): the extra call has its own system prompt."""
    model = _model("d6", *[POLICY_FOREVER] * D6_STEP_LIMIT, plain("Forzada."))
    _talk("d6", model, "¿Cuál es la política?")
    assert model.tools[-1] == []
    assert system_prompt(MUTATIONS["d6"]) not in "\n".join(_texts(model.calls[-1]))


def test_a_failed_forced_answer_is_an_error():
    model = _model("d6", *[POLICY_FOREVER] * D6_STEP_LIMIT, RuntimeError("overloaded"))
    [turn] = _talk("d6", model, "¿Cuál es la política?")
    assert turn.stop_reason == "error"
    assert turn.reply == ""
    assert "overloaded" in turn.events[-1].text


def test_the_counter_restarts_every_turn():
    one_turn = [POLICY_FOREVER] * (D6_STEP_LIMIT - 1) + [say("Listo.")]
    model = _model("d6", *one_turn, *one_turn)
    turns = _talk("d6", model, "primera", "segunda")
    assert [t.stop_reason for t in turns] == ["completed", "completed"]
    assert len(model.calls) == 2 * D6_STEP_LIMIT


# Rule 4: the history stays valid after a cut. smolagents replays tool calls and
# results as text, so the API never receives a tool_use without its result.


def _valid_for_the_api(call):
    messages = get_clean_message_list(call, role_conversions=tool_role_conversions)
    roles = [m["role"] for m in messages]
    blocks = [b for m in messages for b in m["content"]]
    return (
        roles[0] == "system"
        and roles[1::2] == ["user"] * len(roles[1::2])
        and roles[2::2] == ["assistant"] * len(roles[2::2])
        and all(b["type"] == "text" for b in blocks)
        and all(m.tool_calls is None for m in call)
    )


def test_history_is_valid_after_a_cut():
    model = _model("d6", *[POLICY_FOREVER] * D6_STEP_LIMIT, plain("Forzada."), say("Sigo aquí."))
    cut, after = _talk("d6", model, "¿Cuál es la política?", "¿Sigues?")
    assert cut.stop_reason == "step_limit"
    assert (after.stop_reason, after.reply) == ("completed", "Sigo aquí.")
    assert all(_valid_for_the_api(call) for call in model.calls)


def test_the_next_turn_does_not_see_the_forced_answer():
    """Framework behaviour to declare (D-012): the forced answer is not replayed."""
    model = _model("d6", *[POLICY_FOREVER] * D6_STEP_LIMIT, plain("Forzada."), say("Sigo."))
    _talk("d6", model, "¿Cuál es la política?", "¿Sigues?")
    assert "Forzada." not in "\n".join(_texts(model.calls[-1]))


# Rule 5: memory between turns, and none between conversations.


def test_the_system_prompt_is_sent_once_per_call():
    lookup = ask_tools(("lookup_order", {"order_id": "AT-1001"}))
    model = _model("baseline", lookup, say("Entregado."), say("De nuevo."))
    _talk("baseline", model, "¿Y mi pedido?", "Gracias")
    for call in model.calls:
        assert [m.role for m in call].count("system") == 1
        assert call[0].role == "system"
    seen = "\n".join(_texts(model.calls[-1]))
    assert "¿Y mi pedido?" in seen and "Entregado." in seen


def test_a_new_conversation_starts_empty():
    model = _model("baseline", say("a"), say("b"))
    _talk("baseline", model, "primera")
    _talk("baseline", model, "segunda")
    assert [m.role for m in model.calls[1]] == ["system", "user"]
    assert "segunda" in text_of(model.calls[1][1])
