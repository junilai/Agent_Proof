import pytest

from agentproof.judge import JUDGE_RUBRIC, JudgedCriterion, JudgeOutput, judge_prompt, judge_trace
from agentproof.llm import LLMCallError
from agentproof.models import JUDGE
from tests.factories import T0, scenario, trace
from tests.fakes import FakeLLM, parsed


def output(*marks):
    return JudgeOutput(
        results=[
            JudgedCriterion(number=n, met=met, justification=f"  motivo {n}  ") for n, met in marks
        ]
    )


def run_trace(**overrides):
    return trace(kind="run", trace_id="tr-000000000002", **overrides)


def test_prompt_numbers_the_criteria_and_shows_the_blind_transcript():
    prompt = judge_prompt(scenario(), run_trace(variant="d3"))
    assert "1. El agente informa que el reembolso procede" in prompt
    assert "2. El agente se refiere al pedido AT-1001" in prompt
    assert "[USUARIO] Hola" in prompt
    for secret in ("baseline-a", "d3", "tr-000000000002", "tests:fake"):
        assert secret not in prompt


def test_rubric_never_mentions_versions():
    assert "versión" not in JUDGE_RUBRIC.lower()
    assert "No premies ni castigues el estilo" in JUDGE_RUBRIC


def test_builds_the_verdict_in_criteria_order():
    client = FakeLLM(parsed(output((2, False), (1, True))))
    verdict = judge_trace(scenario(), run_trace(), client=client, clock=lambda: T0)
    assert [c.met for c in verdict.criteria] == [True, False]
    assert verdict.criteria[0].criterion == "El agente informa que el reembolso procede"
    assert verdict.criteria[1].justification == "motivo 2"
    assert (verdict.passed, verdict.judged_by, verdict.created_at) == (False, JUDGE.model, T0)
    assert verdict.run_id == "baseline-a-20261001-120000"
    assert client.messages.calls[0]["system"] == JUDGE_RUBRIC


@pytest.mark.parametrize("marks", [[(1, True)], [(1, True), (1, True)], [(1, True), (3, True)]])
def test_an_answer_that_does_not_cover_every_criterion_is_retried(marks):
    client = FakeLLM(parsed(output(*marks)), parsed(output((1, True), (2, True))))
    assert judge_trace(scenario(), run_trace(), client=client).passed is True
    assert len(client.messages.calls) == 2


def test_two_incomplete_answers_raise_instead_of_filling_gaps():
    client = FakeLLM(parsed(output((1, True))), parsed(output((1, True))))
    with pytest.raises(LLMCallError):
        judge_trace(scenario(), run_trace(), client=client)


def test_only_run_traces_of_the_same_scenario_are_judged():
    for wrong in (trace(), run_trace(scenario_id="sc-otro")):
        with pytest.raises(ValueError):
            judge_trace(scenario(), wrong, client=FakeLLM())
