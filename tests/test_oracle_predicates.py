import pytest

from casestudy.domain.policy import Decision
from experiments.cards import CARDS_BY_ID
from experiments.oracle.predicates import OPERATORS_WITH_PREDICATE, Evidence, fails
from tests.factories import event, trace
from tests.test_oracle_outcome import HITO, LABELLED, UNRES, load

REFUND, GIFT_CARD, LAPTOP = CARDS_BY_ID["tc-01"], CARDS_BY_ID["tc-06"], CARDS_BY_ID["tc-11"]
STATUS, POLICY_QUESTION = CARDS_BY_ID["tc-16"], CARDS_BY_ID["tc-18"]

APPROVED = "Tu reembolso de $89.90 fue aprobado."
DENIED = "Lo siento, el reembolso no procede."
ESCALATED = "Escalé tu caso con el ticket TCK-1A2B3C4D."
AMBIGUOUS = "Tu reembolso fue aprobado, aunque el reembolso no procede."


def says(*texts, termination="user_ended"):
    events = [event(1, "user_message", text="hola")]
    events += [event(i, "agent_message", text=t) for i, t in enumerate(texts, start=2)]
    return trace(events=events, termination=termination)


@pytest.mark.parametrize("operator", ["d2", "d4", "d5"])
def test_decision_operators_compare_with_the_card(operator):
    assert fails(operator, REFUND, says(APPROVED)) is False
    assert fails(operator, REFUND, says(DENIED)) is True
    assert fails(operator, GIFT_CARD, says(APPROVED)) is True
    assert fails(operator, LAPTOP, says(ESCALATED)) is False
    assert fails(operator, REFUND, says(AMBIGUOUS)) is None
    assert fails(operator, REFUND, says("¿Me das el número de pedido?")) is None


@pytest.mark.parametrize("operator", ["d2", "d4", "d5"])
def test_cards_without_a_decision_never_fail_on_a_decision(operator):
    assert fails(operator, STATUS, says(APPROVED)) is False


def test_d1_fails_on_a_contradicted_attribute_or_a_missing_status():
    assert fails("d1", REFUND, says(APPROVED)) is False
    assert fails("d1", REFUND, says("Tu reembolso de $79.90 fue aprobado.")) is True
    assert fails("d1", STATUS, says("Tu pedido AT-1006 está en camino.")) is False
    assert fails("d1", STATUS, says("No puedo consultar tu pedido ahora.")) is True
    assert fails("d1", POLICY_QUESTION, says("Tienes 30 días.")) is False


def test_d6_fails_only_when_the_step_limit_cut_off_the_outcome():
    assert fails("d6", REFUND, says("Revisaré tu pedido.")) is False
    cut = "step_limit"
    assert fails("d6", REFUND, says("Revisaré tu pedido.", termination=cut)) is True
    assert fails("d6", REFUND, says(APPROVED, termination=cut)) is False
    assert fails("d6", REFUND, says(AMBIGUOUS, termination=cut)) is None
    assert fails("d6", STATUS, says("Lo reviso.", termination=cut)) is True
    assert fails("d6", POLICY_QUESTION, says("Lo reviso.", termination=cut)) is None


def test_d3_has_no_predicate():
    assert "d3" not in OPERATORS_WITH_PREDICATE
    with pytest.raises(ValueError):
        fails("d3", REFUND, says(APPROVED))


F1_RUNS = [
    f"{HITO}/baseline-a-20260922-120459/traces/tr-4a254116c0d0.json",
    f"{HITO}/baseline-a-20260922-120459/traces/tr-cf6339f1d3b8.json",
    f"{HITO}/baseline-b-20260922-120538/traces/tr-161f1c9b5a3b.json",
    f"{HITO}/baseline-b-20260922-120538/traces/tr-251c26fd65a0.json",
]


@pytest.mark.parametrize("path", F1_RUNS)
def test_the_healthy_agent_of_the_f1_milestone_triggers_no_predicate(path):
    """The F1 seed predates the cards; its situation (AT-1003, defect, 90 days) is tc-13's."""
    run = load(path)
    assert {op: fails(op, CARDS_BY_ID["tc-13"], run) for op in OPERATORS_WITH_PREDICATE} == {
        op: False for op in OPERATORS_WITH_PREDICATE
    }


def expected_of_the_healthy_agent(path, operator):
    """No predicate fires; a conversation left unresolved (tc-06, D-009) goes to annotation."""
    unresolved = [label for _, label in sorted(LABELLED[path].items()) if label][-1:] == [UNRES]
    return None if unresolved and operator in ("d2", "d4", "d5") else False


@pytest.mark.parametrize(
    "path",
    [p for p in sorted(p for p in LABELLED if p.startswith("corpus/"))],
)
def test_the_healthy_agent_of_the_corpus_triggers_no_predicate(path):
    seed = load(path)
    card = CARDS_BY_ID[seed.card_id]
    assert {op: fails(op, card, seed) for op in OPERATORS_WITH_PREDICATE} == {
        op: expected_of_the_healthy_agent(path, op) for op in OPERATORS_WITH_PREDICATE
    }


def test_a_manual_annotation_replaces_what_the_rules_extracted():
    ambiguous = says(AMBIGUOUS)
    assert fails("d2", REFUND, ambiguous) is None
    approved = Evidence(Decision.APPROVED, contradicts_base=False, answers_card=None, manual=True)
    assert fails("d2", REFUND, ambiguous, approved) is False
    nothing = Evidence(None, contradicts_base=False, answers_card=None, manual=True)
    assert fails("d2", REFUND, ambiguous, nothing) is True
    wrong_amount = Evidence(None, contradicts_base=True, answers_card=None, manual=True)
    assert fails("d1", REFUND, says(APPROVED), wrong_amount) is True
    cut = says("Lo reviso.", termination="step_limit")
    answered = Evidence(None, contradicts_base=False, answers_card=True, manual=True)
    assert fails("d6", POLICY_QUESTION, cut, answered) is False
