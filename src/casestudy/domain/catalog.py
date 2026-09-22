"""Knowledge base of the case study: the fixed set of Andina Tech orders.

Together, the orders cover every branch of the refund policy, and none sits
near a rule boundary, so the true decision is never a matter of rounding.
"""

from datetime import date

from casestudy.domain.orders import Order, OrderStatus

_DELIVERED = OrderStatus.DELIVERED

# Tabla de datos: dos líneas por pedido, sin el formateo automático.
# fmt: off
ORDERS: tuple[Order, ...] = (
    Order("AT-1001", "María Pérez", "Audífonos inalámbricos Sony WH-CH720N", "audio",
          89.90, _DELIVERED, date(2026, 9, 17), date(2026, 9, 21)),
    Order("AT-1002", "Carlos Ruiz", "Laptop Lenovo IdeaPad Slim 5", "computadoras",
          1149.00, _DELIVERED, date(2026, 9, 17), date(2026, 9, 21)),
    Order("AT-1003", "Ana Torres", "Monitor Samsung de 27 pulgadas", "monitores",
          310.00, _DELIVERED, date(2026, 6, 29), date(2026, 7, 3)),
    Order("AT-1004", "Luis Gómez", "Cámara web Logitech C920", "accesorios",
          75.00, _DELIVERED, date(2025, 8, 23), date(2025, 8, 27)),
    Order("AT-1005", "Sofía Vera", "Tablet Samsung Galaxy Tab S9 FE", "computadoras",
          249.00, OrderStatus.PREPARING, date(2026, 9, 29)),
    Order("AT-1006", "Diego León", "Teclado mecánico Keychron K2", "accesorios",
          159.00, OrderStatus.IN_TRANSIT, date(2026, 9, 26)),
    Order("AT-1007", "Elena Mora", "Tarjeta de regalo Andina Tech", "tarjeta_de_regalo",
          50.00, _DELIVERED, date(2026, 9, 19), date(2026, 9, 23)),
    Order("AT-1008", "Pedro Salas", "Licencia digital de antivirus", "software_descargable",
          69.99, _DELIVERED, date(2026, 9, 12), date(2026, 9, 16)),
    Order("AT-1009", "Lucía Andrade", "Mouse inalámbrico Logitech M185", "accesorios",
          45.50, _DELIVERED, date(2026, 9, 24), date(2026, 9, 28)),
    Order("AT-1010", "Jorge Cevallos", "Mouse ergonómico Logitech Lift", "accesorios",
          39.90, _DELIVERED, date(2026, 7, 29), date(2026, 8, 2)),
    Order("AT-1011", "Valeria Paredes", "Teléfono Samsung Galaxy A55", "telefonia",
          899.00, _DELIVERED, date(2026, 9, 7), date(2026, 9, 11)),
    Order("AT-1012", "Andrés Molina", "Teclado Logitech MX Keys", "accesorios",
          120.00, _DELIVERED, date(2026, 9, 5), date(2026, 9, 9)),
    Order("AT-1013", "Gabriela Ortiz", "Parlante JBL Charge 5", "audio",
          180.00, _DELIVERED, date(2026, 3, 11), date(2026, 3, 15)),
)
# fmt: on

ORDERS_BY_ID: dict[str, Order] = {order.order_id: order for order in ORDERS}
