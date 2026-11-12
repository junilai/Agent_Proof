"""A scripted CrewAI LLM, for testing the CrewAI edition without any API."""

import socket
import uuid
from typing import Any

import pytest
from crewai.llms.base_llm import BaseLLM
from pydantic import Field, model_validator

from agentproof.models import TARGET_BASELINE_MODEL

USAGE = {"input_tokens": 100, "output_tokens": 20}
TELEMETRY_OFF = {
    "CREWAI_DISABLE_TELEMETRY": "true",
    "CREWAI_DISABLE_TRACKING": "true",
    "OTEL_SDK_DISABLED": "true",
    "CREWAI_TRACING_ENABLED": "false",
    "CREWAI_TESTING": "true",
}


def say(text: str) -> str:
    return text


def ask_tools(*calls: tuple[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """One model response asking for tools, in the shape CrewAI's native providers return."""
    return [
        {"id": f"toolu_{uuid.uuid4().hex[:12]}", "name": name, "input": args}
        for name, args in calls
    ]


def offline(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Telemetry and tracing off, and every socket connection refused and recorded."""
    for var, value in TELEMETRY_OFF.items():
        monkeypatch.setenv(var, value)
    attempts: list[Any] = []

    def refuse(self: socket.socket, address: Any) -> None:
        attempts.append(address)
        raise OSError(f"network blocked in tests: {address}")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    return attempts


class ScriptedLLM(BaseLLM):
    """Answers with its responses in order: a list asks for tools, a str is the final text.

    An ``Exception`` among them is raised. ``model`` is the id the agent requested,
    as with CrewAI's Anthropic provider, which strips the ``anthropic/`` prefix.
    Every answered call reports the same usage.
    """

    llm_type: str = "scripted"
    provider: str = "anthropic"
    model: str = TARGET_BASELINE_MODEL
    responses: list[Any] = Field(default_factory=list)  # Any so pydantic leaves exceptions alone
    repeat_last: bool = False
    calls: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _default_model(cls, data: Any) -> Any:
        """BaseLLM checks the model before field defaults apply."""
        if isinstance(data, dict) and not data.get("model"):
            return {**data, "model": TARGET_BASELINE_MODEL}
        return data

    def call(
        self,
        messages: Any,
        tools: list[dict[str, Any]] | None = None,
        callbacks: Any = None,
        available_functions: Any = None,
        from_task: Any = None,
        from_agent: Any = None,
        response_model: Any = None,
    ) -> Any:
        index = len(self.calls)
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        self.calls.append(
            {
                "messages": [dict(m) for m in messages],
                "tools": [t.get("function", t).get("name") for t in tools or []],
            }
        )
        if index >= len(self.responses) and not self.repeat_last:
            raise AssertionError(f"no scripted response for call {index + 1}")
        response = self.responses[min(index, len(self.responses) - 1)]
        if isinstance(response, Exception):
            raise response
        self._track_token_usage_internal(dict(USAGE))
        if isinstance(response, list) and index >= len(self.responses):
            return [{**call, "id": f"toolu_{uuid.uuid4().hex[:12]}"} for call in response]
        return response

    def supports_function_calling(self) -> bool:
        return True
