import asyncio
import json
import os

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from agentproof.adapters.claude_sdk import (
    ClaudeSDKSession,
    session_factory,
    tool_name,
    turn_from_messages,
)
from agentproof.schema import Usage

LOOKUP = {"pedido": "AT-1001", "estado": "entregado", "dias_desde_entrega": 10}


def result(subtype="success", is_error=False, terminal_reason="completed", errors=None):
    return ResultMessage(
        subtype=subtype,
        duration_ms=1000,
        duration_api_ms=900,
        is_error=is_error,
        num_turns=2,
        session_id="s",
        total_cost_usd=0.0104,
        usage={
            "input_tokens": 4,
            "output_tokens": 400,
            "cache_read_input_tokens": 1314,
            "cache_creation_input_tokens": 2061,
        },
        terminal_reason=terminal_reason,
        errors=errors,
    )


def lookup_messages():
    return [
        AssistantMessage(
            content=[
                TextBlock("Voy a revisar su pedido."),
                ToolUseBlock("toolu_1", "mcp__store__lookup_order", {"order_id": "AT-1001"}),
            ],
            model="claude-sonnet-5",
        ),
        UserMessage(
            content=[ToolResultBlock("toolu_1", [{"type": "text", "text": json.dumps(LOOKUP)}])]
        ),
        AssistantMessage(content=[TextBlock("Su reembolso procede.")], model="claude-sonnet-5"),
    ]


def test_tool_names_lose_the_mcp_prefix():
    assert tool_name("mcp__store__lookup_order") == "lookup_order"
    assert tool_name("lookup_order") == "lookup_order"


def test_a_completed_turn():
    turn = turn_from_messages([*lookup_messages(), result()])
    assert turn.stop_reason == "completed"
    assert turn.reply == "Voy a revisar su pedido.\nSu reembolso procede."
    assert [e.kind for e in turn.events] == ["agent_message", "tool_call", "agent_message"]
    call = turn.events[1]
    assert (call.tool, call.arguments, call.result) == (
        "lookup_order",
        {"order_id": "AT-1001"},
        LOOKUP,
    )
    assert turn.usage == Usage(input_tokens=3379, output_tokens=400, cost_usd=0.0104)


def test_the_step_limit_is_not_an_error():
    turn = turn_from_messages(
        [*lookup_messages()[:2], result("error_max_turns", True, "max_turns", ["Reached max"])]
    )
    assert turn.stop_reason == "step_limit"
    assert [e.kind for e in turn.events] == ["agent_message", "tool_call"]


def test_other_failures_are_errors_with_their_reason():
    turn = turn_from_messages([result("error_during_execution", True, None, ["boom"])])
    assert turn.stop_reason == "error"
    assert turn.events[-1].kind == "error" and "boom" in turn.events[-1].text


def test_a_failed_tool_and_an_assistant_error_are_recorded():
    messages = [
        AssistantMessage(content=[ToolUseBlock("t2", "mcp__store__lookup_order", {})], model="m"),
        UserMessage(content=[ToolResultBlock("t2", "falló", is_error=True)]),
        AssistantMessage(content=[], model="m", error="rate_limit"),
        result(),
    ]
    turn = turn_from_messages(messages)
    assert turn.events[0].is_error and turn.events[0].result == "falló"
    assert turn.events[1].kind == "error" and "rate_limit" in turn.events[1].text


def test_an_api_error_reports_its_http_status():
    failed = result("success", True, None)
    failed.api_error_status = 529
    turn = turn_from_messages([failed])
    assert turn.stop_reason == "error" and "HTTP 529" in turn.events[-1].text


def test_a_stream_without_result_is_an_error():
    turn = turn_from_messages(lookup_messages())
    assert turn.stop_reason == "error" and turn.events[-1].kind == "error"


class FakeSDKClient:
    def __init__(self, options):
        self.options, self.queries, self.connected = options, [], False
        self.dirs_during_session = []

    async def connect(self):
        self.connected = True

    async def query(self, prompt):
        self.queries.append(prompt)
        self.dirs_during_session = [
            os.path.isdir(self.options.cwd),
            os.path.isdir(self.options.env["CLAUDE_CONFIG_DIR"]),
        ]

    async def receive_response(self):
        for message in [*lookup_messages(), result()]:
            yield message

    async def disconnect(self):
        self.connected = False


def test_each_session_runs_isolated_and_cleans_up():
    clients = []

    def factory(options):
        clients.append(FakeSDKClient(options))
        return clients[-1]

    async def talk():
        options = ClaudeAgentOptions(model="claude-sonnet-5", env={"OTRA": "1"})
        async with ClaudeSDKSession(options, client_factory=factory) as session:
            return await session.send("hola")

    turn = asyncio.run(talk())
    client = clients[0]
    assert turn.reply.endswith("Su reembolso procede.") and client.queries == ["hola"]
    assert client.dirs_during_session == [True, True]
    assert client.options.env["OTRA"] == "1"
    assert not os.path.exists(client.options.cwd)
    assert not os.path.exists(client.options.env["CLAUDE_CONFIG_DIR"])
    assert not client.connected


def test_session_factory_builds_the_agent_of_the_variant():
    seen = []

    def build(variant):
        seen.append(variant)
        return ClaudeAgentOptions(model="m")

    session = session_factory(build, "baseline")()
    assert isinstance(session, ClaudeSDKSession) and seen == ["baseline"]


def test_a_failed_connection_leaves_nothing_behind():
    clients = []

    class RefusingClient(FakeSDKClient):
        async def connect(self):
            raise ConnectionError("sin CLI")

    def factory(options):
        clients.append(RefusingClient(options))
        return clients[-1]

    async def talk():
        async with ClaudeSDKSession(ClaudeAgentOptions(model="m"), client_factory=factory):
            pass

    with pytest.raises(ConnectionError):
        asyncio.run(talk())
    assert not os.path.exists(clients[0].options.cwd)
    assert not os.path.exists(clients[0].options.env["CLAUDE_CONFIG_DIR"])
