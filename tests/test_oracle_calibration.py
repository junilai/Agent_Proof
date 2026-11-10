"""Calibration of the oracle against real replies of degraded agents (D-005).

Until F3 the only recorded replies came from the healthy agent; these show how a
degraded agent sounds when it is wrong. The rules must never classify a reply the
wrong way: a case may be left to manual annotation, never inverted.
"""

import json
from pathlib import Path

import pytest

from casestudy.domain.catalog import ORDERS_BY_ID
from experiments.cards import CARDS_BY_ID
from experiments.oracle.attributes import attribute_discrepancies
from experiments.oracle.outcome import UNRESOLVED, communicated_decision
from experiments.oracle.predicates import fails
from tests.factories import event, trace

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))["replies"]


SDK = load("oracle_replies.json")
LANGGRAPH = load("oracle_replies_langgraph.json")
REPLIES = SDK + LANGGRAPH


def as_trace(reply):
    events = [event(1, "user_message", text=reply["user"])]
    events += [
        event(i, e["kind"], text=e["text"], tool=e["tool"])
        for i, e in enumerate(reply["events"], start=2)
    ]
    cut = reply["stop_reason"] == "step_limit"
    return trace(events=events, termination="step_limit" if cut else "user_ended")


def name(reply):
    return f"{reply['batch']}-{reply['variant']}-{reply['card_id']}"


def test_the_fixture_covers_each_operator_and_both_batches():
    assert {r["variant"] for r in SDK} == {"d1", "d2", "d4", "d5", "d6"}
    assert {r["batch"] for r in SDK} == {"ajuste", "reserva"}
    assert len(SDK) == 28


def test_the_langgraph_fixture_covers_the_e4_conditions_in_every_situation():
    """E4 runs the baseline and family A; every situation of D-005 under each of them.

    The labels are the reconciled ones of a blind double annotation (D-005, LangGraph addendum).
    """
    situations = {(r["card_id"], r["user"]) for r in SDK}
    assert {r["batch"] for r in LANGGRAPH} == {"langgraph"}
    for variant in ("baseline", "d1", "d4", "d6"):
        assert {
            (r["card_id"], r["user"]) for r in LANGGRAPH if r["variant"] == variant
        } == situations
    assert len(LANGGRAPH) == 4 * len(situations)


@pytest.mark.parametrize("reply", REPLIES, ids=name)
def test_no_reply_is_classified_the_wrong_way(reply):
    card, run, label = CARDS_BY_ID[reply["card_id"]], as_trace(reply), reply["label"]
    found = communicated_decision(run)
    # A decision the rules do not read goes to manual annotation: never an error in the
    # LangGraph replies. The SDK ones, read when the rules were written, must all be read.
    to_annotate = found is UNRESOLVED or (found is None and reply["batch"] == "langgraph")
    assert to_annotate or (found.value if found else None) == label["decision"]
    order = ORDERS_BY_ID[card.orders[0]]
    assert bool(attribute_discrepancies(run, order)) == label["discrepancies"]
    # The baseline has no predicate of its own: each operator's is read on its traces.
    expected = label["fails_as"] if "fails_as" in label else {reply["variant"]: label["fails"]}
    for operator, value in expected.items():
        assert fails(operator, card, run) in (value, None)


def test_every_sdk_reply_is_resolved_by_the_rules():
    unresolved = [
        name(r) for r in SDK if fails(r["variant"], CARDS_BY_ID[r["card_id"]], as_trace(r)) is None
    ]
    assert unresolved == []
