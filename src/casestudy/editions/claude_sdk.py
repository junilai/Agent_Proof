"""Case-study agent, Claude Agent SDK edition.

A plain Claude Agent SDK application: the framework-free domain wrapped as
in-process MCP tools, with the SDK's own loop. It knows nothing about AgentProof.
The agent only gets its three tools: no built-in tools, no filesystem settings or
instruction files, no skills and no MCP servers other than its own.
"""

import json
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, create_sdk_mcp_server, tool

from agentproof.models import TARGET_BASELINE_MODEL
from casestudy.domain.prompt import SYSTEM_PROMPT
from casestudy.domain.tools import create_ticket, get_refund_policy, lookup_order

SERVER_NAME = "store"
STEP_LIMIT = 10
VARIANTS = ("baseline",)

_LOOKUP = "Consulta un pedido por su identificador (por ejemplo, AT-1001)."
_POLICY = "Devuelve el texto de la política de reembolsos vigente."
_TICKET = "Escala un caso creando un ticket para un supervisor o un reclamo de garantía."


def _content(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}


@tool("lookup_order", _LOOKUP, {"order_id": str})
async def lookup_order_tool(args: dict[str, Any]) -> dict[str, Any]:
    return _content(lookup_order(args["order_id"]))


@tool("get_refund_policy", _POLICY, {})
async def refund_policy_tool(args: dict[str, Any]) -> dict[str, Any]:
    return _content(get_refund_policy())


@tool("create_ticket", _TICKET, {"summary": str, "order_id": str})
async def create_ticket_tool(args: dict[str, Any]) -> dict[str, Any]:
    return _content(create_ticket(args["summary"], args["order_id"]))


TOOLS = (lookup_order_tool, refund_policy_tool, create_ticket_tool)


def build_options(variant: str = "baseline") -> ClaudeAgentOptions:
    """The agent for a variant; F3 adds the degraded variants D1–D6."""
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant: {variant}")
    server = create_sdk_mcp_server(name=SERVER_NAME, version="1.0.0", tools=list(TOOLS))
    return ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        model=TARGET_BASELINE_MODEL,
        tools=[],
        mcp_servers={SERVER_NAME: server},
        strict_mcp_config=True,
        allowed_tools=[f"mcp__{SERVER_NAME}__{t.name}" for t in TOOLS],
        setting_sources=[],
        skills=[],
        max_turns=STEP_LIMIT,
    )
