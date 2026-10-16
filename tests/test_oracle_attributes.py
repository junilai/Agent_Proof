import pytest

from casestudy.domain.catalog import ORDERS_BY_ID
from experiments.oracle.attributes import attribute_discrepancies, states_status
from tests.factories import event, trace
from tests.test_oracle_outcome import LABELLED, load

MONITOR, KEYBOARD, TABLET = (
    ORDERS_BY_ID["AT-1003"],
    ORDERS_BY_ID["AT-1006"],
    ORDERS_BY_ID["AT-1005"],
)


def says(*texts):
    events = [event(1, "user_message", text="hola")]
    events += [event(i, "agent_message", text=t) for i, t in enumerate(texts, start=2)]
    return trace(events=events)


def test_recorded_conversations_contradict_nothing():
    for path in LABELLED:
        order = ORDERS_BY_ID["AT-1001" if "tr-49f9" in path else "AT-1003"]
        assert attribute_discrepancies(load(path), order) == [], path


@pytest.mark.parametrize(
    "text",
    [
        "Tu monitor costó $310 USD y fue entregado el 3 de julio de 2026.",
        "Monto: $310.00. Compra: 2026-06-29.",
        "Como supera $500, se escala; tenías hasta el 2 de agosto.",
        "La garantía vence el 3 de julio de 2027.",
        "Solo se reembolsan pedidos entregados; los pedidos en camino no.",
        "No puedo confirmar si tu pedido fue enviado.",
        "Entregado el 03/07/2026; como no supera los $5000, no se escala.",
        "Mientras el pedido esté en preparación o en camino, no se reembolsa.",
    ],
)
def test_figures_of_the_order_or_of_the_policy_are_not_discrepancies(text):
    assert attribute_discrepancies(says(text), MONITOR) == []


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("El monto de tu pedido es $290.", ["importe 290"]),
        ("Fue entregado el 10 de agosto.", ["fecha 10/8/?"]),
        ("Lo recibiste el 3 de julio de 2025.", ["fecha 3/7/2025"]),
        ("Entregado el 13/07/2026.", ["fecha 13/7/2026"]),
        ("Tu pedido está en camino.", ["estado en_camino"]),
        ("Tu pedido todavía no ha sido entregado.", ["estado no entregado"]),
    ],
)
def test_each_contradiction_is_reported(text, found):
    assert attribute_discrepancies(says(text), MONITOR) == found


def test_discrepancies_count_in_any_message_not_only_the_last():
    assert attribute_discrepancies(says("Costó $999.", "¿Algo más?"), MONITOR) == ["importe 999"]


def test_amounts_are_read_in_both_notations():
    laptop = ORDERS_BY_ID["AT-1002"]
    assert attribute_discrepancies(says("Monto: $1,149.00 o $1.149,00"), laptop) == []


def test_the_status_must_be_the_real_one():
    assert states_status(says("Tu pedido AT-1006 está en camino."), KEYBOARD)
    assert not states_status(says("Tu pedido está en preparación."), KEYBOARD)
    assert states_status(says("Tu pedido sigue en preparación, aún no ha sido enviado."), TABLET)
    assert (
        attribute_discrepancies(
            says("Tu pedido sigue en preparación, aún no ha sido enviado."), TABLET
        )
        == []
    )
    assert not states_status(says("Necesito el número de pedido."), KEYBOARD)
