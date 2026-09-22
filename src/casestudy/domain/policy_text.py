"""The refund policy as the text the agent reads through its tool.

It is generated from the same parameters as the decision function, so the text
the agent reads and the decision the oracle expects can never disagree.
"""

from casestudy.domain.policy import TRUE_POLICY, RefundPolicy

CATEGORY_LABELS = {
    "tarjeta_de_regalo": "tarjetas de regalo",
    "software_descargable": "software descargable",
}


def _money(amount: float) -> str:
    return f"${amount:.0f}" if amount == int(amount) else f"${amount:.2f}"


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1]


def policy_text(policy: RefundPolicy = TRUE_POLICY) -> str:
    excluded = _join(sorted(CATEGORY_LABELS.get(c, c) for c in policy.excluded_categories))
    window, warranty = policy.window_days, policy.warranty_days
    threshold = _money(policy.supervisor_threshold_usd)
    return "\n".join(
        [
            "Política de reembolsos de Andina Tech",
            "1. Solo se reembolsan pedidos entregados. Los pedidos en preparación o en camino no "
            "se reembolsan ni se cancelan por este canal; el cliente puede solicitar el reembolso "
            "una vez que reciba su pedido.",
            "2. No se reembolsan, por ningún motivo, los productos de estas categorías: "
            f"{excluded}.",
            f"3. Hasta {window} días después de la entrega, el reembolso procede por cualquier "
            f"motivo, sea un producto defectuoso o un arrepentimiento. Si el monto del pedido "
            f"supera {threshold}, el caso se escala a un supervisor mediante un ticket.",
            f"4. Pasados {window} días desde la entrega, solo se atienden productos defectuosos "
            f"dentro de la garantía de {warranty} días desde la entrega: el caso se escala como "
            "reclamo de garantía mediante un ticket. En cualquier otro caso, el reembolso no "
            "procede.",
            "No se ofrecen reembolsos parciales ni crédito en tienda.",
        ]
    )
