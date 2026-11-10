"""Case-study agent, smolagents edition.

A plain smolagents ``ToolCallingAgent``: the framework-free domain wrapped as
smolagents tools, the domain prompt in the native ``instructions`` slot, and the
model through ``LiteLLMModel``. It knows nothing about AgentProof. Each variant
applies one mutation from the shared domain definition (D1–D6); a step is one
model call, as with ``max_turns`` in the Claude Agent SDK edition.

smolagents adds its own pieces, used as they come: its ReAct prompt around the
domain prompt, the ``final_answer`` tool through which the agent replies, and one
extra model call, without tools, that forces an answer once ``max_steps`` is spent.
"""

from typing import Any

from smolagents import Tool

from casestudy.domain.mutations import MUTATIONS, Mutation
from casestudy.domain.tools import TOOL_DESCRIPTIONS, create_ticket, get_refund_policy, lookup_order

VARIANTS = tuple(MUTATIONS)
STEP_LIMIT = 10
D6_STEP_LIMIT = 2
"""Model calls per turn under D6, before the forced answer; to calibrate live (D-003)."""
MAX_TOKENS = 32000
"""Output tokens per model call, the same for every variant (D-012)."""
REQUEST_TIMEOUT = 600.0
"""Seconds per model call, so a hung call cannot stall a conversation."""


def _string(description: str = "") -> dict[str, str]:
    # smolagents requires a description per argument; the other editions send none.
    return {"type": "string", "description": description}


def step_limit(mutation: Mutation) -> int:
    return D6_STEP_LIMIT if mutation.step_limit is not None else STEP_LIMIT


def tools_for(mutation: Mutation) -> list[Tool]:
    """The agent's tools under a mutation: D1 removes one, D4 changes what one returns."""

    class LookupOrder(Tool):
        name = "lookup_order"
        description = TOOL_DESCRIPTIONS[name]
        inputs = {"order_id": _string()}
        output_type = "object"

        def forward(self, order_id: str) -> dict[str, Any]:
            return lookup_order(order_id)

    class GetRefundPolicy(Tool):
        name = "get_refund_policy"
        description = TOOL_DESCRIPTIONS[name]
        inputs: dict[str, Any] = {}
        output_type = "string"

        def forward(self) -> str:
            return get_refund_policy(mutation.policy)

    class CreateTicket(Tool):
        name = "create_ticket"
        description = TOOL_DESCRIPTIONS[name]
        inputs = {"summary": _string(), "order_id": _string()}
        output_type = "object"

        def forward(self, summary: str, order_id: str) -> dict[str, str]:
            return create_ticket(summary, order_id)

    tools = [LookupOrder(), GetRefundPolicy(), CreateTicket()]
    return [tool for tool in tools if tool.name not in mutation.removed_tools]
