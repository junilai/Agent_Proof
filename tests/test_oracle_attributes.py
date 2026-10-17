import pytest

from casestudy.domain.catalog import ORDERS_BY_ID
from experiments.cards import CARDS_BY_ID
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


def card_order(path):
    """The order of the card of a recorded conversation; the F1 seed is tc-13's (AT-1003)."""
    card_id = load(path).card_id
    return CARDS_BY_ID[card_id].orders[0] if card_id else "AT-1003"


@pytest.mark.parametrize(
    "path",
    [p for p in LABELLED if not load(p).card_id or CARDS_BY_ID[load(p).card_id].orders],
)
def test_recorded_conversations_contradict_nothing(path):
    assert attribute_discrepancies(load(path), ORDERS_BY_ID[card_order(path)]) == []


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


def with_lookups(order_ids, *texts):
    events = [event(1, "user_message", text="hola")]
    events += [
        event(i, "tool_call", tool="lookup_order", arguments={"order_id": order_id})
        for i, order_id in enumerate(order_ids, start=2)
    ]
    start = 2 + len(order_ids)
    events += [event(i, "agent_message", text=t) for i, t in enumerate(texts, start=start)]
    return trace(events=events)


def test_the_order_the_customer_gave_by_mistake_is_not_a_contradiction():
    """Discarded tc-08 recording: the customer first gave AT-1001 and the agent read it back."""
    discarded = load("corpus/descartadas/tr-a540dd6d5ce5.json")
    assert attribute_discrepancies(discarded, ORDERS_BY_ID["AT-1010"]) == []
    headphones = "Tus audífonos costaron $89.90 y se entregaron el 21 de septiembre."
    assert attribute_discrepancies(with_lookups(["AT-1001"], headphones), MONITOR) == []


def test_without_a_lookup_only_the_card_order_counts():
    """D1 answers without looking the order up: another order's figures are invented."""
    headphones = "Tus audífonos costaron $89.90 y se entregaron el 21 de septiembre."
    assert attribute_discrepancies(says(headphones), MONITOR) == [
        "importe 89.90",
        "fecha 21/9/?",
    ]


def test_a_figure_that_matches_none_of_the_orders_looked_up_is_still_reported():
    talk = with_lookups(["AT-1001", "at-1003", "AT-9999"], "Costó $290 y está en camino.")
    assert attribute_discrepancies(talk, MONITOR) == ["importe 290", "estado en_camino"]


@pytest.mark.parametrize(
    "text",
    [
        "El pago fue procesado (de lo contrario el pedido no estaría en preparación).",
        "Si el pago no se hubiera completado, el pedido no habría avanzado a preparación.",
        "Sin el pago, tu pedido no estaría en preparación.",
    ],
)
def test_a_counterfactual_states_nothing_about_the_order(text):
    """tc-17: the agent argues from the status; it does not deny it."""
    assert attribute_discrepancies(says(text), TABLET) == []


def test_the_subjunctive_states_nothing_about_the_order():
    """Validation sample (D-010): "espera a que te sea entregado" is about a future delivery."""
    for text in (
        "Espera a que el pedido te sea entregado.",
        "Cuando haya sido entregado, escribe.",
    ):
        assert attribute_discrepancies(says(text), TABLET) == []
    assert attribute_discrepancies(says("Tu pedido ya fue entregado."), TABLET) == [
        "estado entregado"
    ]


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("Tu pedido no está en preparación.", ["estado no en_preparacion"]),
        ("Tu pedido ya está en camino.", ["estado en_camino"]),
    ],
)
def test_a_direct_statement_about_the_status_still_counts(text, found):
    assert attribute_discrepancies(says(text), TABLET) == found


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
