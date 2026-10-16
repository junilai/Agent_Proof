from fractions import Fraction

from agentproof.report import Retries, compare_runs, render_comparison
from agentproof.schema import JudgeFailure
from agentproof.store import Store
from tests.factories import T0, manifest, trace, verdict

BASE, CAND = "base-20261001-120000", "cand-20261001-130000"


def fill(store, run_id, scenario_id, outcomes):
    """outcomes: True/False = judged verdict; None = trace without verdict (invalid)."""
    if run_id not in store.runs():
        store.create_run(manifest(run_id=run_id, condition=run_id.split("-")[0]))
    for rep, passed in enumerate(outcomes, start=1):
        trace_id = f"tr-{run_id[:4]}-{scenario_id}-{rep}"
        run_trace = trace(
            kind="run", trace_id=trace_id, run_id=run_id, scenario_id=scenario_id, repetition=rep
        )
        store.save_run_trace(run_trace)
        if passed is not None:
            store.save_verdict(
                verdict([passed], trace_id=trace_id, run_id=run_id, scenario_id=scenario_id)
            )


def test_an_isolated_drop_of_four_tenths_is_only_a_weak_signal(tmp_path):
    """5/5 to 3/5 gives p = 0.44: the drop is there, the evidence is not (§5.5)."""
    store = Store(tmp_path)
    fill(store, BASE, "sc-a", [True] * 5)
    fill(store, CAND, "sc-a", [True, True, True, False, False])
    comparison = compare_runs(store, BASE, CAND)
    only = comparison.comparisons[0]
    assert only.drop == Fraction(2, 5) and only.p_value == Fraction(4, 9)
    assert only.status == "señal débil" and not only.regressed
    assert comparison.weak_signals == [only] and comparison.exit_code == 0


def twenty(store, flipped, base=True, cand=False):
    """Twenty scenarios at 5/5 in both runs, except `flipped` of them go from base to cand."""
    for i in range(20):
        changed = i < flipped
        fill(store, BASE, f"sc-{i:02d}", [base if changed else True] * 5)
        fill(store, CAND, f"sc-{i:02d}", [cand if changed else True] * 5)


def test_four_joint_regressions_among_twenty_fail_the_build(tmp_path):
    store = Store(tmp_path)
    twenty(store, 4)
    comparison = compare_runs(store, BASE, CAND)
    assert [c.scenario_id for c in comparison.regressions] == ["sc-00", "sc-01", "sc-02", "sc-03"]
    assert comparison.exit_code == 2


def test_three_joint_regressions_among_twenty_are_weak_signals(tmp_path):
    store = Store(tmp_path)
    twenty(store, 3)
    comparison = compare_runs(store, BASE, CAND)
    assert comparison.regressions == [] and len(comparison.weak_signals) == 3
    assert comparison.exit_code == 0


def test_a_significant_improvement_is_never_a_regression(tmp_path):
    store = Store(tmp_path)
    twenty(store, 4, base=False, cand=True)
    comparison = compare_runs(store, BASE, CAND)
    assert {c.status for c in comparison.comparisons} == {"ok"} and comparison.exit_code == 0


def test_a_drop_of_two_tenths_is_not(tmp_path):
    store = Store(tmp_path)
    fill(store, BASE, "sc-a", [True] * 5)
    fill(store, CAND, "sc-a", [True, True, True, True, False])
    comparison = compare_runs(store, BASE, CAND)
    assert comparison.regressions == [] and comparison.exit_code == 0


def test_invalid_repetitions_are_counted_but_not_rated(tmp_path):
    store = Store(tmp_path)
    fill(store, BASE, "sc-a", [True, True, None])
    fill(store, CAND, "sc-a", [True, None, None])
    comparison = compare_runs(store, BASE, CAND)
    only = comparison.comparisons[0]
    assert (only.baseline.valid, only.candidate.valid) == (2, 1)
    assert comparison.invalid == {BASE: 1, CAND: 2}
    assert only.candidate.rate == 1 and not only.regressed


def test_scenarios_present_in_only_one_run_are_listed_apart(tmp_path):
    store = Store(tmp_path)
    fill(store, BASE, "sc-a", [True])
    fill(store, BASE, "sc-b", [True])
    fill(store, CAND, "sc-a", [True])
    comparison = compare_runs(store, BASE, CAND)
    assert [c.scenario_id for c in comparison.comparisons] == ["sc-a"]
    assert comparison.unmatched == ["sc-b"]


def test_rendering_shows_the_regressions(tmp_path):
    store = Store(tmp_path)
    fill(store, BASE, "sc-a", [True] * 5)
    fill(store, CAND, "sc-a", [False] * 5)
    text = render_comparison(compare_runs(store, BASE, CAND))
    assert BASE in text and CAND in text and "REGRESIÓN" in text
    assert "-100%" in text and "0.0079" in text
    assert "1 regresión(es) y 0 señal(es) débil(es)" in text


def test_rendering_shows_no_change_as_plus_zero(tmp_path):
    store = Store(tmp_path)
    fill(store, BASE, "sc-a", [True, True])
    fill(store, CAND, "sc-a", [True, True])
    text = render_comparison(compare_runs(store, BASE, CAND))
    assert "+0%" in text and "-0%" not in text


def test_pairs_with_fewer_valid_repetitions_than_planned_are_marked(tmp_path):
    store = Store(tmp_path)
    fill(store, BASE, "sc-a", [True, True])
    fill(store, CAND, "sc-a", [True, None])
    text = render_comparison(compare_runs(store, BASE, CAND))
    assert "100%*" in text and "D-001" in text


def test_a_scenario_without_valid_repetitions_is_not_tested(tmp_path):
    store = Store(tmp_path)
    fill(store, BASE, "sc-a", [True, True])
    fill(store, CAND, "sc-a", [None, None])
    comparison = compare_runs(store, BASE, CAND)
    assert comparison.comparisons[0].p_value is None
    assert "sin juicio" in render_comparison(comparison)


def test_retries_are_reported_and_a_recovered_repetition_is_not_invalid(tmp_path):
    """Repetition 1 broke once and was rerun; repetition 2 needed a second judgment;
    repetition 3 was never judged after three tries."""
    store = Store(tmp_path)
    fill(store, BASE, "sc-a", [True] * 3)
    fill(store, CAND, "sc-a", [True, True, None])
    broken = trace(
        kind="run",
        trace_id="tr-cand-sc-a-1-broken",
        run_id=CAND,
        scenario_id="sc-a",
        repetition=1,
        termination="simulator_error",
    )
    store.save_run_trace(broken)
    (rerun,) = [t for t in store.run_traces(CAND) if t.trace_id == "tr-cand-sc-a-1"]
    store.save_run_trace(rerun.model_copy(update={"attempt": 2}))
    (second,) = [v for v in store.verdicts(CAND) if v.trace_id == "tr-cand-sc-a-2"]
    store.save_verdict(second.model_copy(update={"attempts": 2}))
    store.save_judge_failure(
        JudgeFailure(
            trace_id="tr-cand-sc-a-3",
            scenario_id="sc-a",
            run_id=CAND,
            attempts=3,
            reasons=["RuntimeError: x"] * 3,
            at=T0,
        )
    )
    comparison = compare_runs(store, BASE, CAND)
    assert comparison.invalid == {BASE: 0, CAND: 1}
    assert comparison.retries[CAND] == Retries(conversations=1, judgments=3)
    assert "reintentos (D-001): 1 conversación(es), 3 juicio(s)" in render_comparison(comparison)
