"""Optional human review of the induced scenarios: the curated suite (§5.3).

The pipeline never needs it and the experiments never use it: they run on the
scenarios as induced. Whoever wants to review them works on a copy of the corpus
in another folder, where each scenario is approved as it is or corrected; the
original corpus is never touched. The curated suite is then run and judged like
any other, with ``--data`` pointing to the copy.

    <copy>/corpus/seeds/...        the same seeds
    <copy>/corpus/scenarios/...    the induced scenarios, replaced as they are reviewed
    <copy>/corpus/revision.json    who reviewed each scenario and whether it changed
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, TypeAdapter

from agentproof.schema import Scenario
from agentproof.store import Store


class Review(BaseModel):
    scenario_id: str
    reviewer: str
    corrected: bool
    reviewed_at: datetime


_REVIEWS = TypeAdapter(list[Review])


def _log(copy: Store) -> Path:
    return copy.root / "corpus" / "revision.json"


def start(source: Store, copy: Store) -> None:
    """Copy the seeds and the induced scenarios; what the copy already has is kept."""
    if copy.root.resolve() == source.root.resolve():
        raise ValueError("la suite curada va en otra carpeta: el corpus original no se modifica")
    known = {seed.trace_id for seed in copy.seeds()}
    for seed in source.seeds():
        if seed.trace_id not in known:
            copy.save_seed(seed)
    for scenario in source.scenarios():
        copy.save_scenario(scenario)


def reviews(copy: Store) -> dict[str, Review]:
    path = _log(copy)
    if not path.exists():
        return {}
    return {r.scenario_id: r for r in _REVIEWS.validate_json(path.read_bytes())}


def save(copy: Store, scenario: Scenario, review: Review) -> None:
    """Keep the reviewed scenario in the copy and log the review."""
    copy.save_scenario(scenario, overwrite=True)
    done = reviews(copy)
    done[review.scenario_id] = review
    _log(copy).write_bytes(_REVIEWS.dump_json(list(done.values()), indent=2) + b"\n")


def corrected(
    scenario: Scenario,
    *,
    goal: str,
    opening: str,
    criteria: list[str],
    reviewer: str,
    now: datetime,
) -> Scenario:
    """The scenario with the reviewer's text; it still has to be a valid scenario."""
    fields = scenario.model_dump()
    fields.update(
        user_goal=goal,
        opening_message=opening,
        success_criteria=criteria,
        induced_by=f"{scenario.induced_by}; revisado por {reviewer}",
        created_at=now,
    )
    return Scenario.model_validate(fields)
