import pytest
from pydantic import ValidationError

from agentproof.schema import Usage
from agentproof.session import AgentEvent, AgentSession, AgentTurn


class MinimalSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None

    async def send(self, message):
        return AgentTurn(reply=message)


def test_any_class_with_the_three_methods_is_a_session():
    assert isinstance(MinimalSession(), AgentSession)
    assert not isinstance(object(), AgentSession)


def test_turn_defaults_to_a_completed_turn_without_events():
    turn = AgentTurn(reply="Hola")
    assert (turn.events, turn.stop_reason, turn.usage) == ([], "completed", None)


def test_adapters_cannot_emit_user_messages():
    with pytest.raises(ValidationError):
        AgentEvent(kind="user_message", text="Hola")


def test_unknown_stop_reasons_are_rejected():
    with pytest.raises(ValidationError):
        AgentTurn(reply="", stop_reason="timeout")


def test_turn_carries_the_agent_usage():
    assert AgentTurn(reply="", usage=Usage(input_tokens=3)).usage.input_tokens == 3
