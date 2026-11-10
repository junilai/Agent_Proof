"""The CrewAI edition with CrewAI's real Anthropic provider, against a fake Messages API.

Nothing leaves the machine: both Anthropic clients get an in-memory transport,
and every socket is refused. These tests pin what CrewAI sends and what it drops,
which a scripted LLM cannot show.
"""

import asyncio
import json
import uuid

import httpx2
import pytest
from anthropic import Anthropic, AsyncAnthropic

from agentproof.adapters.crewai import CrewAISession
from casestudy.domain.mutations import MUTATIONS
from casestudy.domain.prompt import system_prompt
from casestudy.domain.tools import TOOL_DESCRIPTIONS
from casestudy.editions.crewai import D6_STEP_LIMIT, MAX_TOKENS, builder, default_model
from tests.fakes_crewai import offline

USAGE = {
    "input_tokens": 100,
    "output_tokens": 20,
    "cache_creation_input_tokens": 7,
    "cache_read_input_tokens": 3,
}


@pytest.fixture(autouse=True)
def network(monkeypatch):
    return offline(monkeypatch)


def text(value):
    return {"type": "text", "text": value}


def use(name, arguments):
    return {
        "type": "tool_use",
        "id": f"toolu_{uuid.uuid4().hex[:12]}",
        "name": name,
        "input": arguments,
    }


class FakeMessagesAPI:
    """Answers each request with the next scripted content and records the request body."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request):
        body = json.loads(request.content)
        self.requests.append(body)
        content = self.responses.pop(0)
        stop = "tool_use" if any(block["type"] == "tool_use" for block in content) else "end_turn"
        return httpx2.Response(
            200,
            json={
                "id": f"msg_{len(self.requests)}",
                "type": "message",
                "role": "assistant",
                "model": body["model"] + "-20261001",
                "content": content,
                "stop_reason": stop,
                "stop_sequence": None,
                "usage": USAGE,
            },
        )

    def model(self, variant):
        """The edition's own model for the variant, talking to this fake API."""
        llm = default_model(MUTATIONS[variant])
        llm.api_key = "test-key"
        params = llm._get_client_params(include_http_client=False)
        transport = httpx2.MockTransport(self)
        llm._client = Anthropic(**params, http_client=httpx2.Client(transport=transport))
        llm._async_client = AsyncAnthropic(
            **params, http_client=httpx2.AsyncClient(transport=transport)
        )
        return llm


def _talk(variant, api, *messages):
    async def run():
        async with CrewAISession(builder(variant, model=api.model(variant))) as session:
            return [await session.send(m) for m in messages]

    return asyncio.run(run())


def test_the_request_carries_the_domain_tools_prompt_and_limits(network):
    api = FakeMessagesAPI([text("Hola.")])
    [turn] = _talk("baseline", api, "hola")
    [request] = api.requests
    assert request["model"] == MUTATIONS["baseline"].model
    assert request["max_tokens"] == MAX_TOKENS
    assert "thinking" not in request
    assert {t["name"]: t["description"] for t in request["tools"]} == TOOL_DESCRIPTIONS
    system = "".join(block["text"] for block in request["system"])
    assert system_prompt(MUTATIONS["baseline"]) in system
    assert turn.reply == "Hola."
    assert network == []


def test_crewai_sends_strict_tools_and_its_react_stop_sequence():
    """Framework defaults the other editions do not send; declared, not changed."""
    api = FakeMessagesAPI([text("Hola.")])
    _talk("baseline", api, "hola")
    [request] = api.requests
    assert all(tool["strict"] is True for tool in request["tools"])
    assert request["stop_sequences"] == ["\nObservation:"]


def test_text_written_next_to_a_tool_call_never_reaches_the_customer():
    """CrewAI drops it, unlike the other editions; the trace shows what the customer saw."""
    api = FakeMessagesAPI(
        [text("Voy a revisar tu pedido."), use("lookup_order", {"order_id": "AT-1001"})],
        [text("Fue entregado.")],
    )
    [turn] = _talk("baseline", api, "¿Y mi pedido?")
    assert [e.kind for e in turn.events] == ["tool_call", "agent_message"]
    assert turn.reply == "Fue entregado."
    assert "Voy a revisar" not in json.dumps(api.requests[1], ensure_ascii=False)


def test_the_forced_answer_is_requested_without_tools():
    api = FakeMessagesAPI(
        *[[use("get_refund_policy", {})] for _ in range(D6_STEP_LIMIT)],
        [text("Te resumo la política.")],
    )
    [turn] = _talk("d6", api, "¿Cuál es la política?")
    assert turn.stop_reason == "step_limit"
    assert turn.reply == "Te resumo la política."
    forced = api.requests[-1]
    assert len(api.requests) == D6_STEP_LIMIT + 1
    assert "tools" not in forced
    assert forced["messages"][-1]["role"] == "user"


def test_input_tokens_include_the_cached_ones():
    """CrewAI always marks cache breakpoints: the console, not this price, is the cost."""
    api = FakeMessagesAPI([text("Hola.")])
    [turn] = _talk("baseline", api, "hola")
    assert "cache_control" in json.dumps(api.requests[0])
    assert (turn.usage.input_tokens, turn.usage.output_tokens) == (110, 20)
