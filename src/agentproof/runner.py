"""Runner (§5.1): replays every scenario ``repetitions`` times against one agent.

Each attempt is one ``converse`` call, so it always yields exactly one trace,
even when the agent crashes, and a failing scenario never stops the suite. A
repetition the simulated user broke (``simulator_error``) is run again within
the caps of D-001; the failed attempt is kept. Nothing the agent did is ever
retried. A run that was interrupted is resumed with ``resume=True``: every
repetition that already has a valid trace is skipped, and the retries already
spent still count against the caps.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

from agentproof import retries
from agentproof.conversation import TraceContext, UserDriver, converse, utc_now
from agentproof.schema import RunManifest, Scenario, Trace
from agentproof.session import SessionFactory
from agentproof.simulator import SimulatedUser
from agentproof.store import Store


async def run_suite(
    scenarios: Sequence[Scenario],
    session_factory: SessionFactory,
    manifest: RunManifest,
    store: Store,
    user_for: Callable[[Scenario], UserDriver] = SimulatedUser,
    clock: Callable[[], datetime] = utc_now,
    on_trace: Callable[[Trace], None] | None = None,
    resume: bool = False,
) -> list[Trace]:
    done = store.run_traces(manifest.run_id) if resume else []
    if not resume:
        store.create_run(manifest)
    traces: list[Trace] = []
    for scenario in scenarios:
        retried = retries.conversation_retries(done, scenario.scenario_id)
        for repetition in range(1, manifest.repetitions + 1):
            previous = [
                t
                for t in done
                if t.scenario_id == scenario.scenario_id and t.repetition == repetition
            ]
            if any(t.termination != "simulator_error" for t in previous):
                continue
            attempt = max((t.attempt or 1 for t in previous), default=0) + 1
            if previous:
                if attempt > retries.PER_REPETITION + 1 or retried >= retries.PER_SCENARIO:
                    continue
                retried += 1
            while True:
                context = TraceContext(
                    kind="run",
                    adapter=manifest.adapter,
                    agent=manifest.agent,
                    variant=manifest.variant,
                    condition=manifest.condition,
                    run_id=manifest.run_id,
                    scenario_id=scenario.scenario_id,
                    repetition=repetition,
                    attempt=attempt,
                )
                trace = await converse(
                    session_factory,
                    user_for(scenario),
                    context,
                    turn_budget=manifest.turn_budget,
                    model_config=manifest.models,
                    clock=clock,
                )
                store.save_run_trace(trace)
                traces.append(trace)
                if on_trace is not None:
                    on_trace(trace)
                exhausted = attempt > retries.PER_REPETITION or retried >= retries.PER_SCENARIO
                if trace.termination != "simulator_error" or exhausted:
                    break
                attempt, retried = attempt + 1, retried + 1
    return traces
