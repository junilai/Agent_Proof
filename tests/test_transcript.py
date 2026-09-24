from agentproof.transcript import MODEL_MASK, render_transcript
from tests.factories import T0, event, trace

LOOKUP_RESULT = {"estado": "entregado", "dias_desde_entrega": 10}


def conversation():
    lookup = event(2, "tool_call", tool="lookup_order", arguments={"order_id": "AT-1001"})
    return [
        event(1, "user_message", text="Hola, quiero devolver mis audífonos"),
        lookup.model_copy(update={"result": LOOKUP_RESULT}),
        event(3, "agent_message", text="Su reembolso procede."),
        event(4, "error", text="RuntimeError: límite"),
    ]


def test_renders_each_event_with_its_spanish_label():
    assert render_transcript(trace(events=conversation())).splitlines() == [
        "[USUARIO] Hola, quiero devolver mis audífonos",
        '[HERRAMIENTA] lookup_order({"order_id": "AT-1001"}) -> '
        '{"dias_desde_entrega": 10, "estado": "entregado"}',
        "[AGENTE] Su reembolso procede.",
        "[ERROR] RuntimeError: límite",
    ]


def test_marks_failed_tool_calls():
    failed = event(1, "tool_call", tool="lookup_order", arguments={}, result="no", is_error=True)
    assert render_transcript(trace(events=[failed])).endswith(" (error)")


def test_never_reveals_the_run_metadata_or_the_model():
    leak = event(5, "error", text="NotFoundError: model claude-haiku-4-5-20251001 not found")
    d3 = trace(
        kind="run",
        events=[*conversation(), leak],
        variant="d3",
        condition="d3",
        run_id="d3-20261102-101500",
        agent="casestudy.editions.claude_sdk:build_options",
        models={"target": "claude-haiku-4-5-20251001"},
    )
    text = render_transcript(d3)
    secrets = ("claude-haiku-4-5-20251001", "d3-20261102", "casestudy.editions", "build_options")
    for secret in (*secrets, T0.isoformat(), "2026-10-01"):
        assert secret not in text
    assert f"NotFoundError: model {MODEL_MASK} not found" in text


def test_the_card_is_not_part_of_the_transcript():
    """The inducer and the judge read this text: neither may learn the ground truth."""
    rendered = render_transcript(trace(card_id="tc-03"))
    assert "tc-03" not in rendered
