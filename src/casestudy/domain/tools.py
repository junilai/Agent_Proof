"""The agent's tools as pure functions, without any framework.

Each edition wraps these functions with its framework's own tool mechanism.
Keys and messages are in Spanish because the model and the customers read them.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import date

from casestudy.domain.catalog import ORDERS_BY_ID
from casestudy.domain.orders import DOMAIN_TODAY, Order
from casestudy.domain.policy import TRUE_POLICY, RefundPolicy
from casestudy.domain.policy_text import policy_text


def lookup_order(
    order_id: str,
    catalog: Mapping[str, Order] = ORDERS_BY_ID,
    today: date = DOMAIN_TODAY,
) -> dict[str, object]:
    key = order_id.strip().upper()
    order = catalog.get(key)
    if order is None:
        return {"error": "PEDIDO_NO_ENCONTRADO", "pedido": key}
    return {
        "pedido": order.order_id,
        "cliente": order.customer,
        "producto": order.product,
        "categoria": order.category,
        "monto_usd": order.amount_usd,
        "estado": order.status.value,
        "fecha_compra": order.purchase_date.isoformat(),
        "fecha_entrega": order.delivery_date.isoformat() if order.delivery_date else None,
        "dias_desde_entrega": order.days_since_delivery(today),
    }


def get_refund_policy(policy: RefundPolicy = TRUE_POLICY) -> str:
    return policy_text(policy)


def create_ticket(summary: str, order_id: str) -> dict[str, str]:
    return {
        "ticket": f"TCK-{uuid.uuid4().hex[:8].upper()}",
        "pedido": order_id.strip().upper(),
        "resumen": summary.strip(),
        "estado": "escalado",
    }
