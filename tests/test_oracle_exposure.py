import pytest

from agentproof.schema import scenario_id_for
from casestudy.domain.mutations import MUTATIONS
from experiments.cards import CARDS_BY_ID
from experiments.oracle.exposure import is_exposed, seed_of
from tests.factories import event, trace


def seed(*tools):
    events = [event(1, "user_message", text="hola")]
    events += [event(i, "tool_call", tool=tool) for i, tool in enumerate(tools, start=2)]
    return trace(events=events)


def test_the_seed_is_read_back_from_the_scenario_identifier():
    assert seed_of(scenario_id_for("tr-49f9d41b2bc6")) == "tr-49f9d41b2bc6"
    with pytest.raises(ValueError):
        seed_of("tr-49f9d41b2bc6")


def test_trace_operators_depend_only_on_the_tools_the_seed_called():
    card = CARDS_BY_ID["tc-16"]
    lookup = seed("lookup_order")
    full = seed("lookup_order", "get_refund_policy", "create_ticket")
    assert is_exposed("d1", card, lookup) and not is_exposed("d1", card, seed())
    assert is_exposed("d4", card, full) and not is_exposed("d4", card, lookup)
    assert is_exposed("d6", card, full) and not is_exposed("d6", card, lookup)


def test_card_operators_depend_only_on_the_card():
    nothing = seed()
    assert is_exposed("d2", CARDS_BY_ID["tc-01"], nothing)
    assert not is_exposed("d2", CARDS_BY_ID["tc-16"], nothing)
    assert is_exposed("d5", CARDS_BY_ID["tc-06"], nothing)
    assert not is_exposed("d5", CARDS_BY_ID["tc-01"], nothing)
    assert not is_exposed("d5", CARDS_BY_ID["tc-11"], nothing)


def test_d3_defines_no_exposed_set_and_every_operator_is_known():
    assert is_exposed("d3", CARDS_BY_ID["tc-01"], seed()) is None
    for name in set(MUTATIONS) - {"baseline"}:
        is_exposed(name, CARDS_BY_ID["tc-01"], seed())
    with pytest.raises(ValueError):
        is_exposed("d7", CARDS_BY_ID["tc-01"], seed())
