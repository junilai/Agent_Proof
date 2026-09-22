"""AgentProof command line: record | induce | run | judge | report.

The adapter is loaded by name (``claude_sdk`` -> ``agentproof.adapters.claude_sdk``,
or a full module path) and the agent by ``module:attribute``, so adding a
framework never requires changing this file (§5.7).
"""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import typer

from agentproof.conversation import Exchange, TraceContext, converse
from agentproof.induction import induce_missing, induce_scenario
from agentproof.schema import Scenario, Trace
from agentproof.session import SessionFactory
from agentproof.store import Store

app = typer.Typer(
    help="AgentProof: detección de regresiones en agentes basados en LLM.", no_args_is_help=True
)
DATA = typer.Option(Path("."), "--data", help="Carpeta que contiene corpus/ y results/.")
ADAPTER = typer.Option(..., "--adapter", help="Adaptador del framework, por ejemplo claude_sdk.")
AGENT = typer.Option(..., "--agent", help="Constructor del agente, como modulo:atributo.")
VARIANT = typer.Option("baseline", "--variant", help="Variante del agente.")


def load_object(path: str) -> Any:
    module, _, attribute = path.partition(":")
    if not attribute:
        raise typer.BadParameter(f"se esperaba modulo:atributo, se recibió {path!r}")
    return getattr(importlib.import_module(module), attribute)


def load_adapter(name: str) -> Any:
    return importlib.import_module(name if "." in name else f"agentproof.adapters.{name}")


def session_factory_for(adapter: str, agent: str, variant: str) -> SessionFactory:
    return load_adapter(adapter).session_factory(load_object(agent), variant)


class HumanUser:
    """A person at the terminal; an empty line ends the conversation."""

    def __init__(
        self,
        read: Callable[[str], str] = input,
        write: Callable[[str], None] = typer.echo,
    ) -> None:
        self.read, self.write = read, write

    async def first_message(self) -> str:
        while not (message := self.read("usted> ").strip()):
            pass
        return message

    async def next_message(self, history: Sequence[Exchange]) -> str | None:
        self.write(f"agente> {history[-1].agent}")
        try:
            return self.read("usted> ").strip() or None
        except EOFError:  # Ctrl+D also ends the conversation
            return None


def _induce(seed: Trace) -> Scenario:
    return induce_scenario(seed)


@app.command()
def record(adapter: str = ADAPTER, agent: str = AGENT, variant: str = VARIANT, data: Path = DATA):
    """Graba una conversación con una persona como traza semilla."""
    factory = session_factory_for(adapter, agent, variant)
    context = TraceContext(kind="seed", adapter=adapter, agent=agent, variant=variant)
    typer.echo("Escriba sus mensajes. Una línea vacía termina la conversación.")
    trace = asyncio.run(converse(factory, HumanUser(), context))
    if not any(event.kind == "user_message" for event in trace.events):
        typer.echo("No se guardó nada: la conversación no tiene mensajes.", err=True)
        raise typer.Exit(1)
    path = Store(data).save_seed(trace)
    typer.echo(f"Conversación guardada en {path} (terminación: {trace.termination}).")


@app.command()
def induce(data: Path = DATA):
    """Induce el escenario de cada semilla que aún no lo tiene."""
    summary = induce_missing(Store(data), induce=_induce)
    for scenario_id in summary.created:
        typer.echo(f"creado: {scenario_id}")
    for scenario_id in summary.kept:
        typer.echo(f"ya existía: {scenario_id}")
    for scenario_id, reason in summary.failed.items():
        typer.echo(f"falló: {scenario_id} ({reason})", err=True)
    if summary.failed:
        raise typer.Exit(1)
