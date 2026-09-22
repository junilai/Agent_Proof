"""Blind judge (§5.1): grades one run trace against its scenario's criteria.

It reads only the numbered criteria and the blind transcript; it never learns
which condition, variant or model produced the conversation. The rubric is the
exact text the human annotators receive in E2 (§5.5). An answer that does not
cover every criterion exactly once is retried and, if it fails again, reported:
missing results are never filled in.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

import anthropic
from pydantic import BaseModel

from agentproof.conversation import utc_now
from agentproof.llm import structured_call
from agentproof.models import JUDGE
from agentproof.schema import CriterionResult, Scenario, Trace, Verdict
from agentproof.transcript import render_transcript

JUDGE_RUBRIC = "\n".join(
    [
        "Evalúas cómo resolvió un agente de atención al cliente una conversación con un cliente.",
        "Recibirás los criterios de éxito del caso y la transcripción completa de la conversación.",
        "Para cada criterio, decide si se cumple:",
        "- Se cumple si la transcripción muestra con claridad que el agente lo satisfizo.",
        "- No se cumple si el agente no lo satisfizo o si no es posible verificarlo con la "
        "transcripción.",
        "Juzga únicamente lo que muestra la transcripción. No premies ni castigues el estilo, la "
        "extensión ni la cortesía.",
        "Para cada criterio, indica su número, si se cumple y una justificación breve en español.",
    ]
)


class JudgedCriterion(BaseModel):
    number: int
    met: bool
    justification: str


class JudgeOutput(BaseModel):
    results: list[JudgedCriterion]


def judge_prompt(scenario: Scenario, trace: Trace) -> str:
    criteria = "\n".join(f"{i}. {c}" for i, c in enumerate(scenario.success_criteria, start=1))
    return f"CRITERIOS DE ÉXITO:\n{criteria}\n\nTRANSCRIPCIÓN:\n{render_transcript(trace)}"


def judge_trace(
    scenario: Scenario,
    trace: Trace,
    client: Any = None,
    clock: Callable[[], datetime] = utc_now,
) -> Verdict:
    if trace.kind != "run" or trace.scenario_id != scenario.scenario_id or trace.run_id is None:
        raise ValueError(f"trace {trace.trace_id} is not a run of {scenario.scenario_id}")
    run_id = trace.run_id
    criteria = scenario.success_criteria

    def to_verdict(output: JudgeOutput) -> Verdict:
        numbers = [r.number for r in output.results]
        if sorted(numbers) != list(range(1, len(criteria) + 1)):
            raise ValueError(f"el juez no evaluó cada criterio una vez: {numbers}")
        by_number = {r.number: r for r in output.results}
        return Verdict(
            trace_id=trace.trace_id,
            scenario_id=scenario.scenario_id,
            run_id=run_id,
            criteria=[
                CriterionResult(
                    criterion=text,
                    met=by_number[i].met,
                    justification=by_number[i].justification.strip(),
                )
                for i, text in enumerate(criteria, start=1)
            ],
            judged_by=JUDGE.model,
            created_at=clock(),
        )

    return structured_call(
        client or anthropic.Anthropic(),
        JUDGE,
        system=JUDGE_RUBRIC,
        prompt=judge_prompt(scenario, trace),
        output_type=JudgeOutput,
        validate=to_verdict,
    )
