"""Framework-neutral data contract of AgentProof.

Every stage of the pipeline communicates through these models; only the
adapters in ``agentproof.adapters`` know anything about a specific framework.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field, model_validator

EventKind = Literal["user_message", "agent_message", "tool_call", "error"]
TraceKind = Literal["seed", "run"]
Termination = Literal["user_ended", "turn_budget", "step_limit", "agent_error", "simulator_error"]

_RUN_FIELDS = ("condition", "run_id", "scenario_id", "repetition")


class Usage(BaseModel):
    """Tokens and cost reported by a component; the cost is ``None`` when unknown."""

    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None

    def __add__(self, other: Usage) -> Usage:
        costs = [c for c in (self.cost_usd, other.cost_usd) if c is not None]
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cost_usd=sum(costs) if costs else None,
        )


class TraceEvent(BaseModel):
    step: int = Field(ge=1)
    kind: EventKind
    ts: datetime
    text: str | None = None
    tool: str | None = None
    arguments: dict[str, Any] | None = None
    result: Any = None
    is_error: bool = False


class Trace(BaseModel):
    trace_id: str
    kind: TraceKind
    adapter: str
    agent: str
    variant: str
    condition: str | None = None
    run_id: str | None = None
    scenario_id: str | None = None
    repetition: int | None = None
    card_id: str | None = None
    """Situation the conversation was elicited with; opaque to the core (§5.2)."""
    termination: Termination
    events: list[TraceEvent]
    models: dict[str, Any]
    usage: Usage = Field(default_factory=Usage)
    started_at: datetime
    ended_at: datetime

    @model_validator(mode="after")
    def _run_fields_match_the_kind(self) -> Trace:
        present = [getattr(self, name) is not None for name in _RUN_FIELDS]
        if self.kind == "run" and not all(present):
            raise ValueError("run traces need condition, run_id, scenario_id and repetition")
        if self.kind == "seed" and any(present):
            raise ValueError("seed traces cannot carry run fields")
        return self

    def final_reply(self) -> str:
        """Agent text after the last user message: the reply the failure predicates inspect."""
        last_user = max((e.step for e in self.events if e.kind == "user_message"), default=0)
        texts = [
            e.text or "" for e in self.events if e.kind == "agent_message" and e.step > last_user
        ]
        return "\n".join(texts)


def new_trace_id() -> str:
    return f"tr-{uuid.uuid4().hex[:12]}"


class Scenario(BaseModel):
    """Induced from one seed trace: the input of the simulated user and of the judge."""

    scenario_id: str
    seed_trace_id: str
    user_goal: str
    opening_message: str
    success_criteria: list[str] = Field(min_length=2, max_length=5)
    induced_by: str
    created_at: datetime

    @model_validator(mode="after")
    def _id_follows_the_seed(self) -> Scenario:
        if self.scenario_id != scenario_id_for(self.seed_trace_id):
            raise ValueError("scenario_id must be derived from seed_trace_id")
        return self


class CriterionResult(BaseModel):
    criterion: str
    met: bool
    justification: str


class Verdict(BaseModel):
    trace_id: str
    scenario_id: str
    run_id: str
    criteria: list[CriterionResult] = Field(min_length=1)
    judged_by: str
    created_at: datetime

    @computed_field
    @property
    def passed(self) -> bool:
        return all(c.met for c in self.criteria)


class RunManifest(BaseModel):
    run_id: str
    condition: str
    variant: str
    adapter: str
    agent: str
    repetitions: int = Field(ge=1)
    turn_budget: int = Field(ge=1)
    models: dict[str, Any]
    created_at: datetime


def scenario_id_for(seed_trace_id: str) -> str:
    return f"sc-{seed_trace_id}"


def run_id_for(condition: str, when: datetime) -> str:
    return f"{condition}-{when:%Y%m%d-%H%M%S}"
