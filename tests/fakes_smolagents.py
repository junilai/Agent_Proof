"""A scripted smolagents model, for testing the smolagents edition without any API."""

import uuid
from typing import Any

from smolagents import Model
from smolagents.models import (
    ChatMessage,
    ChatMessageToolCall,
    ChatMessageToolCallFunction,
    MessageRole,
)
from smolagents.monitoring import TokenUsage

from agentproof.models import TARGET_BASELINE_MODEL

INPUT_TOKENS, OUTPUT_TOKENS = 100, 20


def _call(name: str, arguments: dict[str, Any]) -> ChatMessageToolCall:
    return ChatMessageToolCall(
        id=f"call_{uuid.uuid4().hex[:12]}",
        type="function",
        function=ChatMessageToolCallFunction(name=name, arguments=dict(arguments)),
    )


def ask_tools(*calls: tuple[str, dict[str, Any]]) -> ChatMessage:
    return ChatMessage(
        role=MessageRole.ASSISTANT,
        content="",
        tool_calls=[_call(name, args) for name, args in calls],
    )


def say(text: str) -> ChatMessage:
    """A reply, the way a tool-calling smolagents agent gives one: through ``final_answer``."""
    return ask_tools(("final_answer", {"answer": text}))


def plain(text: str) -> ChatMessage:
    """Text without a tool call: what the forced answer after ``max_steps`` gets."""
    return ChatMessage(role=MessageRole.ASSISTANT, content=text)


def text_of(message: ChatMessage) -> str:
    content = message.content
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict))
    return content or ""


class ScriptedModel(Model):
    """Answers with its responses in call order; an `Exception` among them is raised.

    ``model_id`` is the model the edition requests, as with ``LiteLLMModel``, while
    the response carries a dated id on purpose, so prices cannot silently come from it.
    ``calls`` keeps the messages of every call and ``tools`` the tool names sent with it.
    """

    def __init__(
        self,
        responses: list[Any],
        model_id: str = TARGET_BASELINE_MODEL,
        repeat_last: bool = False,
    ) -> None:
        super().__init__(model_id=model_id)
        self.responses = list(responses)
        self.repeat_last = repeat_last
        self.calls: list[list[ChatMessage]] = []
        self.tools: list[list[str]] = []

    def generate(
        self,
        messages: list[ChatMessage],
        stop_sequences: list[str] | None = None,
        response_format: dict[str, str] | None = None,
        tools_to_call_from: list[Any] | None = None,
        **kwargs: Any,
    ) -> ChatMessage:
        index = len(self.calls)
        self.calls.append(list(messages))
        self.tools.append([t.name for t in tools_to_call_from or []])
        if index >= len(self.responses) and not self.repeat_last:
            raise AssertionError(f"no scripted response for call {index + 1}")
        response = self.responses[min(index, len(self.responses) - 1)]
        if isinstance(response, Exception):
            raise response
        calls = [_call(c.function.name, c.function.arguments) for c in response.tool_calls or []]
        return ChatMessage(
            role=MessageRole.ASSISTANT,
            content=response.content,
            tool_calls=calls or None,
            raw={"model": self.model_id.removeprefix("anthropic/") + "-20261001"},
            token_usage=TokenUsage(input_tokens=INPUT_TOKENS, output_tokens=OUTPUT_TOKENS),
        )
