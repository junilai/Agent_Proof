"""Live check of the Claude Agent SDK edition and its isolation from the machine.

Excluded by default and never run in CI. Run by hand with:
    uv run --env-file .env pytest -m live -s tests/test_live_agent.py
"""

import asyncio
import dataclasses
import os

import pytest
from claude_agent_sdk import ClaudeSDKClient

from agentproof.adapters.claude_sdk import ClaudeSDKSession, turn_from_messages
from casestudy.editions.claude_sdk import build_options

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="sin ANTHROPIC_API_KEY"),
]

CANARY = "MANZANA-42"
CANARY_FACT = f"La palabra del día es {CANARY}."
NEUTRAL_PROMPT = "Eres un asistente útil. Responde en español."
COSTS: list[float] = []


def talk(options, message):
    async def go():
        async with ClaudeSDKSession(options) as session:
            return await session.send(message)

    turn = asyncio.run(go())
    COSTS.append(turn.usage.cost_usd if turn.usage else 0.0)
    print(f"\nAGENTE ({turn.stop_reason}): {turn.reply}")
    return turn


def ask_in(workdir, config, options, question):
    """Like a session, but in a working directory chosen by the test."""

    async def go():
        env = {**options.env, "CLAUDE_CONFIG_DIR": str(config)}
        async with ClaudeSDKClient(dataclasses.replace(options, cwd=workdir, env=env)) as client:
            await client.query(question)
            return turn_from_messages([m async for m in client.receive_response()])

    turn = asyncio.run(go())
    COSTS.append(turn.usage.cost_usd if turn.usage else 0.0)
    print(f"\nAGENTE ({turn.stop_reason}): {turn.reply}")
    return turn


def test_a_real_refund_turn():
    turn = talk(
        build_options(),
        "Hola, mis audífonos del pedido AT-1001 llegaron dañados y quiero que me devuelvan "
        "el dinero.",
    )
    tools = [e.tool for e in turn.events if e.kind == "tool_call"]
    assert turn.stop_reason == "completed"
    assert "lookup_order" in tools and "get_refund_policy" in tools
    reply = turn.reply.lower()
    assert "procede" in reply or "aprobad" in reply
    assert turn.usage.cost_usd > 0


def test_the_real_step_limit():
    options = dataclasses.replace(build_options(), max_turns=1)
    turn = talk(options, "Quiero devolver la laptop del pedido AT-1002, ya no la quiero.")
    assert turn.stop_reason == "step_limit"


def test_the_agent_never_reads_instruction_files(tmp_path):
    """Canary with a positive control.

    An instruction file in the working directory, under the name the SDK reads,
    states a fact the agent cannot otherwise know. Both runs use the agent's
    options with a neutral system prompt and differ only in ``setting_sources``,
    the layer that decides whether instruction files are loaded: the control loads
    the project settings and must report the fact, which proves the canary can be
    detected; the agent's own isolation must not. The model is asked directly for
    the file, because the store persona hides off-topic facts and instructions
    found in files are often not obeyed.
    """
    project = tmp_path / "proyecto"
    project.mkdir()
    (project / "CLAUDE.md").write_text(CANARY_FACT + "\n", encoding="utf-8")
    question = (
        "¿Hay contenido de un archivo CLAUDE.md en tu contexto? Si lo hay, cópialo "
        "literalmente; si no, responde NINGUNO."
    )
    agent = dataclasses.replace(build_options(), system_prompt=NEUTRAL_PROMPT)
    control = dataclasses.replace(agent, setting_sources=["project"])
    revealed = ask_in(project, tmp_path / "config-control", control, question)
    isolated = ask_in(project, tmp_path / "config-agente", agent, question)
    assert CANARY in revealed.reply, "el control no vio el canario: la prueba no discrimina"
    assert CANARY not in isolated.reply


def test_zz_cost_report():
    print(f"\nCOSTO TOTAL: USD {sum(COSTS):.4f} en {len(COSTS)} turnos")
    assert COSTS
