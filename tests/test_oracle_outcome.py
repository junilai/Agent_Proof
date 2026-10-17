from pathlib import Path

import pytest

from agentproof.schema import Trace
from casestudy.domain.policy import Decision
from experiments.oracle.outcome import UNRESOLVED, communicated_decision, decision_in
from tests.factories import event, trace

ROOT = Path(__file__).resolve().parents[1]
HITO = "evidence/f1-hito/results/runs"
PRO, NO, ESC = Decision.APPROVED, Decision.DENIED, Decision.ESCALATED
UNRES = UNRESOLVED

# Each agent message recorded so far, labelled by hand once: the decision it states,
# or None when it states none. Follow-up answers that restate the escalated case
# (steps 9 of the F1 runs) are labelled as an escalation. A ticket opened for another
# matter is labelled by the refund decision the message states (D-009).
LABELLED = {
    "corpus/seeds/tr-49f9d41b2bc6.json": {2: None, 4: None, 8: PRO, 10: PRO},
    "corpus/seeds/tr-a450dfb016b9.json": {2: None, 4: None, 8: ESC, 10: ESC, 12: ESC, 14: None},
    "corpus/seeds/tr-b5c4babdd36b.json": {2: None, 4: None, 6: None, 8: None, 10: None, 12: None},
    # The other seventeen elicited conversations, labelled by D-009.
    "corpus/seeds/tr-08b90a7484e8.json": {2: None, 6: ESC, 8: ESC, 10: None, 12: ESC, 14: None},
    "corpus/seeds/tr-0b1ba54b3bff.json": {
        2: None, 4: None, 8: ESC, 10: ESC, 12: ESC, 14: ESC, 16: None,
    },
    "corpus/seeds/tr-1bcac31bb099.json": {2: None, 4: None, 7: ESC, 9: ESC, 11: ESC},
    "corpus/seeds/tr-1d3d63b4ec80.json": {2: None, 6: NO, 8: NO, 10: UNRES, 12: None, 14: None},
    "corpus/seeds/tr-3ee71ca0bdcf.json": {2: None, 4: None, 7: None, 9: None},
    "corpus/seeds/tr-69b396c04669.json": {
        2: None, 4: None, 6: None, 8: None, 12: PRO, 14: None, 17: None,
    },
    "corpus/seeds/tr-6c6ab21b3116.json": {2: None, 5: None, 7: None},
    "corpus/seeds/tr-8e76607664f8.json": {2: None, 6: PRO, 8: PRO},
    "corpus/seeds/tr-91931c2b95fa.json": {2: None, 6: ESC, 8: ESC},
    "corpus/seeds/tr-96424db58a33.json": {2: None, 5: None, 8: NO, 11: NO, 13: None},
    "corpus/seeds/tr-9a551596a82f.json": {2: None, 4: None, 6: None, 8: NO, 10: NO, 12: None},
    "corpus/seeds/tr-c54fe59dc976.json": {2: None, 5: PRO, 7: None, 9: PRO},
    "corpus/seeds/tr-d707df857e02.json": {2: None, 6: NO, 8: UNRES, 10: NO, 12: None},
    "corpus/seeds/tr-dcdc60171b83.json": {2: None, 5: None, 7: None, 9: None},
    "corpus/seeds/tr-e326cdcb18af.json": {2: None, 4: None, 8: NO, 10: NO, 12: NO},
    "corpus/seeds/tr-f4615497b746.json": {2: None, 5: PRO, 7: None, 9: None, 11: PRO},
    "corpus/seeds/tr-f4fbcd9bf2e0.json": {2: None, 5: None, 8: NO, 10: NO, 12: NO},
    "evidence/f1-hito/corpus/seeds/tr-0a7510c36f69.json": {
        2: None, 6: ESC, 8: ESC, 10: ESC, 12: ESC,
    },
    f"{HITO}/baseline-a-20260922-120459/traces/tr-4a254116c0d0.json": {
        2: None, 5: ESC, 7: ESC, 9: ESC,
    },
    f"{HITO}/baseline-a-20260922-120459/traces/tr-cf6339f1d3b8.json": {
        2: None, 5: ESC, 7: ESC, 9: ESC,
    },
    f"{HITO}/baseline-b-20260922-120538/traces/tr-161f1c9b5a3b.json": {
        2: None, 5: ESC, 7: ESC, 9: ESC,
    },
    f"{HITO}/baseline-b-20260922-120538/traces/tr-251c26fd65a0.json": {
        2: None, 5: ESC, 7: ESC, 9: ESC,
    },
}  # fmt: skip


def load(path: str) -> Trace:
    return Trace.model_validate_json((ROOT / path).read_text(encoding="utf-8"))


def agent_messages(path: str) -> dict[int, str]:
    return {e.step: e.text or "" for e in load(path).events if e.kind == "agent_message"}


def test_every_recorded_agent_message_is_labelled():
    assert {path: set(agent_messages(path)) for path in LABELLED} == {
        path: set(labels) for path, labels in LABELLED.items()
    }
    assert sum(len(labels) for labels in LABELLED.values()) == 120


@pytest.mark.parametrize("path", LABELLED)
def test_no_recorded_message_is_classified_the_wrong_way(path):
    """A message may be missed (None) but never given a decision it does not state."""
    for step, text in agent_messages(path).items():
        label, found = LABELLED[path][step], decision_in(text)
        assert found == label or (label is not None and found is None), (step, found)


def test_misses_are_few_and_almost_all_restate_an_earlier_decision():
    """A follow-up that only refers to an existing ticket may be missed: the earlier
    message already stated the decision, so the conversation keeps it (D-002)."""
    first_statements = [
        (path, step)
        for path, labels in LABELLED.items()
        for step, text in agent_messages(path).items()
        if labels[step] is not None
        and decision_in(text) is None
        and labels[step] not in [labels[earlier] for earlier in labels if earlier < step]
    ]
    assert len(first_statements) <= 2, first_statements


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Tu reembolso de $89.90 ha sido aprobado.", PRO),
        ("Según la política, el reembolso procede sin problema.", PRO),
        ("Lo siento, el reembolso no procede.", NO),
        ("Las tarjetas de regalo no son reembolsables.", NO),
        ("No puedo procesar un reembolso para ese pedido.", NO),
        ("Ya no aplica para reembolso directo por este canal.", NO),
        ("Voy a escalar tu caso como reclamo de garantía.", ESC),
        ("Creé el ticket TCK-12AB34CD para un supervisor.", ESC),
        ("El reembolso procede, pero como supera $500 lo escalo a un supervisor.", ESC),
        ("No aplica el reembolso directo, así que escalaré tu caso.", ESC),
    ],
)
def test_each_rule(text, expected):
    assert decision_in(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Como el monto es menor a $500, no requiere escalar a un supervisor.",
        "Para poder escalar tu caso necesito el número de pedido.",
        "No tengo forma de generar el ticket por esta vía.",
        "¿Quieres que escale tu caso a un supervisor?",
        "Si el monto supera $500, el reembolso procede con un ticket.",
        "No se ofrecen créditos en tienda ni reembolsos parciales.",
        "Puedo ayudarte con consultas de pedidos y solicitudes de reembolso.",
        "El sistema con el que gestiono los tickets está vinculado a un pedido.",
        "Con esa confirmación, escalo tu caso como reclamo de garantía.",
        "Necesito el comprobante; de lo contrario no podría procesar el reembolso.",
        "Una vez recibido, solicita el reembolso (procede por cualquier motivo).",
        "Deberías esperar a recibirlo y luego solicitar el reembolso, que procede sin problema.",
    ],
)
def test_negations_purposes_questions_and_conditionals_state_no_decision(text):
    assert decision_in(text) is None


# Agent message of the elicited conversation of card tc-10, which expects the refund not to
# proceed: the agent denies it and, at the customer's request, opens a technical-support ticket.
TC10_TICKET = (
    "¡Listo! He creado el ticket **TCK-785568E4** para tu caso. Un especialista de soporte "
    "técnico se pondrá en contacto contigo para revisar el problema con tu cámara web.\n\n"
    "Recuerda que, como te comenté, el reembolso no procede al estar fuera del periodo de "
    "garantía, pero esperamos que el equipo técnico pueda ayudarte a resolver el inconveniente."
    "\n\n¿Hay algo más en lo que pueda ayudarte?"
)


def test_a_technical_support_ticket_is_not_an_escalation_of_the_refund():
    assert decision_in(TC10_TICKET) == NO
    assert decision_in("Creé el ticket TCK-1 para que soporte técnico revise tu cámara.") is None


@pytest.mark.parametrize(
    "amount",
    ["supera los $500", "supera los 500 dólares", "excede los USD 500", "es mayor a $500.00"],
)
def test_each_way_of_stating_the_threshold_keeps_the_escalation(amount):
    text = f"Como el monto {amount}, escalé tu reembolso a un supervisor; logística te contactará."
    assert decision_in(text) == ESC


@pytest.mark.parametrize("amount", ["no supera los $500", "no es mayor a 500 dólares"])
def test_an_amount_below_the_threshold_does_not_keep_an_escalation(amount):
    text = f"Como el monto {amount}, tu reembolso está aprobado. Creé el ticket TCK-1 a logística."
    assert decision_in(text) == PRO


def test_the_threshold_or_a_warranty_claim_is_still_an_escalation_with_support_around():
    threshold = (
        "Como supera los $500, escalé tu reembolso con el ticket TCK-1 a un supervisor; "
        "soporte técnico te ayudará."
    )
    warranty = "Registré el reclamo de garantía TCK-2 y el equipo técnico revisará el equipo."
    pickup = "Escalé tu caso como reclamo de garantía; el equipo de logística retirará el equipo."
    assert decision_in(threshold) == decision_in(warranty) == decision_in(pickup) == ESC


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Tu reembolso está aprobado. Creé el ticket TCK-1 para que logística coordine "
            "la devolución física.",
            PRO,
        ),
        (
            "No puedo procesar el reembolso de una licencia. Escalé tu caso para que te "
            "ayuden con la activación.",
            NO,
        ),
        (
            "Escalé el atraso de tu pedido a un supervisor; aún no es posible procesar "
            "el reembolso.",
            NO,
        ),
        ("He creado el ticket TCK-1 para que te ayuden con la activación de tu licencia.", None),
        ("Un supervisor te contactará pronto respecto al ticket TCK-1.", None),
        (
            "Como no supera los $500, tu reembolso está aprobado. Creé el ticket TCK-1 para "
            "que logística coordine la devolución física.",
            PRO,
        ),
        ("Creo que el ticket TCK-1 ya tiene toda la información.", None),
    ],
)
def test_a_ticket_for_another_matter_keeps_the_refund_decision(text, expected):
    """D-009: logistics, activation, a delay or technical support are not the refund."""
    assert decision_in(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Creé el ticket TCK-1 para que te confirmen el tiempo de acreditación del reembolso.",
            None,
        ),
        ("Escalé tu caso a un supervisor por la demora; buscará acelerar el envío.", None),
        (
            "Escalé tu caso a un supervisor por la demora; evaluará si es posible una "
            "excepción para reembolsarte.",
            ESC,
        ),
        ("Escalé tu caso por la demora: un supervisor revisará tu solicitud de reembolso.", ESC),
        (
            "El reembolso no procede y ningún supervisor podrá autorizar el reembolso; creé "
            "un ticket para la activación.",
            NO,
        ),
        ("La política no contempla excepciones; escalé tu caso por la demora del envío.", None),
    ],
)
def test_an_escalation_for_another_matter_counts_only_when_tied_to_the_refund(text, expected):
    """Second validation sample (D-010): the time a refund takes and a delay are other matters."""
    assert decision_in(text) == expected


def test_recasting_the_request_while_escalating_leaves_the_refund_open():
    text = (
        "No se trata de un reembolso por arrepentimiento, sino de una posible falla; "
        "voy a escalar tu caso a un supervisor."
    )
    assert decision_in(text) is UNRESOLVED
    recast_only = "No se trata de un reembolso por arrepentimiento, sino de otra cosa."
    assert decision_in(recast_only) is None


def test_approval_and_denial_without_escalation_is_not_guessed():
    text = "Tu reembolso fue aprobado. Normalmente estos productos no son reembolsables."
    assert decision_in(text) is UNRESOLVED


def conversation(*agent_texts):
    events = [event(1, "user_message", text="hola")]
    events += [event(i, "agent_message", text=t) for i, t in enumerate(agent_texts, start=2)]
    return trace(events=events)


@pytest.mark.parametrize("path", LABELLED)
def test_the_communicated_decision_of_every_recorded_conversation(path):
    """D-002: the latest message that states a decision, as labelled by hand."""
    stated = [label for _, label in sorted(LABELLED[path].items()) if label is not None]
    assert communicated_decision(load(path)) == (stated[-1] if stated else None)


def test_later_messages_without_a_decision_do_not_replace_it():
    assert (
        communicated_decision(conversation("El reembolso procede.", "¡Que tengas buen día!")) == PRO
    )


def test_when_the_agent_changes_its_mind_the_last_decision_counts():
    talk = conversation("El reembolso procede.", "Corrijo: el reembolso no procede.")
    assert communicated_decision(talk) == NO


def test_a_follow_up_about_an_existing_ticket_keeps_the_earlier_decision():
    talk = conversation(
        "Lamentablemente, el reembolso no procede mientras el pedido no se entregue.",
        "Un supervisor se contactará contigo pronto respecto al ticket TCK-1.",
    )
    assert communicated_decision(talk) == NO


def test_an_unresolved_last_decision_is_not_skipped():
    talk = conversation(
        "El reembolso procede.", "Tu reembolso fue aprobado, el reembolso no procede."
    )
    assert communicated_decision(talk) is UNRESOLVED
    assert communicated_decision(conversation("Hola", "¿En qué te ayudo?")) is None
