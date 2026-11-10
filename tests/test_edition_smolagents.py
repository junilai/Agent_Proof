"""The smolagents edition: the contract of spec §4, without the API.

Each test names the rule it checks. Those that converse drive the edition through
``SmolagentsSession`` with a scripted model, the way AgentProof runs it.
"""

import pytest

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
from tests.fakes_smolagents import ScriptedModel

FINAL_ANSWER = "final_answer"


def _model(variant="baseline", *responses, repeat_last=False):
    return ScriptedModel(
        model_id=MUTATIONS[variant].model, responses=list(responses), repeat_last=repeat_last
    )


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


def test_tools_wrap_the_domain():
    tools = _tools()
    assert tools["lookup_order"](order_id="at-1001") == lookup_order("AT-1001")
    assert tools["get_refund_policy"]() == get_refund_policy()
    ticket = tools["create_ticket"](summary="Laptop", order_id="AT-1002")
    assert ticket["estado"] == "escalado" and ticket["pedido"] == "AT-1002"


# Rule 2: the six mutations, with the same definition.


def test_every_mutation_is_a_variant():
    assert VARIANTS == tuple(MUTATIONS)


def test_unknown_variants_are_rejected():
    with pytest.raises(ValueError):
        builder("d9")


def test_d1_has_no_lookup_order():
    assert list(_tools("d1")) == ["get_refund_policy", "create_ticket"]
    assert _agent_tools("d1") == ["get_refund_policy", "create_ticket"]


def test_d4_returns_the_corrupt_policy():
    assert _tools("d4")["get_refund_policy"]() == policy_text(CORRUPT_POLICY)
    assert _tools("baseline")["get_refund_policy"]() == get_refund_policy()


@pytest.mark.parametrize("variant", list(MUTATIONS))
def test_the_domain_prompt_goes_in_the_native_instructions(variant):
    agent = builder(variant, model=_model(variant))
    assert agent.instructions == system_prompt(MUTATIONS[variant])
    assert system_prompt(MUTATIONS[variant]) in agent.system_prompt


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
