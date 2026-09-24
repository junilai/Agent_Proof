from collections import Counter

from casestudy.domain.catalog import ORDERS_BY_ID
from casestudy.domain.policy import Decision, decide
from experiments.cards import CARDS, CARDS_BY_ID, cards_expecting, cards_with_decision

DECISIONS = {
    "procede": Decision.APPROVED,
    "no_procede": Decision.DENIED,
    "escalamiento": Decision.ESCALATED,
}


def test_twenty_cards_with_unique_ids():
    assert len(CARDS) == 20 and len(CARDS_BY_ID) == 20


def test_every_order_exists_in_the_domain():
    assert all(order in ORDERS_BY_ID for card in CARDS for order in card.orders)


def test_the_expected_outcome_is_what_the_policy_decides():
    for card in cards_with_decision():
        (order_id,) = card.orders
        assert card.reason is not None
        assert decide(ORDERS_BY_ID[order_id], card.reason) == DECISIONS[card.expected], card.card_id


def test_only_cards_with_a_decision_carry_a_reason():
    assert all(card.reason is None for card in CARDS if card.expected == "sin_decision")


def test_the_coverage_matrix_is_balanced():
    assert Counter(card.expected for card in CARDS) == {
        "procede": 5,
        "no_procede": 5,
        "escalamiento": 5,
        "sin_decision": 5,
    }
    assert min(Counter(card.tone for card in CARDS).values()) >= 5


def test_the_operators_fixed_before_induction_have_exposed_and_control_sets():
    decisions = cards_with_decision()  # D2: prompt recortado
    denied = cards_expecting("no_procede")  # D5: aprobar todo reembolso
    assert len(decisions) == 15 and len(CARDS) - len(decisions) == 5
    assert len(denied) == 5 and len(CARDS) - len(denied) == 15


def test_cards_without_orders_control_the_tool_operators():
    assert len([card for card in CARDS if not card.orders]) >= 3


def test_every_card_describes_a_situation_and_names_its_orders():
    for card in CARDS:
        assert len(card.text) >= 60, card.card_id
        assert all(order in card.text for order in card.orders), card.card_id
