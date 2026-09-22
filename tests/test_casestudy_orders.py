from datetime import date

import pytest

from casestudy.domain.catalog import ORDERS, ORDERS_BY_ID
from casestudy.domain.orders import DOMAIN_TODAY, Order, OrderStatus


def delivered_days(orders):
    return [o.days_since_delivery() for o in orders if o.status is OrderStatus.DELIVERED]


def test_domain_date_is_fixed():
    assert DOMAIN_TODAY == date(2026, 10, 1)


def test_days_since_delivery_uses_the_domain_date():
    assert ORDERS_BY_ID["AT-1001"].days_since_delivery() == 10
    assert ORDERS_BY_ID["AT-1001"].days_since_delivery(date(2026, 10, 11)) == 20


def test_undelivered_order_has_no_days_since_delivery():
    assert ORDERS_BY_ID["AT-1005"].days_since_delivery() is None


def test_only_delivered_orders_have_a_delivery_date():
    with pytest.raises(ValueError):
        Order(
            "X-1",
            "c",
            "p",
            "audio",
            10.0,
            OrderStatus.IN_TRANSIT,
            date(2026, 9, 1),
            date(2026, 9, 2),
        )
    with pytest.raises(ValueError):
        Order("X-2", "c", "p", "audio", 10.0, OrderStatus.DELIVERED, date(2026, 9, 1))


def test_delivery_cannot_precede_purchase():
    with pytest.raises(ValueError):
        Order(
            "X-3",
            "c",
            "p",
            "audio",
            10.0,
            OrderStatus.DELIVERED,
            date(2026, 9, 5),
            date(2026, 9, 1),
        )


def test_catalog_has_between_12_and_16_orders_with_unique_ids():
    assert 12 <= len(ORDERS) <= 16
    assert len(ORDERS_BY_ID) == len(ORDERS)


def test_no_order_sits_near_a_rule_boundary():
    days = delivered_days(ORDERS)
    assert not [d for d in days if 27 <= d <= 33], "cerca de la ventana de 30 días"
    assert not [d for d in days if 360 <= d <= 370], "cerca de la garantía de 365 días"
    assert not [o.order_id for o in ORDERS if 450 <= o.amount_usd <= 550], (
        "cerca del umbral de $500"
    )
