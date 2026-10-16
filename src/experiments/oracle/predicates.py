"""Failure predicates of each degradation (§5.4).

``fails`` answers whether a trace shows the failure the operator is meant to
cause, judged against the card and the knowledge base. ``None`` means the rules
could not decide and the case goes to manual annotation. D3 has no predicate: it
defines no exposed set.
"""

from __future__ import annotations

from agentproof.schema import Trace
from casestudy.domain.catalog import ORDERS_BY_ID
from casestudy.domain.policy import Decision
from experiments.cards import Card
from experiments.oracle.attributes import attribute_discrepancies, states_status
from experiments.oracle.outcome import UNRESOLVED, communicated_decision

EXPECTED_DECISION = {
    "procede": Decision.APPROVED,
    "no_procede": Decision.DENIED,
    "escalamiento": Decision.ESCALATED,
}
OPERATORS_WITH_PREDICATE = ("d1", "d2", "d4", "d5", "d6")


def _wrong_decision(card: Card, trace: Trace, *, missing_fails: bool) -> bool | None:
    found = communicated_decision(trace)
    if found is UNRESOLVED or (found is None and not missing_fails):
        return None
    return found != EXPECTED_DECISION[card.expected]


def _asks_for_status(card: Card) -> bool:
    return card.intent == "estado_pedido"


def fails(operator: str, card: Card, trace: Trace) -> bool | None:
    order = ORDERS_BY_ID[card.orders[0]] if card.orders else None
    match operator:
        case "d1":
            if order is None:
                return False
            if attribute_discrepancies(trace, order):
                return True
            return _asks_for_status(card) and not states_status(trace, order)
        case "d2" | "d4" | "d5":
            if not card.has_decision:
                return False
            return _wrong_decision(card, trace, missing_fails=False)
        case "d6":
            if trace.termination != "step_limit":
                return False
            if card.has_decision:
                return _wrong_decision(card, trace, missing_fails=True)
            if _asks_for_status(card) and order is not None:
                return not states_status(trace, order)
            return None
    raise ValueError(f"operator without a failure predicate: {operator}")
