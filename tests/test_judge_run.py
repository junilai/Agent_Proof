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


class FlakyJudge:
    """Fails the first `failures` calls for each trace, then judges it."""

    def __init__(self, failures=99):
        self.failures, self.calls = failures, []

    def __call__(self, scenario, run_trace):
        self.calls.append(run_trace.trace_id)
        if self.calls.count(run_trace.trace_id) <= self.failures:
            raise RuntimeError("el juez no respondió")
        return verdict([True], trace_id=run_trace.trace_id, scenario_id=scenario.scenario_id)


def one_trace(tmp_path, attempt=1, broken_before=0):
    """A valid trace of repetition 1 and `broken_before` broken conversations after it."""
    store = Store(tmp_path)
    store.save_scenario(scenario())
    store.create_run(manifest())
    store.save_run_trace(trace(kind="run", trace_id="tr-valid", repetition=1, attempt=attempt))
    for n in range(1, broken_before + 1):
        store.save_run_trace(
            trace(
                kind="run",
                trace_id=f"tr-sim-{n}",
                repetition=2 + (n - 1) // 3,
                attempt=1 + (n - 1) % 3,
                termination="simulator_error",
            )
        )
    return store


def test_a_judgment_that_fails_once_is_judged_again_on_the_same_trace(tmp_path):
    store = one_trace(tmp_path)
    summary = judge_run(store, RUN_ID, judge=FlakyJudge(failures=1))
    assert summary.judged == ["tr-valid"]
    assert store.verdicts(RUN_ID)[0].attempts == 2
    assert store.judge_failures(RUN_ID)[0].attempts == 1


def test_a_judgment_that_always_fails_stops_at_two_retries_and_stays_stopped(tmp_path):
    store = one_trace(tmp_path)
    judge = FlakyJudge()
    assert "tr-valid" in judge_run(store, RUN_ID, judge=judge).failed
    assert judge.calls == ["tr-valid"] * 3
    assert store.judge_failures(RUN_ID)[0].attempts == 3
    assert "tr-valid" in judge_run(store, RUN_ID, judge=judge).failed
    assert len(judge.calls) == 3


def test_the_repetition_cap_is_shared_with_the_conversation_retries(tmp_path):
    """Its conversation was already retried twice: the judgment gets no retry."""
    judge = FlakyJudge()
    judge_run(one_trace(tmp_path, attempt=3), RUN_ID, judge=judge)
    assert judge.calls == ["tr-valid"]


def test_the_scenario_cap_is_shared_with_the_conversation_retries(tmp_path):
    """Repetitions 2 and 3 spent four retries on broken conversations: one judging retry left."""
    judge = FlakyJudge()
    judge_run(one_trace(tmp_path, broken_before=6), RUN_ID, judge=judge)
    assert judge.calls == ["tr-valid"] * 2
