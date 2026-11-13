"""AgentProof command line: record | induce | review | run | resume | judge | report | cost.

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
from pydantic import ValidationError

from agentproof import models
from agentproof import review as curation
from agentproof.conversation import Exchange, TraceContext, UserDriver, converse, utc_now
from agentproof.cost import cost_summary, render_cost
from agentproof.induction import induce_missing, induce_scenario
from agentproof.judge import judge_run, judge_trace
from agentproof.report import compare_runs, render_comparison
from agentproof.runner import RunInProgress, run_suite
from agentproof.schema import RunManifest, Scenario, Trace, Verdict, run_id_for
from agentproof.session import SessionFactory
from agentproof.simulator import SimulatedUser
from agentproof.store import Store
from agentproof.transcript import render_transcript

app = typer.Typer(
    help="AgentProof: detección de regresiones en agentes basados en LLM.", no_args_is_help=True
)
DATA = typer.Option(Path("."), "--data", help="Carpeta que contiene corpus/ y results/.")
ADAPTER = typer.Option(..., "--adapter", help="Adaptador del framework, por ejemplo claude_sdk.")
AGENT = typer.Option(..., "--agent", help="Constructor del agente, como modulo:atributo.")
VARIANT = typer.Option("baseline", "--variant", help="Variante del agente.")
CARD = typer.Option(None, "--card", help="Tarjeta de situación que se le entregó a la persona.")
RUNS = typer.Option(None, "--run", help="Corrida a incluir; se repite. Por omisión, todas.")
SCENARIOS = typer.Option(
    None, "--scenario", help="Escenario a reejecutar; se repite. Por omisión, todos."
)
CURATED = typer.Option(..., "--out", help="Carpeta de la suite curada, aparte del corpus.")
REVIEWER = typer.Option(..., "--reviewer", help="Quién revisa.")


def load_object(path: str) -> Any:
    module, _, attribute = path.partition(":")
    if not attribute:
        raise typer.BadParameter(f"se esperaba modulo:atributo, se recibió {path!r}")
    return getattr(importlib.import_module(module), attribute)


def load_adapter(name: str) -> Any:
    return importlib.import_module(name if "." in name else f"agentproof.adapters.{name}")


def session_factory_for(adapter: str, agent: str, variant: str) -> SessionFactory:
    return load_adapter(adapter).session_factory(load_object(agent), variant)


WAITING = "(el agente está respondiendo, puede tardar unos segundos…)"


class HumanUser:
    """A person at the terminal; an empty line ends the conversation.

    After every message it says the agent is answering: a reply takes several
    seconds and a participant who does not know the tool could think it hung.
    """

    def __init__(
        self,
        read: Callable[[str], str] = input,
        write: Callable[[str], None] = typer.echo,
    ) -> None:
        self.read, self.write = read, write

    async def first_message(self) -> str:
        while not (message := self.read("usted> ").strip()):
            pass
        self.write(WAITING)
        return message

    async def next_message(self, history: Sequence[Exchange]) -> str | None:
        self.write(f"agente> {history[-1].agent}")
        try:
            message = self.read("usted> ").strip() or None
        except EOFError:  # Ctrl+D also ends the conversation
            return None
        if message is not None:
            self.write(WAITING)
        return message


def _induce(seed: Trace) -> Scenario:
    return induce_scenario(seed)


def _simulated_user(scenario: Scenario) -> UserDriver:
    return SimulatedUser(scenario)


def _judge(scenario: Scenario, trace: Trace) -> Verdict:
    return judge_trace(scenario, trace)


def _unknown_run(run_id: object) -> typer.Exit:
    typer.echo(f"No existe la corrida {run_id}.", err=True)
    return typer.Exit(1)


@app.command()
def record(
    adapter: str = ADAPTER,
    agent: str = AGENT,
    variant: str = VARIANT,
    card: str | None = CARD,
    data: Path = DATA,
):
    """Graba una conversación con una persona como traza semilla."""
    factory = session_factory_for(adapter, agent, variant)
    context = TraceContext(kind="seed", adapter=adapter, agent=agent, variant=variant, card_id=card)
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


@app.command()
def review(
    out: Path = CURATED,
    reviewer: str = REVIEWER,
    scenario: list[str] | None = SCENARIOS,
    data: Path = DATA,
):
    """Revisión humana opcional de los escenarios: guarda la suite curada en otra carpeta."""
    copy = Store(out)
    curation.start(Store(data), copy)
    done = curation.reviews(copy)
    seeds = {seed.trace_id: seed for seed in copy.seeds()}
    scenarios = [s for s in copy.scenarios() if not scenario or s.scenario_id in scenario]
    typer.echo(
        f"{sum(s.scenario_id in done for s in scenarios)} de {len(scenarios)} "
        "escenarios ya revisados."
    )
    for current in (s for s in scenarios if s.scenario_id not in done):
        typer.echo(f"\n{'=' * 72}\n{current.scenario_id}\n\nConversación semilla:")
        typer.echo(render_transcript(seeds[current.seed_trace_id]))
        typer.echo(f"\nObjetivo del cliente: {current.user_goal}")
        typer.echo(f"Primer mensaje: {current.opening_message}\nCriterios de éxito:")
        for n, criterion in enumerate(current.success_criteria, start=1):
            typer.echo(f"  {n}. {criterion}")
        choice = typer.prompt("[a]probar, [c]orregir o [s]altar", default="s")
        if choice == "a":
            curation.save(copy, current, _review_of(current, reviewer, corrected=False))
        elif choice == "c":
            try:
                fixed = _correct(current, reviewer)
            except ValidationError as error:
                typer.echo(f"No se guardó: {error.errors()[0]['msg']}", err=True)
                continue
            curation.save(copy, fixed, _review_of(fixed, reviewer, corrected=True))
    typer.echo(f"\nSuite curada en {out}. Se corre con: agentproof run --data {out} ...")


def _review_of(scenario: Scenario, reviewer: str, *, corrected: bool) -> curation.Review:
    return curation.Review(
        scenario_id=scenario.scenario_id,
        reviewer=reviewer,
        corrected=corrected,
        reviewed_at=utc_now(),
    )


def _correct(scenario: Scenario, reviewer: str) -> Scenario:
    """Enter keeps each text; "-" removes a criterion; new ones until an empty line."""
    goal = typer.prompt("Objetivo", default=scenario.user_goal)
    opening = typer.prompt("Primer mensaje", default=scenario.opening_message)
    criteria = []
    for n, criterion in enumerate(scenario.success_criteria, start=1):
        answer = typer.prompt(f"Criterio {n} (- lo quita)", default=criterion)
        if answer != "-":
            criteria.append(answer)
    while added := typer.prompt("Criterio nuevo (vacío termina)", default="", show_default=False):
        criteria.append(added)
    return curation.corrected(
        scenario, goal=goal, opening=opening, criteria=criteria, reviewer=reviewer, now=utc_now()
    )


@app.command()
def run(
    adapter: str = ADAPTER,
    agent: str = AGENT,
    condition: str = typer.Option(..., "--condition", help="Condición, por ejemplo baseline-a."),
    variant: str = VARIANT,
    repetitions: int = typer.Option(5, "--repetitions", min=1),
    turn_budget: int = typer.Option(10, "--turn-budget", min=1),
    scenario: list[str] | None = SCENARIOS,
    data: Path = DATA,
):
    """Reejecuta cada escenario con el usuario simulado contra una variante del agente."""
    store = Store(data)
    scenarios = store.scenarios()
    if not scenarios:
        typer.echo("No hay escenarios: ejecute primero 'agentproof induce'.", err=True)
        raise typer.Exit(1)
    if scenario:
        unknown = sorted(set(scenario) - {s.scenario_id for s in scenarios})
        if unknown:
            typer.echo(f"Escenarios desconocidos: {', '.join(unknown)}.", err=True)
            raise typer.Exit(1)
        scenarios = [s for s in scenarios if s.scenario_id in set(scenario)]
    now = utc_now()
    manifest = RunManifest(
        run_id=run_id_for(condition, now),
        condition=condition,
        variant=variant,
        adapter=adapter,
        agent=agent,
        repetitions=repetitions,
        turn_budget=turn_budget,
        models=models.snapshot(),
        created_at=now,
        scenario_ids=[s.scenario_id for s in scenarios],
    )
    factory = session_factory_for(adapter, agent, variant)
    asyncio.run(run_suite(scenarios, factory, manifest, store, _simulated_user, on_trace=_progress))
    typer.echo(f"Corrida {manifest.run_id} completa.")


def _progress(trace: Trace) -> None:
    retry = f" (intento {trace.attempt})" if (trace.attempt or 1) > 1 else ""
    typer.echo(f"{trace.scenario_id} #{trace.repetition}{retry}: {trace.termination}")


@app.command()
def resume(run_id: str = typer.Option(..., "--run", help="Id de la corrida."), data: Path = DATA):
    """Retoma una corrida interrumpida sin repetir lo que ya se ejecutó."""
    store = Store(data)
    try:
        manifest = store.manifest(run_id)
    except KeyError as missing:
        raise _unknown_run(missing) from None
    if manifest.scenario_ids is None:
        typer.echo("La corrida no registró sus escenarios: no se puede reanudar.", err=True)
        raise typer.Exit(1)
    if manifest.models != models.snapshot():
        typer.echo(
            "Los modelos fijados cambiaron desde que empezó la corrida: "
            "reanudarla mezclaría dos protocolos.",
            err=True,
        )
        raise typer.Exit(1)
    scenarios = [store.scenario(scenario_id) for scenario_id in manifest.scenario_ids]
    factory = session_factory_for(manifest.adapter, manifest.agent, manifest.variant)
    try:
        asyncio.run(
            run_suite(
                scenarios,
                factory,
                manifest,
                store,
                _simulated_user,
                on_trace=_progress,
                resume=True,
            )
        )
    except RunInProgress:
        typer.echo("La corrida sigue en curso en otro proceso: espere a que termine.", err=True)
        raise typer.Exit(1) from None
    typer.echo(f"Corrida {manifest.run_id} completa.")


@app.command()
def judge(run_id: str = typer.Option(..., "--run", help="Id de la corrida."), data: Path = DATA):
    """Juzga las trazas de una corrida que aún no tienen juicio."""
    try:
        summary = judge_run(Store(data), run_id, judge=_judge)
    except KeyError as missing:
        raise _unknown_run(missing) from None
    typer.echo(
        f"juzgadas: {len(summary.judged)} · ya juzgadas: {len(summary.kept)} · "
        f"inválidas: {len(summary.skipped)} · fallidas: {len(summary.failed)}"
    )
    for trace_id, reason in summary.failed.items():
        typer.echo(f"falló: {trace_id} ({reason})", err=True)
    if summary.failed:
        raise typer.Exit(1)


@app.command()
def report(
    baseline: str = typer.Option(..., "--baseline", help="Corrida de referencia."),
    candidate: str = typer.Option(..., "--candidate", help="Corrida candidata."),
    data: Path = DATA,
):
    """Compara dos corridas; sale con 2 si hay regresiones y con 0 si no."""
    try:
        comparison = compare_runs(Store(data), baseline, candidate)
    except KeyError as missing:
        raise _unknown_run(missing) from None
    typer.echo(render_comparison(comparison))
    raise typer.Exit(comparison.exit_code)


@app.command()
def cost(
    runs: list[str] = RUNS,
    data: Path = DATA,
):
    """Costo y latencia por componente, con la fecha de los precios."""
    try:
        components = cost_summary(Store(data), runs or None)
    except KeyError as missing:
        raise _unknown_run(missing) from None
    typer.echo(render_cost(components))
