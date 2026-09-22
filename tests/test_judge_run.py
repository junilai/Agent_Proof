from agentproof.judge import judge_run
from agentproof.store import Store
from tests.factories import manifest, scenario, trace, verdict

RUN_ID = "baseline-a-20261001-120000"


def prepared_store(tmp_path):
    store = Store(tmp_path)
    store.save_scenario(scenario())
    store.create_run(manifest())
    store.save_run_trace(trace(kind="run", trace_id="tr-ok", repetition=1))
    store.save_run_trace(
        trace(kind="run", trace_id="tr-sim", repetition=2, termination="simulator_error")
    )
    store.save_run_trace(trace(kind="run", trace_id="tr-crash", repetition=3))
    return store


def fake_judge(scenario, run_trace):
    if run_trace.trace_id == "tr-crash":
        raise RuntimeError("el juez no respondió")
    return verdict([True], trace_id=run_trace.trace_id, scenario_id=scenario.scenario_id)


def test_judges_each_valid_trace_once(tmp_path):
    store = prepared_store(tmp_path)
    first = judge_run(store, RUN_ID, judge=fake_judge)
    assert first.judged == ["tr-ok"] and first.skipped == ["tr-sim"]
    assert first.failed == {"tr-crash": "RuntimeError: el juez no respondió"}
    second = judge_run(store, RUN_ID, judge=fake_judge)
    assert second.judged == [] and second.kept == ["tr-ok"]
    assert [v.trace_id for v in store.verdicts(RUN_ID)] == ["tr-ok"]
