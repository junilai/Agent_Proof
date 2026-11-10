"""The local console of the CrewAI edition: CrewAI has no Studio for a single agent."""

import asyncio
import os
import runpy
from pathlib import Path

import pytest

from agentproof.adapters.crewai import TELEMETRY_VARS, TRACING_VAR
from casestudy.domain.mutations import MUTATIONS
from casestudy.domain.tools import lookup_order
from casestudy.editions.crewai import D6_STEP_LIMIT
from tests.fakes_crewai import ScriptedLLM, ask_tools, offline, say

CONSOLE = Path(__file__).resolve().parents[1] / "studio" / "crewai" / "console.py"


@pytest.fixture
def console(monkeypatch):
    attempts = offline(monkeypatch)
    for var in (*TELEMETRY_VARS, TRACING_VAR):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("VARIANT", raising=False)
    module = runpy.run_path(str(CONSOLE), run_name="console")
    yield module
    assert attempts == []


def _chat(console, llm, *lines, variant=None):
    shown = []
    session = console["build_session"](variant, model=llm)
    asyncio.run(console["chat"](session, iter(lines), shown.append))
    return "\n".join(shown)


def test_the_console_turns_telemetry_and_tracing_off(console):
    assert all(os.environ[var] == "true" for var in TELEMETRY_VARS)
    assert os.environ[TRACING_VAR] == "false"


def test_the_console_builds_the_edition_of_the_variant(console, monkeypatch):
    assert console["build_session"](model=ScriptedLLM()).agent.max_iter == 10
    monkeypatch.setenv("VARIANT", "d6")
    assert console["build_session"](model=ScriptedLLM()).agent.max_iter == D6_STEP_LIMIT
    assert console["build_session"]().agent.llm.model == MUTATIONS["baseline"].model


def test_the_console_drives_one_scripted_turn(console):
    lookup = ask_tools(("lookup_order", {"order_id": "AT-1001"}))
    shown = _chat(console, ScriptedLLM(responses=[lookup, say("Fue entregado.")]), "¿Y mi pedido?")
    assert 'lookup_order {"order_id": "AT-1001"}' in shown
    assert lookup_order("AT-1001")["producto"] in shown
    assert "Fue entregado." in shown
    assert "completed" in shown and "1 llamada" in shown


def test_the_console_shows_the_cut(console):
    policy = ask_tools(("get_refund_policy", {}))
    llm = ScriptedLLM(responses=[*[policy] * D6_STEP_LIMIT, say("Forzada.")])
    shown = _chat(console, llm, "¿Cuál es la política?", variant="d6")
    assert "step_limit" in shown and f"límite: {D6_STEP_LIMIT}" in shown
    assert "Forzada." in shown
