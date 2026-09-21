import re

from casestudy.domain.policy import RefundPolicy
from casestudy.domain.policy_text import policy_text
from casestudy.domain.tools import create_ticket, get_refund_policy, lookup_order


def test_lookup_returns_order_data_with_days_since_delivery():
    data = lookup_order(" at-1001 ")
    assert data["pedido"] == "AT-1001"
    assert data["estado"] == "entregado"
    assert data["dias_desde_entrega"] == 10
    assert data["fecha_entrega"] == "2026-09-21"
    assert data["monto_usd"] == 89.90


def test_lookup_of_undelivered_order_has_no_delivery_fields():
    data = lookup_order("AT-1006")
    assert data["estado"] == "en_camino"
    assert data["fecha_entrega"] is None and data["dias_desde_entrega"] is None


def test_lookup_of_unknown_order_returns_an_error():
    assert lookup_order("AT-9999") == {"error": "PEDIDO_NO_ENCONTRADO", "pedido": "AT-9999"}


def test_refund_policy_tool_returns_the_policy_text():
    assert get_refund_policy() == policy_text()
    assert "90 días" in get_refund_policy(RefundPolicy(window_days=90))


def test_create_ticket_escalates_with_a_unique_id():
    first = create_ticket("  Laptop sobre el umbral  ", "at-1002")
    second = create_ticket("Otro caso", "AT-1003")
    assert re.fullmatch(r"TCK-[0-9A-F]{8}", first["ticket"])
    assert first["ticket"] != second["ticket"]
    assert first == {
        **first,
        "pedido": "AT-1002",
        "resumen": "Laptop sobre el umbral",
        "estado": "escalado",
    }
