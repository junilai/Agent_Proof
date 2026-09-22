import asyncio

import pytest

from agentproof.conversation import Exchange
from agentproof.llm import LLMCallError
from agentproof.models import SIM_USER
from agentproof.simulator import END_TOKEN, SimulatedUser, history_prompt
from tests.factories import scenario
from tests.fakes import FakeAsyncLLM, reply

HISTORY = [Exchange("Hola, mis audífonos llegaron dañados", "¿Me da su número de pedido?")]


def ask(client, history=HISTORY):
    return asyncio.run(SimulatedUser(scenario(), client=client).next_message(history))


def test_first_message_is_the_opening_message_without_calling_the_model():
    client = FakeAsyncLLM()
    user = SimulatedUser(scenario(), client=client)
    assert asyncio.run(user.first_message()) == scenario().opening_message
    assert client.messages.calls == []


def test_asks_the_pinned_model_with_the_goal_and_the_conversation():
    client = FakeAsyncLLM(reply("  Es el AT-1001  "))
    assert ask(client) == "Es el AT-1001"
    request = client.messages.calls[0]
    assert request["model"] == SIM_USER.model and request["max_tokens"] == SIM_USER.max_tokens
    assert scenario().user_goal in request["system"]
    assert request["messages"] == [{"role": "user", "content": history_prompt(HISTORY)}]


def test_history_shows_only_what_the_customer_sees():
    assert history_prompt(HISTORY).splitlines()[:3] == [
        "Conversación hasta ahora:",
        "[CLIENTE] Hola, mis audífonos llegaron dañados",
        "[AGENTE] ¿Me da su número de pedido?",
    ]


def test_the_end_token_ends_the_conversation():
    assert ask(FakeAsyncLLM(reply(f"Gracias, eso era todo. {END_TOKEN}"))) is None


@pytest.mark.parametrize("answer", [reply("", stop_reason="refusal"), reply("   ")])
def test_a_refusal_or_an_empty_answer_is_a_simulator_failure(answer):
    with pytest.raises(LLMCallError):
        ask(FakeAsyncLLM(answer))
