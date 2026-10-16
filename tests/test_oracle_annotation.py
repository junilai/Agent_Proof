from typer.testing import CliRunner

from agentproof.schema import scenario_id_for
from agentproof.store import Store
from experiments.oracle.annotation import (
    Annotation,
    app,
    load_annotations,
    operators_for,
    pending,
    present,
    save_annotation,
)
from tests.factories import T0, event, manifest, trace

SEED_ID = "tr-5eed00000001"
AMBIGUOUS = "Tu reembolso fue aprobado, aunque el reembolso no procede."
APPROVED = "Tu reembolso de $89.90 fue aprobado."


def run_trace(trace_id, condition, text, repetition):
    events = [event(1, "user_message", text="hola"), event(2, "agent_message", text=text)]
    return trace(
        "run",
        events=events,
        trace_id=trace_id,
        condition=condition,
        variant="baseline" if condition.startswith("baseline") else condition,
        run_id=f"{condition}-20261016-120000",
        scenario_id=scenario_id_for(SEED_ID),
        repetition=repetition,
    )


def populated(tmp_path):
    """A refund card (tc-01) whose seed consulted the order and the policy."""
    store = Store(tmp_path)
    tools = [
        event(2, "tool_call", tool="lookup_order"),
        event(3, "tool_call", tool="get_refund_policy"),
    ]
    store.save_seed(
        trace(
            trace_id=SEED_ID,
            card_id="tc-01",
            events=[event(1, "user_message", text="hola"), *tools],
        )
    )
    runs = {
        "baseline-a": [("tr-a00000000001", AMBIGUOUS), ("tr-a00000000002", APPROVED)],
        "baseline-b": [("tr-b00000000001", AMBIGUOUS)],
        "d5": [("tr-d50000000001", AMBIGUOUS)],
    }
    for condition, traces in runs.items():
        store.create_run(manifest(run_id=f"{condition}-20261016-120000", condition=condition))
        for repetition, (trace_id, text) in enumerate(traces, start=1):
            store.save_run_trace(run_trace(trace_id, condition, text, repetition))
    return store


def annotation(trace_id="tr-a00000000001", decision="procede"):
    return Annotation(
        run_id="baseline-a-20261016-120000",
        trace_id=trace_id,
        decision=decision,
        contradicts_base=False,
        answers_card=True,
        annotated_at=T0,
    )


def test_each_condition_is_judged_with_its_own_predicates():
    assert operators_for("baseline-a") == ("d1", "d2", "d4", "d5", "d6")
    assert operators_for("baseline-b") == ()
    assert operators_for("d4") == ("d4",) and operators_for("d3") == ()


def test_only_exposed_cases_some_predicate_leaves_undecided_are_queued(tmp_path):
    """tc-01 is not exposed to D5 and baseline-b is judged by no predicate."""
    store = populated(tmp_path)
    queue = pending(store, store.runs())
    assert [case.trace.trace_id for case in queue] == ["tr-a00000000001"]
    assert queue[0].card.card_id == "tc-01" and queue[0].seed.trace_id == SEED_ID


def test_an_annotation_settles_the_case_and_is_stored_as_manual(tmp_path):
    store = populated(tmp_path)
    save_annotation(store, annotation())
    assert pending(store, store.runs()) == []
    stored = load_annotations(store)["tr-a00000000001"]
    assert stored.manual is True and stored.evidence().manual
    save_annotation(store, annotation(decision="no procede"))
    assert load_annotations(store)["tr-a00000000001"].decision == "no procede"


def test_the_queue_order_is_random_but_fixed(tmp_path):
    store = populated(tmp_path)
    assert pending(store, store.runs()) == pending(store, store.runs())


def test_the_annotator_never_sees_the_condition(tmp_path):
    case = pending(populated(tmp_path), ["baseline-a-20261016-120000"])[0]
    shown = present(case, 1, 1)
    assert "audífonos Sony" in shown and "AT-1001" in shown and AMBIGUOUS in shown
    for hidden in ("baseline", "d5", "20261016", "procede\n", "expected"):
        assert hidden not in shown.replace(AMBIGUOUS, "")


def test_the_command_asks_and_saves(tmp_path):
    store = populated(tmp_path)
    result = CliRunner().invoke(app, ["--data", str(tmp_path)], input="q\np\nn\ny\n")
    assert result.exit_code == 0, result.output
    saved = load_annotations(store)["tr-a00000000001"]
    assert (saved.decision, saved.contradicts_base, saved.answers_card) == ("procede", False, True)
    again = CliRunner().invoke(app, ["--data", str(tmp_path)])
    assert "No hay casos pendientes" in again.output
