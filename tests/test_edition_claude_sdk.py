import asyncio
import json

import pytest

from agentproof.models import TARGET_BASELINE_MODEL
from casestudy.domain.prompt import SYSTEM_PROMPT
from casestudy.domain.tools import get_refund_policy
from casestudy.editions.claude_sdk import TOOLS, build_options


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
        build_options("d1")
