from datetime import date, timedelta

import pytest

from casestudy.domain.catalog import ORDERS, ORDERS_BY_ID
from casestudy.domain.orders import DOMAIN_TODAY, Order, OrderStatus
from casestudy.domain.policy import Decision, Reason, RefundPolicy, Rule, decide, evaluate


@pytest.mark.parametrize(
    ("order_id", "reason", "decision", "rule"),
    [
        ("AT-1005", Reason.DEFECT, Decision.DENIED, Rule.NOT_DELIVERED),
        ("AT-1006", Reason.REGRET, Decision.DENIED, Rule.NOT_DELIVERED),
        ("AT-1007", Reason.DEFECT, Decision.DENIED, Rule.EXCLUDED_CATEGORY),
        ("AT-1008", Reason.REGRET, Decision.DENIED, Rule.EXCLUDED_CATEGORY),
        ("AT-1002", Reason.REGRET, Decision.ESCALATED, Rule.WITHIN_WINDOW_OVER_THRESHOLD),
        ("AT-1011", Reason.DEFECT, Decision.ESCALATED, Rule.WITHIN_WINDOW_OVER_THRESHOLD),
        ("AT-1001", Reason.DEFECT, Decision.APPROVED, Rule.WITHIN_WINDOW),
        ("AT-1009", Reason.REGRET, Decision.APPROVED, Rule.WITHIN_WINDOW),
        ("AT-1003", Reason.DEFECT, Decision.ESCALATED, Rule.WARRANTY_CLAIM),
        ("AT-1013", Reason.DEFECT, Decision.ESCALATED, Rule.WARRANTY_CLAIM),
        ("AT-1003", Reason.REGRET, Decision.DENIED, Rule.OUTSIDE_WINDOW),
        ("AT-1010", Reason.REGRET, Decision.DENIED, Rule.OUTSIDE_WINDOW),
        ("AT-1004", Reason.DEFECT, Decision.DENIED, Rule.OUTSIDE_WINDOW),
    ],
)
def test_each_rule_on_the_knowledge_base(order_id, reason, decision, rule):
    outcome = evaluate(ORDERS_BY_ID[order_id], reason)
    assert (outcome.decision, outcome.rule) == (decision, rule)


def test_knowledge_base_covers_every_rule():
    assert {evaluate(order, reason).rule for order in ORDERS for reason in Reason} == set(Rule)


def test_decision_values_are_the_closed_vocabulary():
    assert {d.value for d in Decision} == {"procede", "no procede", "escalamiento"}


def test_decide_is_the_decision_of_evaluate():
    for order in ORDERS:
        for reason in Reason:
            assert decide(order, reason) == evaluate(order, reason).decision


def order_delivered(days_ago: int, amount: float = 100.0) -> Order:
    delivered = DOMAIN_TODAY - timedelta(days=days_ago)
    return Order("X-9", "c", "p", "audio", amount, OrderStatus.DELIVERED, delivered, delivered)


def test_rule_boundaries():
    assert decide(order_delivered(30), Reason.REGRET) is Decision.APPROVED
    assert decide(order_delivered(31), Reason.REGRET) is Decision.DENIED
    assert decide(order_delivered(10, amount=500.0), Reason.REGRET) is Decision.APPROVED
    assert decide(order_delivered(10, amount=500.01), Reason.REGRET) is Decision.ESCALATED
    assert decide(order_delivered(365), Reason.DEFECT) is Decision.ESCALATED
    assert decide(order_delivered(366), Reason.DEFECT) is Decision.DENIED


def test_parameters_drive_the_decision():
    corrupted = RefundPolicy(window_days=90)
    order = ORDERS_BY_ID["AT-1010"]
    assert decide(order, Reason.REGRET) is Decision.DENIED
    assert decide(order, Reason.REGRET, corrupted) is Decision.APPROVED


def test_today_can_be_overridden():
    assert (
        decide(ORDERS_BY_ID["AT-1001"], Reason.REGRET, today=date(2026, 12, 1)) is Decision.DENIED
    )
