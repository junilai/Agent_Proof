"""Samples drawn from the judged runs of E1 for the human annotation of F6.

The audit of the oracle (§4 of the pre-registration) takes 5 valid traces per
condition, 3 in which the agent created a ticket and 2 in which it did not,
because tickets are the known weak point of the rules. A condition with fewer
than 3 tickets is completed with traces without one.

The sample of E2 (§6) takes 20 judged pairs the judge passed and 20 it failed.
Within each stratum no scenario and no version of the agent gives more than 2
pairs; a stratum that cannot be filled raises both caps to 3, and if it still
cannot, both strata shrink to the smaller one (D-011).

    python -m experiments.samples --data .
"""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path
from typing import Literal

import typer
from pydantic import BaseModel

from agentproof.schema import Trace
from agentproof.store import Store

AUDIT_SEED = 20261021
AUDIT_PER_CONDITION = 5
AUDIT_WITH_TICKET = 3
E2_SEED = 20261018
E2_PER_STRATUM = 20
E2_CAP = 2
E2_CAP_CONTINGENCY = 3

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


class AuditSample(BaseModel):
    seed: int
    traces: list[Drawn]
    ticket_share: dict[str, tuple[int, int]]


class E2Sample(BaseModel):
    seed: int = E2_SEED
    pairs: list[Drawn]
    caps: dict[str, int]
    per_stratum: int


def _greedy(order: list[Trace], cap: int, size: int) -> list[Trace]:
    """The first traces of ``order`` that keep every scenario and version under ``cap``."""
    by_scenario: Counter[str] = Counter()
    by_variant: Counter[str] = Counter()
    chosen = []
    for t in order:
        if len(chosen) == size:
            break
        if by_scenario[t.scenario_id or ""] < cap and by_variant[t.variant] < cap:
            chosen.append(t)
            by_scenario[t.scenario_id or ""] += 1
            by_variant[t.variant] += 1
    return chosen


def e2_sample(
    store: Store,
    run_ids: list[str],
    size: int = E2_PER_STRATUM,
    cap: int = E2_CAP,
    contingency: int = E2_CAP_CONTINGENCY,
) -> E2Sample:
    passed = {v.trace_id: v.passed for run_id in run_ids for v in store.verdicts(run_id)}
    judged = sorted(
        (t for ts in valid_traces(store, run_ids).values() for t in ts if t.trace_id in passed),
        key=lambda t: t.trace_id,
    )
    rng = random.Random(E2_SEED)
    chosen: dict[Stratum, list[Trace]] = {}
    caps: dict[str, int] = {}
    for stratum, wanted in (("aprobado", True), ("reprobado", False)):
        pool = [t for t in judged if passed[t.trace_id] is wanted]
        order = rng.sample(pool, len(pool))
        chosen[stratum], caps[stratum] = _greedy(order, cap, size), cap
        if len(chosen[stratum]) < size:
            chosen[stratum], caps[stratum] = _greedy(order, contingency, size), contingency
    n = min(len(picked) for picked in chosen.values())
    pairs = [drawn(t, stratum) for stratum, picked in chosen.items() for t in picked[:n]]
    return E2Sample(pairs=pairs, caps=caps, per_stratum=n)


app = typer.Typer(help="Sorteos de la auditoría del oráculo y de la muestra de E2.")
DATA = typer.Option(Path("."), "--data", help="Carpeta que contiene corpus/ y results/.")


@app.command()
def main(data: Path = DATA):
    """Escribe results/samples/auditoria.json y results/samples/e2.json."""
    store = Store(data)
    runs = store.runs()
    audit = AuditSample(
        seed=AUDIT_SEED, traces=audit_sample(store, runs), ticket_share=ticket_share(store, runs)
    )
    e2 = e2_sample(store, runs)
    folder = store.root / "results" / "samples"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "auditoria.json").write_text(audit.model_dump_json(indent=2) + "\n")
    (folder / "e2.json").write_text(e2.model_dump_json(indent=2) + "\n")
    typer.echo(f"Auditoría: {len(audit.traces)} trazas (semilla {AUDIT_SEED}).")
    for condition, (tickets, total) in audit.ticket_share.items():
        typer.echo(f"  {condition}: {tickets} de {total} trazas válidas con ticket")
    typer.echo(
        f"E2: {e2.per_stratum} pares por estrato (semilla {E2_SEED}); "
        f"tope por escenario y por versión: {e2.caps}."
    )


if __name__ == "__main__":
    app()
