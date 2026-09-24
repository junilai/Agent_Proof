import pytest

from agentproof.induction import INDUCTION_SYSTEM, ScenarioDraft, induce_scenario, induction_prompt
from agentproof.llm import LLMCallError
from agentproof.models import INDUCER
from tests.factories import T0, trace
from tests.fakes import FakeLLM, parsed

DRAFT = ScenarioDraft(
    user_goal="  Obtener el reembolso de unos audífonos dañados del pedido AT-1001  ",
    opening_message="Hola, mis audífonos del pedido AT-1001 llegaron dañados",
    success_criteria=[
        "El agente informa que el reembolso procede",
        "  ",
        "El agente se refiere al pedido AT-1001",
    ],
)


def test_prompt_is_the_blind_transcript_of_the_seed():
    prompt = induction_prompt(trace())
    assert prompt.startswith("TRANSCRIPCIÓN DE LA CONVERSACIÓN:")
    assert "[USUARIO] Hola" in prompt and "tr-000000000001" not in prompt


def test_instructions_ask_for_outcome_criteria_not_a_trajectory():
    assert "desenlace" in INDUCTION_SYSTEM
    assert "nunca qué herramienta" in INDUCTION_SYSTEM
    assert "entre 2 y 5" in INDUCTION_SYSTEM
    assert "no exijas que el agente justifique" in INDUCTION_SYSTEM


def test_instructions_keep_the_pace_of_the_seed_conversation():
    assert "solo lo que el cliente reveló en su primer mensaje" in INDUCTION_SYSTEM
    assert "no adelantes" in INDUCTION_SYSTEM


def test_builds_the_scenario_of_the_seed():
    client = FakeLLM(parsed(DRAFT))
    scenario = induce_scenario(trace(), client=client, clock=lambda: T0)
    assert scenario.scenario_id == "sc-tr-000000000001"
    assert scenario.seed_trace_id == "tr-000000000001"
    assert scenario.user_goal == "Obtener el reembolso de unos audífonos dañados del pedido AT-1001"
    assert scenario.success_criteria == [
        "El agente informa que el reembolso procede",
        "El agente se refiere al pedido AT-1001",
    ]
    assert scenario.induced_by == INDUCER.model and scenario.created_at == T0
    assert client.messages.calls[0]["model"] == INDUCER.model


def test_a_draft_with_too_few_criteria_is_retried():
    short = DRAFT.model_copy(update={"success_criteria": ["Solo un criterio"]})
    client = FakeLLM(parsed(short), parsed(DRAFT))
    assert len(induce_scenario(trace(), client=client).success_criteria) == 2
    assert len(client.messages.calls) == 2


def test_two_invalid_drafts_raise():
    short = DRAFT.model_copy(update={"success_criteria": ["Solo un criterio"]})
    with pytest.raises(LLMCallError):
        induce_scenario(trace(), client=FakeLLM(parsed(short), parsed(short)))


def test_only_seed_traces_are_induced():
    client = FakeLLM()
    with pytest.raises(ValueError):
        induce_scenario(trace(kind="run"), client=client)
    assert client.messages.calls == []
