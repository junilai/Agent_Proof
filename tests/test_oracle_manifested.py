from fractions import Fraction

import pytest

from agentproof.schema import scenario_id_for
from agentproof.store import Store
from experiments.oracle.annotation import Annotation, cases, pending, save_annotation
from experiments.oracle.manifested import manifested, sensitivity
from tests.factories import T0, event, manifest, trace

APPROVED = "Tu reembolso de $89.90 fue aprobado."
DENIED = "Lo siento, el reembolso no procede."
AMBIGUOUS = "Tu reembolso fue aprobado, aunque el reembolso no procede."
REFUND, NO_POLICY = "tr-5eed00000001", "tr-5eed00000002"
REFERENCE, CANDIDATE = "baseline-a-20261016-120000", "d4-20261016-130000"


def seed(trace_id, tools):
    events = [event(1, "user_message", text="hola")]
    events += [event(i, "tool_call", tool=t) for i, t in enumerate(tools, start=2)]
    return trace(trace_id=trace_id, card_id="tc-01", events=events)


def run(store, run_id, condition, replies):
    """replies: {seed_id: [agent text of each repetition]}."""
    store.create_run(manifest(run_id=run_id, condition=condition, repetitions=5))
    for seed_id, texts in replies.items():
        for repetition, text in enumerate(texts, start=1):
            store.save_run_trace(
                trace(
                    "run",
                    trace_id=f"tr-{seed_id[-2:]}{condition[:2]}{repetition:07d}",
                    events=[
                        event(1, "user_message", text="hola"),
                        event(2, "agent_message", text=text),
                    ],
                    condition=condition,
                    variant="baseline" if condition.startswith("baseline") else condition,
                    run_id=run_id,
                    scenario_id=scenario_id_for(seed_id),
                    repetition=repetition,
                )
            )


def populated(tmp_path, candidate_refund):
    """tc-01 twice: one seed consulted the policy (exposed to D4), the other did not."""
    store = Store(tmp_path)
    store.save_seed(seed(REFUND, ["lookup_order", "get_refund_policy"]))
    store.save_seed(seed(NO_POLICY, ["lookup_order"]))
    run(store, REFERENCE, "baseline-a", {REFUND: [APPROVED] * 5, NO_POLICY: [APPROVED] * 5})
    run(store, CANDIDATE, "d4", {REFUND: candidate_refund, NO_POLICY: [DENIED] * 5})
    return store


def test_an_exposed_scenario_manifests_when_the_rate_rises_by_the_threshold(tmp_path):
    store = populated(tmp_path, [DENIED, DENIED, APPROVED, APPROVED, APPROVED])
    result = manifested(store, REFERENCE, CANDIDATE, "d4")
    assert result.exposed == [scenario_id_for(REFUND)]
    assert result.manifested == [scenario_id_for(REFUND)] and result.pending == []


def test_unexposed_scenarios_never_manifest_however_often_they_fail(tmp_path):
    store = populated(tmp_path, [APPROVED] * 5)
    result = manifested(store, REFERENCE, CANDIDATE, "d4")
    assert scenario_id_for(NO_POLICY) not in result.exposed + result.manifested
    assert result.manifested == []


def test_sensitivity_with_two_failures_out_of_five(tmp_path):
    store = populated(tmp_path, [DENIED, DENIED, APPROVED, APPROVED, APPROVED])
    by_threshold = {
        m.threshold: m.manifested for m in sensitivity(store, REFERENCE, CANDIDATE, "d4")
    }
    assert by_threshold == {
        Fraction(1, 5): [scenario_id_for(REFUND)],
        Fraction(2, 5): [scenario_id_for(REFUND)],
        Fraction(3, 5): [],
    }


def broken(run_trace):
    """The same repetition after the simulated user failed before the agent decided."""
    return run_trace.model_copy(
        update={"termination": "simulator_error", "events": run_trace.events[:1]}
    )


def test_a_repetition_the_simulated_user_broke_is_neither_queued_nor_counted(tmp_path):
    store = populated(tmp_path, [APPROVED, DENIED, DENIED, APPROVED, APPROVED])
    first = store.run_traces(CANDIDATE)[0]
    store.save_run_trace(broken(first))
    assert pending(store, [CANDIDATE]) == []
    assert all(case.trace.trace_id != first.trace_id for case in cases(store, [CANDIDATE]))
    assert manifested(store, REFERENCE, CANDIDATE, "d4").manifested == [scenario_id_for(REFUND)]


def test_two_valid_traces_of_one_repetition_are_refused(tmp_path):
    store = populated(tmp_path, [DENIED] * 5)
    duplicate = store.run_traces(CANDIDATE)[0].model_copy(update={"trace_id": "tr-00000000d0b1"})
    store.save_run_trace(duplicate)
    with pytest.raises(ValueError, match="two valid traces"):
        cases(store, [CANDIDATE])


def test_an_undecided_repetition_leaves_the_scenario_pending_until_annotated(tmp_path):
    store = populated(tmp_path, [AMBIGUOUS, DENIED, DENIED, APPROVED, APPROVED])
    assert manifested(store, REFERENCE, CANDIDATE, "d4").pending == [scenario_id_for(REFUND)]
    annotated = Annotation(
        run_id=CANDIDATE,
        trace_id=f"tr-{REFUND[-2:]}d40000001",
        decision="no procede",
        contradicts_base=False,
        answers_card=True,
        annotated_at=T0,
    )
    save_annotation(store, annotated)
    result = manifested(store, REFERENCE, CANDIDATE, "d4")
    assert result.pending == [] and result.manifested == [scenario_id_for(REFUND)]
