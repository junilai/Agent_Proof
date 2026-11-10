"""Case-study agent, LangGraph edition.

A plain LangGraph application: the framework-free domain wrapped as LangChain
tools, with its own loop on ``StateGraph``. It knows nothing about AgentProof.
Each variant applies one mutation from the shared domain definition (D1–D6);
a step is one model call, as with ``max_turns`` in the Claude Agent SDK edition.
"""

from typing import Annotated, Any, Literal, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage, SystemMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from casestudy.domain.mutations import MUTATIONS, Mutation
from casestudy.domain.prompt import system_prompt
from casestudy.domain.tools import TOOL_DESCRIPTIONS, create_ticket, get_refund_policy, lookup_order

VARIANTS = tuple(MUTATIONS)
STEP_LIMIT = 10
D6_STEP_LIMIT = 2
"""Model calls per turn under D6, calibrated for this framework (D-003, LangGraph addendum)."""
MAX_TOKENS = 32000
"""Output tokens per model call, the same for every variant (D-012)."""
REQUEST_TIMEOUT = 600.0
"""Seconds per model call; without it ChatAnthropic would wait forever on a hung call."""


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    model_calls: int
    step_limit_reached: bool


def step_limit(mutation: Mutation) -> int:
    return D6_STEP_LIMIT if mutation.step_limit is not None else STEP_LIMIT


def tools_for(mutation: Mutation) -> list[BaseTool]:
    """The agent's tools under a mutation: D1 removes one, D4 changes what one returns."""

    def lookup(order_id: str) -> dict[str, Any]:
        return lookup_order(order_id)

    def refund_policy() -> str:
        return get_refund_policy(mutation.policy)

    def ticket(summary: str, order_id: str) -> dict[str, str]:
        return create_ticket(summary, order_id)

    functions = {
        "lookup_order": lookup,
        "get_refund_policy": refund_policy,
        "create_ticket": ticket,
    }
    return [
        StructuredTool.from_function(function, name=name, description=TOOL_DESCRIPTIONS[name])
        for name, function in functions.items()
        if name not in mutation.removed_tools
    ]


def default_model(mutation: Mutation) -> BaseChatModel:
    """The variant's model, without extended thinking and with the default temperature."""
    return ChatAnthropic(model=mutation.model, max_tokens=MAX_TOKENS, timeout=REQUEST_TIMEOUT)


def builder(variant: str = "baseline", model: BaseChatModel | None = None) -> StateGraph:
    """The agent for a variant, uncompiled: whoever runs it adds its own checkpointer.

    The step counter restarts in ``start`` on every customer turn. The cut is
    decided only after ``tools``, so every tool call in the history has its result.
    The system prompt goes in front of each call and is never stored in the state.
    A tool that raises gives the model an error result, and the turn goes on.
    """
    if variant not in MUTATIONS:
        raise ValueError(f"unknown variant: {variant}")
    mutation = MUTATIONS[variant]
    tools = tools_for(mutation)
    limit = step_limit(mutation)
    prompt = SystemMessage(system_prompt(mutation))
    llm = (model or default_model(mutation)).bind_tools(tools)

    def start(state: AgentState) -> dict[str, Any]:
        return {"model_calls": 0, "step_limit_reached": False}

    def call_model(state: AgentState) -> dict[str, Any]:
        reply = llm.invoke([prompt, *state["messages"]])
        return {"messages": [reply], "model_calls": state["model_calls"] + 1}

    def cut(state: AgentState) -> dict[str, Any]:
        return {"step_limit_reached": True}

    def after_model(state: AgentState) -> Literal["tools", "__end__"]:
        return "tools" if state["messages"][-1].tool_calls else END

    def after_tools(state: AgentState) -> Literal["model", "cut"]:
        return "cut" if state["model_calls"] >= limit else "model"

    graph = StateGraph(AgentState)
    graph.add_node("start", start)
    graph.add_node("model", call_model)
    graph.add_node("tools", ToolNode(tools, handle_tool_errors=True))
    graph.add_node("cut", cut)
    graph.add_edge(START, "start")
    graph.add_edge("start", "model")
    graph.add_conditional_edges("model", after_model)
    graph.add_conditional_edges("tools", after_tools)
    graph.add_edge("cut", END)
    return graph
