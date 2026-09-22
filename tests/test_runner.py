import asyncio

from agentproof.runner import run_suite
from agentproof.store import Store
from tests.factories import manifest, scenario
from tests.fakes import CrashingSession, EchoSession, ScriptedUser, ticking_clock


def run(tmp_path, factory=EchoSession, repetitions=3):
    store = Store(tmp_path)
    scenarios = [scenario(), scenario(scenario_id="sc-tr-b", seed_trace_id="tr-b")]
    seen = []
    traces = asyncio.run(
        run_suite(
            scenarios,
            factory,
            manifest(repetitions=repetitions, turn_budget=4),
            store,
            user_for=lambda s: ScriptedUser(s.opening_message, "gracias"),
            clock=ticking_clock(),
            on_trace=seen.append,
        )
    )
    return store, traces, seen


def test_one_trace_per_scenario_and_repetition(tmp_path):
    store, traces, seen = run(tmp_path)
    pairs = sorted((t.scenario_id, t.repetition) for t in store.run_traces(manifest().run_id))
    assert pairs == [(s, r) for s in ("sc-tr-000000000001", "sc-tr-b") for r in (1, 2, 3)]
    assert len(traces) == len(seen) == 6
    assert store.manifest(manifest().run_id) == manifest(repetitions=3, turn_budget=4)


def test_a_crashing_agent_still_gives_one_trace_each(tmp_path):
    store, traces, _ = run(tmp_path, factory=CrashingSession, repetitions=2)
    assert len(store.run_traces(manifest().run_id)) == 4
    assert {t.termination for t in traces} == {"agent_error"}


def test_traces_carry_the_run_context_and_its_models(tmp_path):
    _, traces, _ = run(tmp_path, repetitions=1)
    first = traces[0]
    assert (first.kind, first.condition, first.variant) == ("run", "baseline-a", "baseline")
    assert first.models == manifest().models
