from fractions import Fraction

import pytest

from agentproof.schema import scenario_id_for
from agentproof.store import Store
from experiments.analysis.detection import detection
from tests.factories import event, manifest, trace, verdict

APPROVED = "Tu reembolso de $89.90 fue aprobado."
DENIED = "Lo siento, el reembolso no procede."
AMBIGUOUS = "Tu reembolso fue aprobado, aunque el reembolso no procede."
REFERENCE, CANDIDATE = "baseline-a-20261016-120000", "d4-20261016-130000"
CONTROL = "baseline-b-20261016-140000"
EXPOSED, UNEXPOSED = ["lookup_order", "get_refund_policy"], ["lookup_order"]
T, F = True, False

# seed: (tools, candidate replies, candidate verdicts); tc-01 expects the refund to proceed,
# so under D4 a denial is a failure. The reference approves and passes every repetition.
SCENARIOS = {
    1: (EXPOSED, [DENIED] * 5, [F] * 5),  # manifested and flagged: TP
    2: (EXPOSED, [DENIED] * 2 + [APPROVED] * 3, [T] * 5),  # manifested at 0.4, missed: FN
    3: (UNEXPOSED, [APPROVED] * 5, [F] * 5),  # flagged, not exposed: FP
    4: (EXPOSED, [APPROVED] * 5, [F] * 5),  # flagged, exposed but not worse: FP
    5: (UNEXPOSED, [APPROVED] * 5, [T] * 5),  # TN
    6: (EXPOSED, [APPROVED] * 5, [T, T, T, F, F]),  # weak signal only: TN
}


def sc(n):
    return scenario_id_for(f"tr-5eed{n:08d}")


def repetitions(store, run_id, n, replies, verdicts, termination="user_ended"):
    for repetition, (text, passed) in enumerate(zip(replies, verdicts, strict=True), start=1):
        trace_id = f"tr-{run_id[:2]}{n:04d}{repetition:06d}"
        store.save_run_trace(
            trace(
                "run",
                trace_id=trace_id,
                events=[
                    event(1, "user_message", text="hola"),
                    event(2, "agent_message", text=text),
                ],
                termination=termination,
                condition=run_id.rsplit("-", 2)[0],
                run_id=run_id,
                scenario_id=sc(n),
                repetition=repetition,
            )
        )
        if passed is not None:
            store.save_verdict(
                verdict([passed], trace_id=trace_id, run_id=run_id, scenario_id=sc(n))
            )


def populated(tmp_path, scenarios=SCENARIOS):
    store = Store(tmp_path)
    for run_id in (REFERENCE, CANDIDATE, CONTROL):
        condition = run_id.rsplit("-", 2)[0]
        store.create_run(manifest(run_id=run_id, condition=condition, repetitions=5))
    for n, (tools, replies, verdicts) in scenarios.items():
        calls = [event(i, "tool_call", tool=t) for i, t in enumerate(tools, start=2)]
        seed_events = [event(1, "user_message", text="hola"), *calls]
        store.save_seed(trace(trace_id=f"tr-5eed{n:08d}", card_id="tc-01", events=seed_events))
        repetitions(store, REFERENCE, n, [APPROVED] * 5, [T] * 5)
        repetitions(store, CANDIDATE, n, replies, verdicts)
        repetitions(store, CONTROL, n, [APPROVED] * 5, [F] * 5 if n == 1 else [T] * 5)
    return store


def test_the_four_cells_partition_every_scenario(tmp_path):
    result = detection(populated(tmp_path), REFERENCE, CANDIDATE, "d4")
    assert (result.true_positives, result.false_negatives) == ([sc(1)], [sc(2)])
    assert (result.false_positives, result.true_negatives) == ([sc(3), sc(4)], [sc(5), sc(6)])
    assert (result.tpr, result.fpr) == (Fraction(1, 2), Fraction(1, 2))
    assert result.deviations == []


def test_false_positives_are_broken_down_by_exposure_and_weak_signals_listed(tmp_path):
    result = detection(populated(tmp_path), REFERENCE, CANDIDATE, "d4")
    assert result.false_positives_unexposed == [sc(3)]
    assert result.false_positives_exposed == [sc(4)]
    assert result.weak_signals == [sc(6)]


def test_no_metric_while_cases_wait_for_manual_annotation(tmp_path):
    scenarios = SCENARIOS | {1: (EXPOSED, [AMBIGUOUS] + [DENIED] * 4, [F] * 5)}
    with pytest.raises(ValueError, match="1 scenario"):
        detection(populated(tmp_path, scenarios), REFERENCE, CANDIDATE, "d4")


def test_a_scenario_without_valid_repetitions_is_a_listed_deviation(tmp_path):
    store = populated(tmp_path)
    repetitions(store, REFERENCE, 5, [APPROVED] * 5, [None] * 5, termination="simulator_error")
    for trace_id in [t.trace_id for t in store.run_traces(REFERENCE) if t.scenario_id == sc(5)]:
        (store.runs_dir / REFERENCE / "verdicts" / f"{trace_id}.json").unlink(missing_ok=True)
    result = detection(store, REFERENCE, CANDIDATE, "d4")
    assert result.deviations == [sc(5)] and result.true_negatives == [sc(6)]


def test_d3_has_no_exposed_set_and_no_confusion_matrix(tmp_path):
    with pytest.raises(ValueError, match="effect size"):
        detection(populated(tmp_path), REFERENCE, CANDIDATE, "d3")
