"""Exposed set of each degradation (§5.4).

Which scenarios a degradation can affect, decided by computable rules over what
was fixed before the induction: the seed trace and its card. D3 replaces the
whole model, so it has no exposed set.
"""

from __future__ import annotations

from agentproof.schema import Trace, scenario_id_for
from experiments.cards import Card

_PREFIX = scenario_id_for("")


def seed_of(scenario_id: str) -> str:
    """The seed trace a scenario was induced from, read from its identifier alone."""
    if not scenario_id.startswith(_PREFIX):
        raise ValueError(f"not a scenario identifier: {scenario_id}")
    return scenario_id.removeprefix(_PREFIX)


def tool_calls(trace: Trace) -> list[str]:
    return [e.tool or "" for e in trace.events if e.kind == "tool_call"]


def is_exposed(operator: str, card: Card, seed: Trace) -> bool | None:
    calls = tool_calls(seed)
    match operator:
        case "d1":
            return "lookup_order" in calls
        case "d2":
            return card.has_decision
        case "d3":
            return None
        case "d4":
            return "get_refund_policy" in calls
        case "d5":
            return card.expected == "no_procede"
        case "d6":
            return len(calls) >= 3
    raise ValueError(f"unknown operator: {operator}")
