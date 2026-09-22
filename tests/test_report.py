from fractions import Fraction

from agentproof.report import compare_runs, render_comparison
from agentproof.store import Store
from tests.factories import manifest, trace, verdict

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


def test_a_drop_of_four_tenths_is_a_regression(tmp_path):
    store = Store(tmp_path)
    fill(store, BASE, "sc-a", [True] * 5)
    fill(store, CAND, "sc-a", [True, True, True, False, False])
    comparison = compare_runs(store, BASE, CAND)
    assert comparison.comparisons[0].drop == Fraction(2, 5)
    assert comparison.regressions[0].scenario_id == "sc-a" and comparison.exit_code == 2


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
    assert "-100%" in text
    assert "1 regresión(es)" in text


def test_rendering_shows_no_change_as_plus_zero(tmp_path):
    store = Store(tmp_path)
    fill(store, BASE, "sc-a", [True, True])
    fill(store, CAND, "sc-a", [True, True])
    text = render_comparison(compare_runs(store, BASE, CAND))
    assert "+0%" in text and "-0%" not in text
