"""Samples drawn from the judged runs of E1 for the human annotation of F6.

The audit of the oracle (§4 of the pre-registration) takes 5 valid traces per
condition, 3 in which the agent created a ticket and 2 in which it did not,
because tickets are the known weak point of the rules. A condition with fewer
than 3 tickets is completed with traces without one.

    python -m experiments.samples --data .
"""

from __future__ import annotations

import random
from typing import Literal

from pydantic import BaseModel

from agentproof.schema import Trace
from agentproof.store import Store

AUDIT_SEED = 20261021
AUDIT_PER_CONDITION = 5
AUDIT_WITH_TICKET = 3

Stratum = Literal["con ticket", "sin ticket", "aprobado", "reprobado"]


class Drawn(BaseModel):
    """One trace of a sample; the stratum it was drawn from is never shown to annotators."""

    run_id: str
    trace_id: str
    scenario_id: str
    condition: str
    variant: str
    stratum: Stratum


def has_ticket(trace: Trace) -> bool:
    return any(e.kind == "tool_call" and e.tool == "create_ticket" for e in trace.events)


def valid_traces(store: Store, run_ids: list[str]) -> dict[str, list[Trace]]:
    """Valid traces per condition, in a fixed order; a simulator error is invalid (D-001)."""
    found: dict[str, list[Trace]] = {}
    for run_id in sorted(run_ids):
        condition = store.manifest(run_id).condition
        traces = [t for t in store.run_traces(run_id) if t.termination != "simulator_error"]
        found.setdefault(condition, []).extend(traces)
    return {c: sorted(ts, key=lambda t: t.trace_id) for c, ts in sorted(found.items())}


def drawn(trace: Trace, stratum: Stratum) -> Drawn:
    return Drawn(
        run_id=trace.run_id or "",
        trace_id=trace.trace_id,
        scenario_id=trace.scenario_id or "",
        condition=trace.condition or "",
        variant=trace.variant,
        stratum=stratum,
    )


def audit_sample(store: Store, run_ids: list[str]) -> list[Drawn]:
    rng = random.Random(AUDIT_SEED)
    sample = []
    for traces in valid_traces(store, run_ids).values():
        with_ticket = [t for t in traces if has_ticket(t)]
        without = [t for t in traces if not has_ticket(t)]
        k = min(AUDIT_WITH_TICKET, len(with_ticket))
        sample += [drawn(t, "con ticket") for t in rng.sample(with_ticket, k)]
        sample += [drawn(t, "sin ticket") for t in rng.sample(without, AUDIT_PER_CONDITION - k)]
    return sample


def ticket_share(store: Store, run_ids: list[str]) -> dict[str, tuple[int, int]]:
    """Valid traces with a ticket and in total, per condition, to weight the audit's error."""
    return {
        condition: (sum(has_ticket(t) for t in traces), len(traces))
        for condition, traces in valid_traces(store, run_ids).items()
    }
