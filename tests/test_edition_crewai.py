"""The CrewAI edition: the contract of spec §4, without the API.

Each test names the rule it checks. Those that converse drive the edition through
``CrewAISession`` with a scripted LLM, the way AgentProof runs it.
"""

import json

import pytest

from agentproof.models import TARGET_DOWNGRADED_MODEL
from casestudy.domain.mutations import BASELINE, CORRUPT_POLICY, MUTATIONS
from casestudy.domain.policy_text import policy_text
from casestudy.domain.tools import TOOL_DESCRIPTIONS, get_refund_policy, lookup_order
from casestudy.editions.crewai import (
    D6_STEP_LIMIT,
    MAX_TOKENS,
    REQUEST_TIMEOUT,
    STEP_LIMIT,
    VARIANTS,
    default_model,
    step_limit,
    tools_for,
)
from tests.fakes_crewai import offline


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


# Rule 2: the six mutations, with the same definition.


def test_every_mutation_is_a_variant():
    assert VARIANTS == tuple(MUTATIONS)


def test_d1_has_no_lookup_order():
    assert list(_tools("d1")) == ["get_refund_policy", "create_ticket"]


def test_d4_returns_the_corrupt_policy():
    assert json.loads(_tools("d4")["get_refund_policy"].run()) == policy_text(CORRUPT_POLICY)
    assert json.loads(_tools("baseline")["get_refund_policy"].run()) == get_refund_policy()


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


def test_step_limits():
    """``max_iter`` counts tool rounds; the cut adds one forced, tool-less answer."""
    assert STEP_LIMIT == 10
    assert 0 < D6_STEP_LIMIT < STEP_LIMIT
    assert step_limit(MUTATIONS["d6"]) == D6_STEP_LIMIT
    for name in ("baseline", "d1", "d2", "d3", "d4", "d5"):
        assert step_limit(MUTATIONS[name]) == STEP_LIMIT
