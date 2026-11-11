"""The oracle audit on E1 against the majority of three annotators (pre-registration §4).

Each audited trace is scored as the oracle validation scores a reconciled label
(D-010, ``experiments.validation.tally``), with the majority of the three
annotators in place of the reconciled label: the decision, the attributes, the
status and the predicate of each exposed operator. The oracle is the one
installed with the code that runs this analysis, with its rules alone: a trace
the rules leave unresolved counts as such ("a la cola").

A decision without a majority is reported apart, unless every annotator's
decision gives the same outcome. Tickets are over-represented in the sample, so
every proportion is given per stratum and weighted by the share of traces with
a ticket in E1 (``ticket_share`` of the sample).
"""

from __future__ import annotations

import json
from collections import Counter
from itertools import chain

from pydantic import BaseModel

from agentproof.store import Store
from experiments.f6.agreement import fleiss_kappa, majority
from experiments.f6.e2 import pairwise
from experiments.f6.labels import FACTS, TraceLabel
from experiments.oracle.annotation import Case, seed_and_card
from experiments.oracle.predicates import OPERATORS_WITH_PREDICATE
from experiments.validation import Label, tally

SAMPLE = ("results", "samples", "auditoria.json")
STRATA = ("con ticket", "sin ticket")
GROUPS = (
    "decisión",
    "atributos",
    "estado",
    *(f"predicado {op}" for op in OPERATORS_WITH_PREDICATE),
)

Table = dict[str, dict[str, int]]


class Apart(BaseModel):
    key: str
    field: str
    votes: list[str]


class AuditTrace(BaseModel):
    key: str
    condition: str
    stratum: str
    majority: dict[str, str | bool | None]
    outcomes: list[tuple[str, str]]


class StratumAudit(BaseModel):
    traces: int
    table: Table


class FieldAgreement(BaseModel):
    items: int
    unanimous: int
    fleiss: float | None
    cohen: dict[str, float | None]


class Audit(BaseModel):
    audited: int
    left_out: list[str]
    strata: dict[str, StratumAudit]
    overall: Table
    ticket_weight: float
    weighted: dict[str, dict[str, float | None]]
    without_majority: list[Apart]
    annotators: dict[str, FieldAgreement]
    traces: list[AuditTrace]


def _cases(store: Store) -> list[tuple[Case, str]]:
    sample = json.loads(store.root.joinpath(*SAMPLE).read_text(encoding="utf-8"))
    seeds = {seed.trace_id: seed for seed in store.seeds()}
    found = []
    for drawn in sample["traces"]:
        trace = next(
            t for t in store.run_traces(drawn["run_id"]) if t.trace_id == drawn["trace_id"]
        )
        seed, card = seed_and_card(seeds, trace.scenario_id or "")
        found.append((Case(drawn["run_id"], trace, seed, card), drawn["stratum"]))
    return found


def ticket_weight(store: Store) -> float:
    """Share of the valid traces of E1 in which the agent created a ticket."""
    sample = json.loads(store.root.joinpath(*SAMPLE).read_text(encoding="utf-8"))
    tickets = sum(t for t, _ in sample["ticket_share"].values())
    return tickets / sum(n for _, n in sample["ticket_share"].values())


def _score(
    case: Case, key: str, stratum: str, votes: list[TraceLabel], apart: list[Apart]
) -> AuditTrace:
    agreed = {name: majority([getattr(v, name) for v in votes]) for name in FACTS}
    readings = [tally(case, Label(item=key, **(agreed | {"decision": v.decision}))) for v in votes]
    outcomes = readings[0]
    if agreed["decision"] is None and case.card.has_decision:
        settled = [o for o in outcomes if all(o in r for r in readings)]
        if settled != outcomes:
            apart.append(Apart(key=key, field="decision", votes=[v.decision for v in votes]))
        outcomes = settled
    else:
        outcomes = tally(case, Label(item=key, **agreed))
    return AuditTrace(
        key=key,
        condition=case.trace.condition or "",
        stratum=stratum,
        majority=agreed,
        outcomes=outcomes,
    )


def _table(outcomes: list[tuple[str, str]]) -> Table:
    table: Table = {group: {} for group in GROUPS}
    for (group, key), n in sorted(Counter(outcomes).items()):
        if group == "predicados":  # each operator apart: "d1 coincide" -> "predicado d1"
            op, key = key.split(" ", 1)
            group = f"predicado {op}"
        table[group][key] = n
    return table


def weighted(ticket: Table, without: Table, weight: float) -> dict[str, dict[str, float | None]]:
    """Each outcome's share of its group, mixing the strata by the share of tickets in E1."""
    found: dict[str, dict[str, float | None]] = {}
    for group in dict.fromkeys(chain(ticket, without)):
        ours, theirs = ticket.get(group, {}), without.get(group, {})
        n, m = sum(ours.values()), sum(theirs.values())
        found[group] = {
            key: None
            if not n or not m
            else weight * ours.get(key, 0) / n + (1 - weight) * theirs.get(key, 0) / m
            for key in sorted(set(ours) | set(theirs))
        }
    return found


def _agreement(name: str, keys: list[str], labels: dict[str, dict[str, TraceLabel]]):
    annotators = sorted(labels)
    asked = [k for k in keys if getattr(labels[annotators[0]][k], name) is not None]
    votes = {a: [getattr(labels[a][k], name) for k in asked] for a in annotators}
    rows = list(zip(*votes.values(), strict=True))
    return FieldAgreement(
        items=len(asked),
        unanimous=sum(len(set(row)) == 1 for row in rows),
        fleiss=fleiss_kappa(rows),
        cohen=pairwise(votes),
    )


def audit(store: Store, labels: dict[str, dict[str, TraceLabel]]) -> Audit:
    annotators = sorted(labels)
    traces, left_out, apart = [], [], []
    for case, stratum in _cases(store):
        key = f"{case.run_id}/{case.trace.trace_id}"
        if not case.card.has_decision and not case.card.orders:
            left_out.append(key)  # the oracle reads nothing in these cards
            continue
        traces.append(_score(case, key, stratum, [labels[a][key] for a in annotators], apart))
    strata = {
        s: StratumAudit(
            traces=sum(t.stratum == s for t in traces),
            table=_table([o for t in traces if t.stratum == s for o in t.outcomes]),
        )
        for s in STRATA
    }
    weight = ticket_weight(store)
    keys = [t.key for t in traces]
    return Audit(
        audited=len(traces),
        left_out=left_out,
        strata=strata,
        overall=_table([o for t in traces for o in t.outcomes]),
        ticket_weight=weight,
        weighted=weighted(strata["con ticket"].table, strata["sin ticket"].table, weight),
        without_majority=apart,
        annotators={name: _agreement(name, keys, labels) for name in FACTS},
        traces=traces,
    )
