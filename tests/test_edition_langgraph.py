"""The LangGraph edition: the contract of spec §4, without the API.

Each test names the rule it checks. Those that converse drive the edition through
``LangGraphSession`` with a scripted model, the way AgentProof runs it.
"""

import json

import pytest

from agentproof.models import TARGET_DOWNGRADED_MODEL
from casestudy.domain.mutations import CORRUPT_POLICY, MUTATIONS
from casestudy.domain.policy_text import policy_text
from casestudy.domain.tools import TOOL_DESCRIPTIONS, get_refund_policy, lookup_order
from casestudy.editions.langgraph import (
    D6_STEP_LIMIT,
    MAX_TOKENS,
    STEP_LIMIT,
    VARIANTS,
    default_model,
    step_limit,
    tools_for,
)


def _value(result):
    if isinstance(result, str):
        try:
            return json.loads(result)
        except ValueError:
            return result
    return result


def _tools(variant="baseline"):
    return {t.name: t for t in tools_for(MUTATIONS[variant])}


def test_baseline_tools_are_the_domain_ones():
    tools = _tools()
    assert list(tools) == list(TOOL_DESCRIPTIONS)
    assert {name: t.description for name, t in tools.items()} == TOOL_DESCRIPTIONS
    assert set(tools["lookup_order"].args) == {"order_id"}
    assert set(tools["get_refund_policy"].args) == set()
    assert set(tools["create_ticket"].args) == {"summary", "order_id"}


def test_tools_wrap_the_domain():
    tools = _tools()
    assert _value(tools["lookup_order"].invoke({"order_id": "at-1001"})) == lookup_order("AT-1001")
    assert _value(tools["get_refund_policy"].invoke({})) == get_refund_policy()
    ticket = _value(tools["create_ticket"].invoke({"summary": "Laptop", "order_id": "AT-1002"}))
    assert ticket["estado"] == "escalado" and ticket["pedido"] == "AT-1002"


def test_every_mutation_is_a_variant():
    assert VARIANTS == tuple(MUTATIONS)


def test_d1_has_no_lookup_order():
    assert list(_tools("d1")) == ["get_refund_policy", "create_ticket"]


def test_d4_returns_the_corrupt_policy():
    assert _value(_tools("d4")["get_refund_policy"].invoke({})) == policy_text(CORRUPT_POLICY)
    assert _value(_tools("baseline")["get_refund_policy"].invoke({})) == get_refund_policy()


def test_d3_uses_the_downgraded_model():
    assert default_model(MUTATIONS["d3"]).model == TARGET_DOWNGRADED_MODEL


@pytest.mark.parametrize("variant", list(MUTATIONS))
def test_every_variant_requests_its_mutation_model(variant):
    model = default_model(MUTATIONS[variant])
    assert model.model == MUTATIONS[variant].model
    assert model.max_tokens == MAX_TOKENS


def test_step_limits():
    assert STEP_LIMIT == 10
    assert 0 < D6_STEP_LIMIT < STEP_LIMIT
    assert step_limit(MUTATIONS["d6"]) == D6_STEP_LIMIT
    for name in ("baseline", "d1", "d2", "d3", "d4", "d5"):
        assert step_limit(MUTATIONS[name]) == STEP_LIMIT
