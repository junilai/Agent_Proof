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

FIXTURE = Path(__file__).parent / "fixtures" / "oracle_replies.json"
REPLIES = json.loads(FIXTURE.read_text(encoding="utf-8"))["replies"]


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
    assert {r["variant"] for r in REPLIES} == {"d1", "d2", "d4", "d5", "d6"}
    assert {r["batch"] for r in REPLIES} == {"ajuste", "reserva"}
    assert len(REPLIES) == 28


@pytest.mark.parametrize("reply", REPLIES, ids=name)
def test_no_reply_is_classified_the_wrong_way(reply):
    card, run, label = CARDS_BY_ID[reply["card_id"]], as_trace(reply), reply["label"]
    found = communicated_decision(run)
    assert found is UNRESOLVED or (found.value if found else None) == label["decision"]
    order = ORDERS_BY_ID[card.orders[0]]
    assert bool(attribute_discrepancies(run, order)) == label["discrepancies"]
    assert fails(reply["variant"], card, run) in (label["fails"], None)


def test_every_reply_is_resolved_by_the_rules():
    unresolved = [
        name(r)
        for r in REPLIES
        if fails(r["variant"], CARDS_BY_ID[r["card_id"]], as_trace(r)) is None
    ]
    assert unresolved == []
