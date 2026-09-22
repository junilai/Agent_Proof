import pytest
from pydantic import BaseModel

from agentproof.llm import LLMCallError, structured_call
from agentproof.models import JUDGE, SIM_USER
from tests.fakes import FakeLLM, parsed, validation_error


class Answer(BaseModel):
    value: int


def call(client, settings=JUDGE, validate=lambda a: a.value):
    return structured_call(
        client, settings, system="sistema", prompt="pregunta", output_type=Answer, validate=validate
    )


def test_sends_the_pinned_settings_and_the_structure():
    client = FakeLLM(parsed(Answer(value=7)))
    assert call(client) == 7
    request = client.messages.calls[0]
    assert request["model"] == JUDGE.model and request["max_tokens"] == JUDGE.max_tokens
    assert request["output_config"] == {"effort": "high"}
    assert request["output_format"] is Answer
    assert request["system"] == "sistema"
    assert request["messages"] == [{"role": "user", "content": "pregunta"}]


def test_no_effort_is_sent_when_the_model_does_not_accept_it():
    client = FakeLLM(parsed(Answer(value=1)))
    call(client, settings=SIM_USER)
    assert "output_config" not in client.messages.calls[0]


@pytest.mark.parametrize(
    "first",
    [
        parsed(None, stop_reason="refusal"),
        parsed(None, stop_reason="max_tokens"),
        parsed(None),
        validation_error(),
    ],
)
def test_one_bad_answer_is_retried(first):
    client = FakeLLM(first, parsed(Answer(value=3)))
    assert call(client) == 3
    assert len(client.messages.calls) == 2


def test_a_failed_validation_is_retried():
    def at_least_ten(answer):
        if answer.value < 10:
            raise ValueError("muy pequeño")
        return answer.value

    client = FakeLLM(parsed(Answer(value=1)), parsed(Answer(value=12)))
    assert call(client, validate=at_least_ten) == 12


def test_two_bad_answers_raise_with_the_reasons():
    client = FakeLLM(parsed(None, stop_reason="refusal"), validation_error())
    with pytest.raises(LLMCallError, match="refusal"):
        call(client)
