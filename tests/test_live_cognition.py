"""Live check of the three LLM stages against the real Anthropic API.

Excluded by default and never run in CI. Run by hand with:
    uv run --env-file .env pytest -m live -s
"""

import asyncio
import os

import anthropic
import pytest

from agentproof.conversation import Exchange
from agentproof.induction import induce_scenario
from agentproof.judge import judge_trace
from agentproof.models import INDUCER, JUDGE, SIM_USER
from agentproof.simulator import SimulatedUser
from casestudy.domain.tools import get_refund_policy, lookup_order
from tests.factories import RUN_FIELDS, event, trace

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="sin ANTHROPIC_API_KEY"),
]

PRICES = {INDUCER.model: (5, 25), SIM_USER.model: (1, 5)}  # USD per million tokens (in, out)
USAGE: list[tuple[str, int, int]] = []


class Recorder:
    """Wraps a real client and records the tokens of every response."""

    def __init__(self, client):
        self.client, self.messages = client, self

    def parse(self, **request):
        response = self.client.messages.parse(**request)
        USAGE.append((request["model"], response.usage.input_tokens, response.usage.output_tokens))
        return response

    async def create(self, **request):
        response = await self.client.messages.create(**request)
        USAGE.append((request["model"], response.usage.input_tokens, response.usage.output_tokens))
        return response


def seed_events():
    return [
        event(
            1,
            "user_message",
            text="Hola, me llegaron unos audífonos Sony dañados, uno de los "
            "lados no suena. Quiero que me devuelvan el dinero.",
        ),
        event(2, "agent_message", text="Lamento lo ocurrido. ¿Me indica su número de pedido?"),
        event(3, "user_message", text="Es el AT-1001"),
        event(
            4,
            "tool_call",
            tool="lookup_order",
            arguments={"order_id": "AT-1001"},
            result=lookup_order("AT-1001"),
        ),
        event(5, "tool_call", tool="get_refund_policy", arguments={}, result=get_refund_policy()),
        event(
            6,
            "agent_message",
            text="Revisé su pedido AT-1001: los audífonos se entregaron hace "
            "10 días, dentro de los 30 días de la política, así que su reembolso procede. "
            "Se reintegrarán $89.90 a su medio de pago.",
        ),
        event(7, "user_message", text="Perfecto, muchas gracias."),
        event(8, "agent_message", text="Con gusto. Que tenga un buen día."),
    ]


@pytest.fixture(scope="module")
def scenario():
    return induce_scenario(trace(events=seed_events()), client=Recorder(anthropic.Anthropic()))


def test_inducer_returns_a_spanish_scenario_with_two_to_five_criteria(scenario):
    print("\nESCENARIO:", scenario.model_dump_json(indent=2))
    assert 2 <= len(scenario.success_criteria) <= 5
    assert "AT-1001" in scenario.opening_message + scenario.user_goal


def test_simulated_user_answers_with_the_dated_haiku_identifier(scenario):
    user = SimulatedUser(scenario, client=Recorder(anthropic.AsyncAnthropic()))
    history = [Exchange(scenario.opening_message, "Lo siento. ¿Me indica su número de pedido?")]
    message = asyncio.run(user.next_message(history))
    print("\nUSUARIO SIMULADO:", message)
    assert isinstance(message, str) and message


def test_judge_grades_every_criterion(scenario):
    run = trace(
        kind="run", events=seed_events(), **{**RUN_FIELDS, "scenario_id": scenario.scenario_id}
    )
    verdict = judge_trace(scenario, run, client=Recorder(anthropic.Anthropic()))
    print("\nJUICIO:", verdict.model_dump_json(indent=2))
    assert len(verdict.criteria) == len(scenario.success_criteria)
    assert verdict.judged_by == JUDGE.model


def test_zz_cost_report():
    total = 0.0
    for model, tokens_in, tokens_out in USAGE:
        price_in, price_out = PRICES[model]
        cost = (tokens_in * price_in + tokens_out * price_out) / 1_000_000
        total += cost
        print(f"\n{model}: {tokens_in} in / {tokens_out} out -> USD {cost:.4f}")
    print(f"\nCOSTO TOTAL: USD {total:.4f}")
    assert USAGE
