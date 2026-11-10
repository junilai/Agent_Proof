"""Live check of the LangGraph edition: each mutation produces the change it declares.

The mirror of test_live_mutations.py for this edition. Excluded by default and never
run in CI. Run by hand with:
    uv run --env-file .env pytest -m live -s tests/test_live_langgraph.py

Only the mechanism mutations (family A) and the baseline get assertions about what
the agent does; D2, D3 and D5 only have to converse, for the reason given there.
"""

import asyncio
import os

import pytest

from agentproof.adapters.langgraph import LangGraphSession
from casestudy.editions.langgraph import builder
from tests.test_live_mutations import GIFT_CARD, REFUND, WARRANTY

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="sin ANTHROPIC_API_KEY"),
]

COSTS: list[float] = []


def talk(variant, message):
    async def go():
        async with LangGraphSession(builder(variant)) as session:
            return await session.send(message)

    turn = asyncio.run(go())
    COSTS.append(turn.usage.cost_usd if turn.usage and turn.usage.cost_usd else 0.0)
    tools = [e.tool for e in turn.events if e.kind == "tool_call"]
    print(f"\n[{variant}] {turn.stop_reason} {tools}\n{turn.reply[:500]}")
    return turn, tools


def test_baseline_still_resolves_a_refund():
    turn, tools = talk("baseline", REFUND)
    assert turn.stop_reason == "completed"
    assert "lookup_order" in tools and "get_refund_policy" in tools
    assert turn.usage.cost_usd is not None


def test_d1_never_consults_the_order():
    turn, tools = talk("d1", "Hola, ¿en qué estado está mi pedido AT-1006?")
    assert turn.stop_reason == "completed" and "lookup_order" not in tools


def test_d4_states_the_corrupt_window():
    turn, tools = talk("d4", "¿Cuántos días tengo para devolver un producto después de recibirlo?")
    assert "get_refund_policy" in tools
    assert "90" in turn.reply and "30 días" not in turn.reply


def test_d6_truncates_only_the_conversations_of_three_calls():
    truncated, _ = talk("d6", WARRANTY)
    complete, _ = talk("d6", REFUND)
    assert truncated.stop_reason == "step_limit"
    assert complete.stop_reason == "completed"


@pytest.mark.parametrize("variant", ["d2", "d3", "d5"])
def test_the_propensity_mutations_still_converse(variant):
    turn, _ = talk(variant, GIFT_CARD)
    assert turn.stop_reason != "error" and turn.reply
    assert turn.usage.cost_usd is not None


def test_zz_cost_report():
    print(f"\nCOSTO TOTAL: USD {sum(COSTS):.4f} en {len(COSTS)} turnos")
    assert COSTS
