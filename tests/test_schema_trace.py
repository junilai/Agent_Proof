from pathlib import Path

import pytest
from pydantic import ValidationError

from agentproof.schema import Trace, Usage, new_trace_id
from tests.factories import RUN_FIELDS, event, trace


def test_seed_trace_needs_no_run_fields():
    assert trace().kind == "seed"


def test_run_trace_requires_every_run_field():
    assert trace(kind="run").repetition == 1
    for missing in RUN_FIELDS:
        with pytest.raises(ValidationError):
            trace(kind="run", **{missing: None})


def test_seed_trace_cannot_carry_run_fields():
    with pytest.raises(ValidationError):
        trace(run_id="baseline-a-20261001-120000")


def test_json_round_trip_keeps_spanish_text():
    original = trace()
    assert Trace.model_validate_json(original.model_dump_json()) == original
    assert "¿En qué le ayudo?" in original.model_dump_json()


def test_final_reply_is_the_agent_text_after_the_last_user_message():
    events = [
        event(1, "user_message", text="Quiero un reembolso"),
        event(2, "agent_message", text="Reviso su pedido."),
        event(3, "user_message", text="Es el AT-1001"),
        event(4, "tool_call", tool="lookup_order", arguments={"order_id": "AT-1001"}, result={}),
        event(5, "agent_message", text="Su reembolso procede."),
        event(6, "agent_message", text="Se acreditará en 5 días."),
    ]
    assert trace(events=events).final_reply() == "Su reembolso procede.\nSe acreditará en 5 días."


def test_final_reply_is_empty_when_the_agent_did_not_answer():
    events = [event(1, "user_message", text="Hola"), event(2, "error", text="RuntimeError: caída")]
    assert trace(events=events, termination="agent_error").final_reply() == ""


def test_usage_adds_tokens_and_known_costs():
    first = Usage(input_tokens=10, output_tokens=5, cost_usd=0.25)
    assert first + Usage(input_tokens=1, output_tokens=2) == Usage(
        input_tokens=11, output_tokens=7, cost_usd=0.25
    )
    assert (Usage() + Usage()).cost_usd is None


def test_new_trace_id_format():
    first, second = new_trace_id(), new_trace_id()
    assert first.startswith("tr-") and len(first) == 15 and first != second


def test_a_seed_trace_remembers_the_card_it_was_recorded_with():
    assert trace(card_id="tc-01").card_id == "tc-01"
    assert trace().card_id is None


def test_traces_saved_before_the_card_field_still_load():
    saved = Path("evidence/f1-hito/corpus/seeds/tr-0a7510c36f69.json").read_text(encoding="utf-8")
    assert Trace.model_validate_json(saved).card_id is None
