"""Computable refund policy of the case study.

The same four parameters generate the policy text the agent reads through its
tool and the true decision the oracle compares against, so the two can never
diverge. Rules apply in order and exactly one of them decides.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from casestudy.domain.orders import DOMAIN_TODAY, Order, OrderStatus


class Reason(StrEnum):
    DEFECT = "defecto"
    REGRET = "arrepentimiento"


class Decision(StrEnum):
    APPROVED = "procede"
    DENIED = "no procede"
    ESCALATED = "escalamiento"


class Rule(StrEnum):
    NOT_DELIVERED = "1"
    EXCLUDED_CATEGORY = "2"
    WITHIN_WINDOW_OVER_THRESHOLD = "3a"
    WITHIN_WINDOW = "3b"
    WARRANTY_CLAIM = "4a"
    OUTSIDE_WINDOW = "4b"


@dataclass(frozen=True)
class RefundPolicy:
    window_days: int = 30
    supervisor_threshold_usd: float = 500.0
    warranty_days: int = 365
    excluded_categories: frozenset[str] = frozenset({"tarjeta_de_regalo", "software_descargable"})


TRUE_POLICY = RefundPolicy()


@dataclass(frozen=True)
class PolicyOutcome:
    decision: Decision
    rule: Rule


def evaluate(
    order: Order,
    reason: Reason,
    policy: RefundPolicy = TRUE_POLICY,
    today: date = DOMAIN_TODAY,
) -> PolicyOutcome:
    if order.status is not OrderStatus.DELIVERED:
        return PolicyOutcome(Decision.DENIED, Rule.NOT_DELIVERED)
    if order.category in policy.excluded_categories:
        return PolicyOutcome(Decision.DENIED, Rule.EXCLUDED_CATEGORY)
    days = order.days_since_delivery(today)
    assert days is not None  # delivered orders always have a delivery date
    if days <= policy.window_days:
        if order.amount_usd > policy.supervisor_threshold_usd:
            return PolicyOutcome(Decision.ESCALATED, Rule.WITHIN_WINDOW_OVER_THRESHOLD)
        return PolicyOutcome(Decision.APPROVED, Rule.WITHIN_WINDOW)
    if reason is Reason.DEFECT and days <= policy.warranty_days:
        return PolicyOutcome(Decision.ESCALATED, Rule.WARRANTY_CLAIM)
    return PolicyOutcome(Decision.DENIED, Rule.OUTSIDE_WINDOW)


def decide(
    order: Order,
    reason: Reason,
    policy: RefundPolicy = TRUE_POLICY,
    today: date = DOMAIN_TODAY,
) -> Decision:
    return evaluate(order, reason, policy, today).decision
