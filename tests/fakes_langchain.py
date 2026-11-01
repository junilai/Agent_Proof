"""A scripted LangChain chat model, for testing LangChain-based editions without any API."""

import uuid
from collections.abc import Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field

from agentproof.models import TARGET_BASELINE_MODEL

USAGE = {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}


def say(text: str) -> AIMessage:
    return AIMessage(content=text)


def ask_tools(*calls: tuple[str, dict[str, Any]]) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": args, "id": f"call_{uuid.uuid4().hex[:12]}"}
            for name, args in calls
        ],
    )


class ScriptedChatModel(BaseChatModel):
    """Answers with its responses in order; an `Exception` among them is raised.

    `model` reaches `invocation_params["model"]`, as with `ChatAnthropic`, while the
    response carries a dated id on purpose, so prices cannot silently come from it.
    """

    model: str = TARGET_BASELINE_MODEL
    responses: list[Any]  # AIMessage | Exception; Any so pydantic leaves exceptions alone
    repeat_last: bool = False
    calls: list[list[BaseMessage]] = Field(default_factory=list)
    bound_tools: list[str] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model": self.model}

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ScriptedChatModel":
        self.bound_tools = [convert_to_openai_tool(t)["function"]["name"] for t in tools]
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        index = len(self.calls)
        self.calls.append(list(messages))
        if index >= len(self.responses) and not self.repeat_last:
            raise AssertionError(f"no scripted response for call {index + 1}")
        response = self.responses[min(index, len(self.responses) - 1)]
        if isinstance(response, Exception):
            raise response
        tool_calls = [
            {**call, "id": f"call_{uuid.uuid4().hex[:12]}"}
            if index >= len(self.responses)
            else call
            for call in response.tool_calls
        ]
        message = AIMessage(
            content=response.content,
            tool_calls=tool_calls,
            id=f"run-{uuid.uuid4().hex[:12]}",
            usage_metadata=USAGE,
            response_metadata={"model_name": self.model + "-20261001"},
        )
        return ChatResult(generations=[ChatGeneration(message=message)])
