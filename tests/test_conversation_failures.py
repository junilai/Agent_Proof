import asyncio

from agentproof.conversation import converse
from agentproof.session import AgentEvent, AgentTurn
from tests.fakes import RUN, SEED, CrashingSession, EchoSession, ScriptedUser, ticking_clock


def talk(user, factory, context=RUN):
    return asyncio.run(converse(factory, user, context, clock=ticking_clock()))


class StepLimitSession(EchoSession):
    async def send(self, message):
        call = AgentEvent(kind="tool_call", tool="lookup_order", arguments={}, result={})
        return AgentTurn(reply="", events=[call], stop_reason="step_limit")


class ErrorTurnSession(EchoSession):
    async def send(self, message):
        failure = AgentEvent(kind="error", text="fallo")
        return AgentTurn(reply="", events=[failure], stop_reason="error")


class UnopenableSession(EchoSession):
    async def __aenter__(self):
        raise ConnectionError("no se pudo iniciar el agente")


class NoisyCloseSession(EchoSession):
    async def __aexit__(self, *exc_info):
        raise RuntimeError("error al cerrar")


class MalformedSession(EchoSession):
    async def send(self, message):
        return None


class SilentUser(ScriptedUser):
    async def first_message(self):
        raise TimeoutError("el simulador no respondió")


class UserFailingLater(ScriptedUser):
    async def next_message(self, history):
        raise TimeoutError("el simulador no respondió")


def kinds(trace):
    return [e.kind for e in trace.events]


def test_agent_exception_is_an_agent_error():
    trace = talk(ScriptedUser("hola", "otra"), CrashingSession)
    assert trace.termination == "agent_error"
    assert kinds(trace) == ["user_message", "error"]
    assert "se cayó la conexión" in trace.events[-1].text


def test_step_limit_ends_the_conversation_without_asking_the_user():
    user = ScriptedUser("hola", "sigue")
    trace = talk(user, StepLimitSession)
    assert trace.termination == "step_limit"
    assert user.seen == []


def test_failed_turn_is_an_agent_error():
    assert talk(ScriptedUser("hola"), ErrorTurnSession).termination == "agent_error"


def test_session_that_cannot_open_is_an_agent_error():
    trace = talk(ScriptedUser("hola"), UnopenableSession)
    assert trace.termination == "agent_error"
    assert kinds(trace) == ["error"]


def test_malformed_turn_is_an_agent_error():
    assert talk(ScriptedUser("hola"), MalformedSession).termination == "agent_error"


def test_failure_when_closing_is_recorded_but_keeps_the_outcome():
    trace = talk(ScriptedUser("hola"), NoisyCloseSession, SEED)
    assert trace.termination == "user_ended"
    assert kinds(trace)[-1] == "error"


def test_simulator_failure_before_starting_never_opens_the_session():
    opened = []
    trace = talk(SilentUser(), lambda: opened.append(1) or EchoSession())
    assert trace.termination == "simulator_error"
    assert kinds(trace) == ["error"] and opened == []


def test_simulator_failure_mid_conversation_is_a_simulator_error():
    trace = talk(UserFailingLater("hola"), EchoSession)
    assert trace.termination == "simulator_error"
    assert kinds(trace) == ["user_message", "tool_call", "agent_message", "error"]
