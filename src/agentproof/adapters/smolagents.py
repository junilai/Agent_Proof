"""smolagents adapter: turns what an agent run yields in a turn into an agent turn.

The only module of AgentProof that imports ``smolagents``. The tool calls, their
results and the reply come from the run's event stream; the step limit and the
tokens come from the memory steps the run added, because the stream does not
yield the step of the forced answer. ``final_answer`` is how the agent replies,
so it is the turn's reply and never a tool call.

smolagents reports tokens but not cost, so the turn is priced with the dated
table in ``agentproof.pricing``, using the model the agent requests, never the id
the response carries. Hitting the step limit is a ``step_limit`` turn, not an
error, and the answer smolagents forces then is the turn's reply.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from smolagents.agents import ToolOutput
from smolagents.memory import ActionStep, FinalAnswerStep, ToolCall
from smolagents.utils import AgentMaxStepsError

from agentproof.pricing import PRICES
from agentproof.schema import Usage
from agentproof.session import AgentEvent, AgentTurn

FINAL_ANSWER = "final_answer"
FORCED_ANSWER_ERROR = "Error in generating final LLM output"
"""How smolagents words a model error during the forced answer, which it swallows."""


def _arguments(arguments: Any) -> dict[str, Any]:
    return arguments if isinstance(arguments, dict) else {"input": arguments}


def _value(output: Any) -> Any:
    return str(output) if isinstance(output, str) else output


def _text(output: Any) -> str:
    if isinstance(output, list):
        return "".join(b.get("text", "") for b in output if isinstance(b, dict))
    return "" if output is None else str(output)


def _usage(steps: Sequence[ActionStep], model: str | None) -> Usage:
    usages = [s.token_usage for s in steps if s.token_usage is not None]
    tokens_in = sum(u.input_tokens for u in usages)
    tokens_out = sum(u.output_tokens for u in usages)
    cost = None
    if model in PRICES:
        per_input, per_output = PRICES[model]
        cost = (tokens_in * per_input + tokens_out * per_output) / 1e6
    return Usage(input_tokens=tokens_in, output_tokens=tokens_out, cost_usd=cost)


def turn_from_run(events: Sequence[Any], steps: Sequence[Any], *, model: str | None) -> AgentTurn:
    """``events``: what ``run(stream=True)`` yielded; ``steps``: the memory steps it added.

    When a step fails, smolagents tells the model only the error, even if some of
    its tools already ran: each of that step's calls is then ``is_error``, with its
    result if the stream yielded one and the error otherwise.
    """
    out: list[AgentEvent] = []
    in_step: list[int] = []
    answered: set[int] = set()
    by_id: dict[str, int] = {}
    reply: Any = None
    for event in events:
        if isinstance(event, ToolCall) and event.name != FINAL_ANSWER:
            by_id[event.id] = len(out)
            in_step.append(len(out))
            out.append(
                AgentEvent(kind="tool_call", tool=event.name, arguments=_arguments(event.arguments))
            )
        elif isinstance(event, ToolOutput) and event.id in by_id:
            index = by_id[event.id]
            answered.add(index)
            out[index] = out[index].model_copy(update={"result": _value(event.output)})
        elif isinstance(event, ActionStep):
            if event.error is not None:
                for index in in_step:
                    update: dict[str, Any] = {"is_error": True}
                    if index not in answered:
                        update["result"] = str(event.error)
                    out[index] = out[index].model_copy(update=update)
            in_step = []
        elif isinstance(event, FinalAnswerStep):
            reply = event.output
    actions = [s for s in steps if isinstance(s, ActionStep)]
    usage = _usage(actions, model)
    text = _text(reply)
    if isinstance(reply, list) or text.startswith(FORCED_ANSWER_ERROR):
        out.append(AgentEvent(kind="error", text=text))
        return AgentTurn(reply="", events=out, stop_reason="error", usage=usage)
    if text:
        out.append(AgentEvent(kind="agent_message", text=text))
    cut = any(isinstance(s.error, AgentMaxStepsError) for s in actions)
    return AgentTurn(
        reply=text, events=out, stop_reason="step_limit" if cut else "completed", usage=usage
    )
