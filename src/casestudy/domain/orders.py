"""Orders of the fictitious Andina Tech store and the fixed domain date.

The domain date is fixed so that the correct decision for an order never
depends on the day an experiment runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

DOMAIN_TODAY = date(2026, 10, 1)


class OrderStatus(StrEnum):
    PREPARING = "en_preparacion"
    IN_TRANSIT = "en_camino"
    DELIVERED = "entregado"


@dataclass(frozen=True)
class Order:
    order_id: str
    customer: str
    product: str
    category: str
    amount_usd: float
    status: OrderStatus
    purchase_date: date
    delivery_date: date | None = None

    def __post_init__(self) -> None:
        delivered = self.status is OrderStatus.DELIVERED
        if delivered != (self.delivery_date is not None):
            raise ValueError(f"{self.order_id}: only delivered orders have a delivery date")
        if self.delivery_date is not None and self.delivery_date < self.purchase_date:
            raise ValueError(f"{self.order_id}: delivered before it was purchased")

    def days_since_delivery(self, today: date = DOMAIN_TODAY) -> int | None:
        if self.delivery_date is None:
            return None
        return (today - self.delivery_date).days
