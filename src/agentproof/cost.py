"""Cost and latency of each component (§5.8, D-007).

The inducer, the simulated user and the judge are priced with the dated table
in ``agentproof.pricing``. The agent caches its prompts, which the table does
not price, so its own SDK estimate is reported instead, next to its tokens.
Artifacts recorded before the components measured themselves are counted as
unrecorded, never as zero cost.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from agentproof import models, pricing
from agentproof.schema import Usage
from agentproof.store import Store


@dataclass
class ComponentCost:
    name: str
    recorded: int = 0
    unrecorded: int = 0
    usage: Usage = field(default_factory=Usage)
    seconds: float = 0.0
    usd: float | None = 0.0
    """Calculated with the price table; None when a model has no price."""
    unpriced: set[str] = field(default_factory=set)

    def add(self, usage: Usage, seconds: float | None, priced_as: str | None, prices) -> None:
        """One artifact; ``priced_as=None`` leaves the USD to the caller (the agent's SDK)."""
        if seconds is None:
            self.unrecorded += 1
            return
        self.recorded += 1
        self.usage += usage
        self.seconds += seconds
        if priced_as is None:
            if usage.cost_usd is not None:
                self.usd = (self.usd or 0.0) + usage.cost_usd
        elif priced_as not in prices:
            self.unpriced.add(priced_as)
            self.usd = None
        elif self.usd is not None:
            per_input, per_output = prices[priced_as]
            self.usd += (usage.input_tokens * per_input + usage.output_tokens * per_output) / 1e6

    @property
    def mean_seconds(self) -> float | None:
        return self.seconds / self.recorded if self.recorded else None


def _sim_model(trace_models: dict) -> str:
    return str((trace_models.get("sim_user") or {}).get("model", models.SIM_USER.model))


def cost_summary(
    store: Store, run_ids: Iterable[str] | None = None, prices=pricing.PRICES
) -> list[ComponentCost]:
    """Inducer over the corpus; simulated user, agent and judge over the runs given (or all)."""
    inducer, simulator = ComponentCost("inductor"), ComponentCost("usuario simulado")
    agent, judge = ComponentCost("agente", usd=None), ComponentCost("evaluador")
    for scenario in store.scenarios():
        inducer.add(scenario.usage, scenario.seconds, scenario.induced_by, prices)
    for run_id in run_ids if run_ids is not None else store.runs():
        for trace in store.run_traces(run_id):
            sim_model = _sim_model(trace.models)
            simulator.add(trace.simulator_usage, trace.simulator_seconds, sim_model, prices)
            agent.add(trace.usage, trace.agent_seconds, None, prices)
        for verdict in store.verdicts(run_id):
            judge.add(verdict.usage, verdict.seconds, verdict.judged_by, prices)
    return [inducer, simulator, agent, judge]


def _usd(value: float | None) -> str:
    return "—" if value is None else f"{value:.4f}"


def render_cost(components: list[ComponentCost]) -> str:
    lines = [
        f"Costo por componente (precios al {pricing.PRICES_AS_OF.isoformat()}, "
        "USD por millón de tokens; el agente, según su SDK)",
        f"{'componente':<18} {'con registro':>12} {'sin registro':>12} "
        f"{'entrada':>10} {'salida':>9} {'USD':>9} {'s medios':>9}",
    ]
    for c in components:
        mean = "—" if c.mean_seconds is None else f"{c.mean_seconds:.1f}"
        lines.append(
            f"{c.name:<18} {c.recorded:>12} {c.unrecorded:>12} {c.usage.input_tokens:>10} "
            f"{c.usage.output_tokens:>9} {_usd(c.usd):>9} {mean:>9}"
        )
        if c.unpriced:
            lines.append(f"  sin precio en la tabla: {', '.join(sorted(c.unpriced))}")
    known = [c.usd for c in components if c.usd is not None]
    partial = any(c.usd is None and c.recorded for c in components)
    scope = "parcial, falta algún componente; " if partial else ""
    lines.append(f"total: USD {sum(known):.4f} ({scope}a conciliar con la consola de Anthropic)")
    return "\n".join(lines)
