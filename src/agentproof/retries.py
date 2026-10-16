"""Caps of the invalid-repetition rule (D-001).

Only failures of the instrumentation are retried: a conversation the simulated
user broke is run again, a judgment that failed is judged again on the same
trace. Both stages share the caps: two retries per repetition and five per
scenario within a run.
"""

from __future__ import annotations

from collections.abc import Iterable

from agentproof.schema import Trace

PER_REPETITION = 2
PER_SCENARIO = 5


def conversation_retries(traces: Iterable[Trace], scenario_id: str) -> int:
    """Conversations of a scenario that were run again after the simulated user failed."""
    return sum(1 for t in traces if t.scenario_id == scenario_id and (t.attempt or 1) > 1)
