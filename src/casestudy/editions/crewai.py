"""Case-study agent, CrewAI edition.

A plain CrewAI ``Agent``: the framework-free domain wrapped as CrewAI tools, with
the domain prompt as its backstory and CrewAI's native Anthropic provider. It
knows nothing about AgentProof. Each variant applies one mutation from the
shared domain definition (D1–D6).

CrewAI's step limit is ``max_iter``, which counts tool rounds: a turn that needs
more than ``max_iter`` model calls is cut, as with ``max_turns`` in the Claude
Agent SDK edition, and CrewAI then makes one more call, without tools, that
forces a final answer.
"""

import json
from collections.abc import Callable
from typing import Any

from crewai import LLM
from crewai.llms.base_llm import BaseLLM
from crewai.tools import BaseTool, tool

from casestudy.domain.mutations import MUTATIONS, Mutation
from casestudy.domain.tools import TOOL_DESCRIPTIONS, create_ticket, get_refund_policy, lookup_order

VARIANTS = tuple(MUTATIONS)
STEP_LIMIT = 10
"""Tool rounds per customer turn (``max_iter``)."""
D6_STEP_LIMIT = 2
"""Tool rounds per turn under D6; to be calibrated live with the D-003 probe."""
MAX_TOKENS = 32000
"""Output tokens per model call, the same for every variant (D-012)."""
REQUEST_TIMEOUT = 600.0
"""Seconds per model call; CrewAI's default builds an Anthropic client with none."""


def step_limit(mutation: Mutation) -> int:
    return D6_STEP_LIMIT if mutation.step_limit is not None else STEP_LIMIT


def _as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _domain_tool(name: str, function: Callable[..., str]) -> BaseTool:
    function.__doc__ = TOOL_DESCRIPTIONS[name]
    return tool(name)(function)


def tools_for(mutation: Mutation) -> list[BaseTool]:
    """The agent's tools under a mutation: D1 removes one, D4 changes what one returns.

    Each returns the domain result as JSON, as the other editions show it to the model.
    """

    def lookup(order_id: str) -> str:
        return _as_json(lookup_order(order_id))

    def refund_policy() -> str:
        return _as_json(get_refund_policy(mutation.policy))

    def ticket(summary: str, order_id: str) -> str:
        return _as_json(create_ticket(summary, order_id))

    functions = {
        "lookup_order": lookup,
        "get_refund_policy": refund_policy,
        "create_ticket": ticket,
    }
    return [
        _domain_tool(name, function)
        for name, function in functions.items()
        if name not in mutation.removed_tools
    ]


def default_model(mutation: Mutation) -> BaseLLM:
    """The variant's model through CrewAI's native Anthropic provider, without thinking."""
    return LLM(model=f"anthropic/{mutation.model}", max_tokens=MAX_TOKENS, timeout=REQUEST_TIMEOUT)
