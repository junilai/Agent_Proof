import asyncio
import json

import pytest

from agentproof.models import TARGET_BASELINE_MODEL, TARGET_DOWNGRADED_MODEL
from casestudy.domain.mutations import CORRUPT_POLICY, MUTATIONS
from casestudy.domain.policy_text import policy_text
from casestudy.domain.prompt import SYSTEM_PROMPT, system_prompt
from casestudy.domain.tools import get_refund_policy
from casestudy.editions.claude_sdk import TOOLS, VARIANTS, build_options, tools_for


def call(tool, args):
    return json.loads(asyncio.run(tool.handler(args))["content"][0]["text"])


def test_baseline_options():
    options = build_options("baseline")
    assert options.model == TARGET_BASELINE_MODEL and options.system_prompt == SYSTEM_PROMPT
    assert options.max_turns == 10


def test_the_agent_is_isolated_from_the_machine():
    options = build_options()
    assert options.tools == [] and options.setting_sources == [] and options.skills == []
    assert options.strict_mcp_config is True
    assert list(options.mcp_servers) == ["store"]
    assert options.allowed_tools == [
        "mcp__store__lookup_order",
        "mcp__store__get_refund_policy",
        "mcp__store__create_ticket",
    ]


def test_tools_wrap_the_domain():
    lookup, policy, ticket = TOOLS
    assert call(lookup, {"order_id": "at-1001"})["dias_desde_entrega"] == 10
    assert call(policy, {}) == get_refund_policy()
    assert call(ticket, {"summary": "Laptop", "order_id": "AT-1002"})["estado"] == "escalado"


def test_unknown_variants_are_rejected():
    with pytest.raises(ValueError):
        build_options("d9")


def test_every_mutation_is_a_variant():
    assert VARIANTS == tuple(MUTATIONS)


def test_d1_loses_the_order_tool():
    options = build_options("d1")
    assert "mcp__store__lookup_order" not in options.allowed_tools
    assert [t.name for t in tools_for(MUTATIONS["d1"])] == ["get_refund_policy", "create_ticket"]
    assert options.system_prompt == SYSTEM_PROMPT


def test_d4_reads_the_corrupt_policy():
    _, policy, _ = tools_for(MUTATIONS["d4"])
    assert call(policy, {}) == policy_text(CORRUPT_POLICY)
    assert call(policy, {}) != get_refund_policy()


def test_prompt_model_and_step_limit_follow_the_mutation():
    assert build_options("d2").system_prompt == system_prompt(MUTATIONS["d2"]) != SYSTEM_PROMPT
    assert build_options("d5").system_prompt == system_prompt(MUTATIONS["d5"]) != SYSTEM_PROMPT
    assert build_options("d3").model == TARGET_DOWNGRADED_MODEL
    assert build_options("d6").max_turns == 2
    for name in ("d1", "d2", "d3", "d4", "d5"):
        assert build_options(name).max_turns == 10
