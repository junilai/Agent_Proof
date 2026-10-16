"""Failure predicates of each degradation (§5.4).

``fails`` answers whether a trace shows the failure the operator is meant to
cause, judged against the card and the knowledge base. It reads the evidence of
the trace, extracted by the rules or, when the author annotated the trace by
hand, taken from that annotation. ``None`` means the rules could not decide and
the case goes to manual annotation. D3 has no predicate: it defines no exposed
set.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentproof.schema import Trace
from casestudy.domain.catalog import ORDERS_BY_ID
from casestudy.domain.policy import Decision
from experiments.cards import Card
from experiments.oracle.attributes import attribute_discrepancies, states_status
from experiments.oracle.outcome import UNRESOLVED, Extracted, communicated_decision

EXPECTED_DECISION = {
    "procede": Decision.APPROVED,
    "no_procede": Decision.DENIED,
    "escalamiento": Decision.ESCALATED,
}
OPERATORS_WITH_PREDICATE = ("d1", "d2", "d4", "d5", "d6")


@dataclass(frozen=True)
class Evidence:
    """What a trace communicated, as far as the predicates need it."""

    decision: Extracted
    contradicts_base: bool
    answers_card: bool | None
    """Whether the agent gave what the card asked for; None when rules cannot tell."""
    manual: bool = False


def asks_for_status(card: Card) -> bool:
    return card.intent == "estado_pedido"


def evidence(card: Card, trace: Trace) -> Evidence:
    """The evidence the rules extract from a trace."""
    order = ORDERS_BY_ID[card.orders[0]] if card.orders else None
    return Evidence(
        decision=communicated_decision(trace) if card.has_decision else None,
        contradicts_base=bool(order and attribute_discrepancies(trace, order)),
        answers_card=states_status(trace, order) if order and asks_for_status(card) else None,
    )


def _wrong_decision(card: Card, found: Evidence, *, missing_fails: bool) -> bool | None:
    if found.decision is UNRESOLVED:
        return None
    if found.decision is None:
        return True if missing_fails or found.manual else None
    return found.decision != EXPECTED_DECISION[card.expected]


def fails(
    operator: str, card: Card, trace: Trace, annotated: Evidence | None = None
) -> bool | None:
    found = annotated or evidence(card, trace)
    match operator:
        case "d1":
            if found.contradicts_base:
                return True
            return asks_for_status(card) and found.answers_card is False
        case "d2" | "d4" | "d5":
            if not card.has_decision:
                return False
            return _wrong_decision(card, found, missing_fails=False)
        case "d6":
            if trace.termination != "step_limit":
                return False
            if card.has_decision:
                return _wrong_decision(card, found, missing_fails=True)
            return None if found.answers_card is None else not found.answers_card
    raise ValueError(f"operator without a failure predicate: {operator}")
