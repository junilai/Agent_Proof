import asyncio

from agentproof import models
from agentproof.conversation import Exchange, converse
from agentproof.schema import Usage
from tests.fakes import RUN, SEED, EchoSession, ScriptedUser, ticking_clock


def talk(user, context=SEED, factory=EchoSession, **options):
    options.setdefault("clock", ticking_clock())
    return asyncio.run(converse(factory, user, context, **options))


def test_records_the_whole_conversation_in_order():
    trace = talk(ScriptedUser("hola", "gracias"), model_config={"judge": "x"})
    kinds = [e.kind for e in trace.events]
    assert kinds == ["user_message", "tool_call", "agent_message"] * 2
    assert [e.step for e in trace.events] == [1, 2, 3, 4, 5, 6]
    assert trace.termination == "user_ended"
    assert trace.final_reply() == "eco: gracias"
    assert trace.usage == Usage(input_tokens=20, output_tokens=10, cost_usd=0.5)
    assert trace.models == {"judge": "x"}
    assert trace.started_at < trace.ended_at


def test_the_user_sees_messages_but_never_tool_calls():
    user = ScriptedUser("hola", "gracias")
    talk(user)
    assert user.seen[0] == [Exchange("hola", "eco: hola")]


def test_turn_budget_stops_the_conversation():
    trace = talk(ScriptedUser("1", "2", "3", "4"), RUN, turn_budget=2)
    assert trace.termination == "turn_budget"
    assert sum(e.kind == "user_message" for e in trace.events) == 2


def test_run_context_is_copied_into_the_trace():
    trace = talk(ScriptedUser("hola"), RUN)
    fields = (trace.kind, trace.condition, trace.run_id, trace.scenario_id, trace.repetition)
    assert fields == ("run", "baseline-a", "baseline-a-20261001-120000", "sc-tr-000000000001", 3)


def test_model_configuration_defaults_to_the_pinned_snapshot():
    assert talk(ScriptedUser("hola")).models == models.snapshot()


def test_the_session_is_closed():
    session = EchoSession()
    talk(ScriptedUser("hola"), factory=lambda: session)
    assert session.closed and session.sent == ["hola"]
