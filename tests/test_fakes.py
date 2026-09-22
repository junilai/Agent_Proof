import asyncio

from agentproof.conversation import Exchange
from agentproof.session import AgentSession
from tests.fakes import EchoSession, ScriptedUser, ticking_clock


def test_scripted_user_says_its_lines_and_then_ends():
    user = ScriptedUser("hola", "gracias")
    history = [Exchange("hola", "eco: hola")]
    assert asyncio.run(user.first_message()) == "hola"
    assert asyncio.run(user.next_message(history)) == "gracias"
    assert asyncio.run(user.next_message(history)) is None
    assert user.seen == [history, history]


def test_echo_session_is_a_session_that_echoes_and_uses_a_tool():
    session = EchoSession()
    assert isinstance(session, AgentSession)
    turn = asyncio.run(session.send("hola"))
    assert turn.reply == "eco: hola"
    assert [e.kind for e in turn.events] == ["tool_call", "agent_message"]


def test_ticking_clock_advances_one_second_per_call():
    clock = ticking_clock()
    assert (clock() - clock()).total_seconds() == -1
