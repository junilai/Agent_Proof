"""Case-study agent, Claude Agent SDK edition.

A plain Claude Agent SDK application: the framework-free domain wrapped as
in-process MCP tools, with the SDK's own loop. It knows nothing about AgentProof.
The agent only gets its three tools: no built-in tools, no filesystem settings or
instruction files, no skills and no MCP servers other than its own. Each variant
applies one mutation from the shared domain definition (D1–D6); the baseline is
the agent the seed corpus is recorded with.
"""

import json
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, SdkMcpTool, create_sdk_mcp_server, tool

from casestudy.domain.mutations import BASELINE, MUTATIONS, Mutation
from casestudy.domain.prompt import system_prompt
from casestudy.domain.tools import create_ticket, get_refund_policy, lookup_order

SERVER_NAME = "store"
STEP_LIMIT = 10
VARIANTS = tuple(MUTATIONS)

_LOOKUP = "Consulta un pedido por su identificador (por ejemplo, AT-1001)."
_POLICY = "Devuelve el texto de la política de reembolsos vigente."
_TICKET = "Escala un caso creando un ticket para un supervisor o un reclamo de garantía."


def _content(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}


def tools_for(mutation: Mutation) -> tuple[SdkMcpTool[Any], ...]:
    """The agent's tools under a mutation: D1 removes one, D4 changes what one returns."""

    @tool("lookup_order", _LOOKUP, {"order_id": str})
    async def lookup_order_tool(args: dict[str, Any]) -> dict[str, Any]:
        return _content(lookup_order(args["order_id"]))

    @tool("get_refund_policy", _POLICY, {})
    async def refund_policy_tool(args: dict[str, Any]) -> dict[str, Any]:
        return _content(get_refund_policy(mutation.policy))

    @tool("create_ticket", _TICKET, {"summary": str, "order_id": str})
    async def create_ticket_tool(args: dict[str, Any]) -> dict[str, Any]:
        return _content(create_ticket(args["summary"], args["order_id"]))

    every = (lookup_order_tool, refund_policy_tool, create_ticket_tool)
    return tuple(t for t in every if t.name not in mutation.removed_tools)


TOOLS = tools_for(BASELINE)


def build_options(variant: str = "baseline") -> ClaudeAgentOptions:
    """The agent for a variant: the baseline or one of the mutations D1–D6."""
    if variant not in MUTATIONS:
        raise ValueError(f"unknown variant: {variant}")
    mutation = MUTATIONS[variant]
    tools = tools_for(mutation)
    server = create_sdk_mcp_server(name=SERVER_NAME, version="1.0.0", tools=list(tools))
    return ClaudeAgentOptions(
        system_prompt=system_prompt(mutation),
        model=mutation.model,
        tools=[],
        mcp_servers={SERVER_NAME: server},
        strict_mcp_config=True,
        allowed_tools=[f"mcp__{SERVER_NAME}__{t.name}" for t in tools],
        setting_sources=[],
        skills=[],
        max_turns=mutation.step_limit or STEP_LIMIT,
    )
