import asyncio

import pytest

from agentproof.runner import run_suite
from agentproof.session import AgentTurn
from agentproof.simulator import END_TOKEN, SimulatedUser
from agentproof.store import Store
from tests.factories import manifest, scenario
from tests.fakes import (
    CrashingSession,
    EchoSession,
    FakeAsyncLLM,
    ScriptedUser,
    reply,
    ticking_clock,
    tokens,
)


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


class BrokenUser(ScriptedUser):
    async def first_message(self) -> str:
        raise RuntimeError("el usuario simulado no respondió")


def failing_first(times):
    """A user factory whose first `times` users fail before the conversation starts."""
    made = []

    def user_for(s):
        made.append(s)
        broken = len(made) <= times
        return BrokenUser() if broken else ScriptedUser(s.opening_message, "gracias")

    return user_for


def run_with(tmp_path, user_for, repetitions=1, factory=EchoSession, turn_budget=4):
    store = Store(tmp_path)
    asyncio.run(
        run_suite(
            [scenario()],
            factory,
            manifest(repetitions=repetitions, turn_budget=turn_budget),
            store,
            user_for=user_for,
            clock=ticking_clock(),
        )
    )
    return [(t.repetition, t.attempt, t.termination) for t in store.run_traces(manifest().run_id)]


def test_a_conversation_the_simulated_user_broke_is_run_again_and_kept(tmp_path):
    found = run_with(tmp_path, failing_first(1))
    assert sorted(found) == [(1, 1, "simulator_error"), (1, 2, "user_ended")]


def test_two_retries_per_repetition_at_most(tmp_path):
    found = run_with(tmp_path, failing_first(99))
    assert sorted(found) == [(1, a, "simulator_error") for a in (1, 2, 3)]


def test_five_retries_per_scenario_at_most(tmp_path):
    """Repetitions 1 and 2 spend two retries each; the third gets the last one."""
    attempts = sorted((r, a) for r, a, _ in run_with(tmp_path, failing_first(99), repetitions=3))
    assert attempts == [(1, 1), (1, 2), (1, 3), (2, 1), (2, 2), (2, 3), (3, 1), (3, 2)]


class StepLimitSession(EchoSession):
    async def send(self, message: str) -> AgentTurn:
        turn = await super().send(message)
        return turn.model_copy(update={"stop_reason": "step_limit"})


@pytest.mark.parametrize(
    ("factory", "user", "turn_budget", "termination"),
    [
        (EchoSession, ("hola",), 4, "user_ended"),
        (EchoSession, ("hola", "otra", "más"), 1, "turn_budget"),
        (StepLimitSession, ("hola",), 4, "step_limit"),
        (CrashingSession, ("hola",), 4, "agent_error"),
    ],
)
def test_what_the_agent_did_is_never_retried(tmp_path, factory, user, turn_budget, termination):
    found = run_with(tmp_path, lambda s: ScriptedUser(*user), 2, factory, turn_budget)
    assert sorted(found) == [(1, 1, termination), (2, 1, termination)]


class Interrupted(Exception):
    pass


def stop_after(count):
    seen = []

    def on_trace(trace):
        seen.append(trace)
        if len(seen) == count:
            raise Interrupted

    return on_trace


def suite(store, user_for, on_trace=None, resume=False, repetitions=3):
    scenarios = [scenario(), scenario(scenario_id="sc-tr-b", seed_trace_id="tr-b")]
    return asyncio.run(
        run_suite(
            scenarios,
            EchoSession,
            manifest(repetitions=repetitions, turn_budget=4),
            store,
            user_for=user_for,
            clock=ticking_clock(),
            on_trace=on_trace,
            resume=resume,
        )
    )


def good_user(s):
    return ScriptedUser(s.opening_message, "gracias")


def test_an_interrupted_run_resumes_without_repeating_anything(tmp_path):
    store = Store(tmp_path)
    with pytest.raises(Interrupted):
        suite(store, good_user, on_trace=stop_after(4))
    assert len(store.run_traces(manifest().run_id)) == 4
    assert len(suite(store, good_user, resume=True)) == 2
    pairs = [(t.scenario_id, t.repetition) for t in store.run_traces(manifest().run_id)]
    assert sorted(pairs) == [(s, r) for s in ("sc-tr-000000000001", "sc-tr-b") for r in (1, 2, 3)]
    assert suite(store, good_user, resume=True) == []


def test_resuming_continues_a_broken_repetition_within_its_caps(tmp_path):
    store = Store(tmp_path)
    with pytest.raises(Interrupted):
        suite(store, failing_first(1), on_trace=stop_after(1), repetitions=1)
    resumed = suite(store, good_user, resume=True, repetitions=1)
    assert [(t.scenario_id, t.attempt, t.termination) for t in resumed] == [
        ("sc-tr-000000000001", 2, "user_ended"),
        ("sc-tr-b", 1, "user_ended"),
    ]


def test_resuming_never_exceeds_the_retries_already_spent(tmp_path):
    store = Store(tmp_path)
    suite(store, failing_first(99), repetitions=1)
    assert suite(store, good_user, resume=True, repetitions=1) == []


def test_traces_record_the_simulated_user_and_the_agent_apart(tmp_path):
    def simulated(s):
        return SimulatedUser(s, client=FakeAsyncLLM(reply(END_TOKEN, usage=tokens(70, 2))))

    store = Store(tmp_path)
    asyncio.run(run_suite([scenario()], EchoSession, manifest(repetitions=1), store, simulated))
    (only,) = store.run_traces(manifest().run_id)
    assert (only.simulator_usage.input_tokens, only.simulator_usage.output_tokens) == (70, 2)
    assert only.usage.input_tokens == 10 and only.usage.cost_usd == 0.25
    assert only.simulator_seconds is not None and only.agent_seconds is not None
