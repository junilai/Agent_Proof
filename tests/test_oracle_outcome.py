from pathlib import Path

import pytest

from agentproof.schema import Trace
from casestudy.domain.policy import Decision
from experiments.oracle.outcome import UNRESOLVED, communicated_decision, decision_in
from tests.factories import event, trace

ROOT = Path(__file__).resolve().parents[1]
HITO = "evidence/f1-hito/results/runs"
PRO, NO, ESC = Decision.APPROVED, Decision.DENIED, Decision.ESCALATED

# Each agent message recorded so far, labelled by hand once: the decision it states,
# or None when it states none. Follow-up answers that restate the escalated case
# (steps 9 of the F1 runs) are labelled as an escalation.
LABELLED = {
    "corpus/seeds/tr-49f9d41b2bc6.json": {2: None, 4: None, 8: PRO, 10: PRO},
    "corpus/seeds/tr-a450dfb016b9.json": {2: None, 4: None, 8: ESC, 10: ESC, 12: ESC, 14: None},
    "corpus/seeds/tr-b5c4babdd36b.json": {2: None, 4: None, 6: None, 8: None, 10: None, 12: None},
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
    assert sum(len(labels) for labels in LABELLED.values()) == 37


@pytest.mark.parametrize("path", LABELLED)
def test_no_recorded_message_is_classified_the_wrong_way(path):
    """A message may be missed (None) but never given a decision it does not state."""
    for step, text in agent_messages(path).items():
        label, found = LABELLED[path][step], decision_in(text)
        assert found == label or (label is not None and found is None), (step, found)


def test_misses_are_few():
    misses = [
        (path, step)
        for path, labels in LABELLED.items()
        for step, text in agent_messages(path).items()
        if labels[step] is not None and decision_in(text) is None
    ]
    assert len(misses) <= 2, misses


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
    ],
)
def test_negations_purposes_questions_and_conditionals_state_no_decision(text):
    assert decision_in(text) is None


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


def test_an_unresolved_last_decision_is_not_skipped():
    talk = conversation(
        "El reembolso procede.", "Tu reembolso fue aprobado, el reembolso no procede."
    )
    assert communicated_decision(talk) is UNRESOLVED
    assert communicated_decision(conversation("Hola", "¿En qué te ayudo?")) is None
