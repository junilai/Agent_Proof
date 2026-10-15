from dataclasses import asdict

from agentproof.models import TARGET_BASELINE_MODEL, TARGET_DOWNGRADED_MODEL
from casestudy.domain.catalog import ORDERS_BY_ID
from casestudy.domain.mutations import (
    BASELINE,
    CORRUPT_POLICY,
    FAMILY_A,
    FAMILY_B,
    MUTATIONS,
    Mutation,
)
from casestudy.domain.policy import TRUE_POLICY, decide
from experiments.cards import cards_with_decision


def changed_fields(mutation):
    base, other = asdict(BASELINE), asdict(mutation)
    return {key for key in base if key not in ("name", "family") and base[key] != other[key]}


def test_baseline_changes_nothing():
    assert BASELINE == Mutation("baseline", None)
    assert BASELINE.policy == TRUE_POLICY and BASELINE.model == TARGET_BASELINE_MODEL
    assert changed_fields(BASELINE) == set()


def test_each_mutation_changes_exactly_what_it_declares():
    assert {name: changed_fields(m) for name, m in MUTATIONS.items() if name != "baseline"} == {
        "d1": {"removed_tools"},
        "d2": {"omit_policy_check"},
        "d3": {"model"},
        "d4": {"policy"},
        "d5": {"injected_instruction"},
        "d6": {"step_limit"},
    }
    assert MUTATIONS["d1"].removed_tools == frozenset({"lookup_order"})
    assert MUTATIONS["d3"].model == TARGET_DOWNGRADED_MODEL
    assert MUTATIONS["d6"].step_limit == 2


def test_families_follow_the_planning():
    assert set(FAMILY_A) == {"d1", "d4", "d6"} and set(FAMILY_B) == {"d2", "d3", "d5"}
    assert all(MUTATIONS[name].family == "A" for name in FAMILY_A)
    assert all(MUTATIONS[name].family == "B" for name in FAMILY_B)


def test_the_corrupt_policy_changes_exactly_seven_decisions():
    changed = {
        card.card_id
        for card in cards_with_decision()
        if decide(ORDERS_BY_ID[card.orders[0]], card.reason, TRUE_POLICY)
        != decide(ORDERS_BY_ID[card.orders[0]], card.reason, CORRUPT_POLICY)
    }
    assert changed == {"tc-06", "tc-07", "tc-08", "tc-11", "tc-12", "tc-13", "tc-15"}
