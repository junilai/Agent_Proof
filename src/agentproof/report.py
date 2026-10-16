"""Comparison of two runs with the regression criterion (§5.5).

A scenario regressed when two conditions hold: Fisher's exact test between the
runs is significant after Benjamini-Hochberg with alpha = 0.05 over the
scenarios compared, and the pass rate drops by at least 0.4. A drop of 0.4
without significance is a weak signal: with R = 5 an isolated scenario cannot
pass the correction, so it is reported but does not fail the build. Rates are
exact fractions. Repetitions without a verdict (simulator failures or judge
errors) are invalid: counted and reported, never rated.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from agentproof.stats import benjamini_hochberg, fisher_exact
from agentproof.store import Store

MIN_DROP = Fraction(2, 5)

Status = Literal["regresión", "señal débil", "ok"]


@dataclass(frozen=True)
class PassCount:
    passed: int
    valid: int

    @property
    def rate(self) -> Fraction | None:
        return Fraction(self.passed, self.valid) if self.valid else None


@dataclass(frozen=True)
class ScenarioComparison:
    scenario_id: str
    baseline: PassCount
    candidate: PassCount
    p_value: Fraction | None
    """None when one of the runs has no valid repetition: nothing to test."""
    status: Status

    @property
    def regressed(self) -> bool:
        return self.status == "regresión"

    @property
    def drop(self) -> Fraction | None:
        if self.baseline.rate is None or self.candidate.rate is None:
            return None
        return self.baseline.rate - self.candidate.rate


@dataclass(frozen=True)
class RunComparison:
    baseline_run: str
    candidate_run: str
    comparisons: list[ScenarioComparison]
    invalid: dict[str, int]
    unmatched: list[str]
    repetitions: dict[str, int]

    @property
    def regressions(self) -> list[ScenarioComparison]:
        return [c for c in self.comparisons if c.regressed]

    @property
    def weak_signals(self) -> list[ScenarioComparison]:
        return [c for c in self.comparisons if c.status == "señal débil"]

    @property
    def exit_code(self) -> int:
        return 2 if self.regressions else 0


def _pass_counts(store: Store, run_id: str) -> tuple[dict[str, PassCount], int]:
    passed: dict[str, int] = defaultdict(int)
    valid: dict[str, int] = defaultdict(int)
    for verdict in store.verdicts(run_id):
        valid[verdict.scenario_id] += 1
        passed[verdict.scenario_id] += verdict.passed
    traces = store.run_traces(run_id)
    counts = {s: PassCount(passed[s], valid[s]) for s in {t.scenario_id or "" for t in traces}}
    invalid = len(traces) - sum(valid.values())
    return counts, invalid


def compare_runs(
    store: Store, baseline_run: str, candidate_run: str, min_drop: Fraction = MIN_DROP
) -> RunComparison:
    base, base_invalid = _pass_counts(store, baseline_run)
    cand, cand_invalid = _pass_counts(store, candidate_run)
    common = sorted(base.keys() & cand.keys())
    p_values = {
        s: fisher_exact(base[s].passed, base[s].valid, cand[s].passed, cand[s].valid)
        for s in common
        if base[s].valid and cand[s].valid
    }
    significant = benjamini_hochberg(p_values)
    comparisons = []
    for scenario_id in common:
        b, c = base[scenario_id], cand[scenario_id]
        drop = None if b.rate is None or c.rate is None else b.rate - c.rate
        status: Status = "ok"
        if drop is not None and drop >= min_drop:
            status = "regresión" if scenario_id in significant else "señal débil"
        comparisons.append(ScenarioComparison(scenario_id, b, c, p_values.get(scenario_id), status))
    return RunComparison(
        baseline_run=baseline_run,
        candidate_run=candidate_run,
        comparisons=comparisons,
        invalid={baseline_run: base_invalid, candidate_run: cand_invalid},
        unmatched=sorted(base.keys() ^ cand.keys()),
        repetitions={
            run_id: store.manifest(run_id).repetitions for run_id in (baseline_run, candidate_run)
        },
    )


def _rate(count: PassCount, planned: int) -> str:
    short = "*" if count.valid < planned else " "
    return "  —  " + short if count.rate is None else f"{float(count.rate):5.0%}{short}"


def _p(p_value: Fraction | None) -> str:
    return "     —" if p_value is None else f"{float(p_value):6.4f}"


_SHOWN = {"regresión": "REGRESIÓN", "señal débil": "señal débil", "ok": "ok"}


def render_comparison(comparison: RunComparison) -> str:
    title = f"AgentProof: {comparison.baseline_run} -> {comparison.candidate_run}"
    header = f"{'escenario':<24} {'base':>7} {'cand':>7} {'cambio':>7} {'p':>6}  estado"
    lines = [title, header, "-" * 72]
    planned_base = comparison.repetitions[comparison.baseline_run]
    planned_cand = comparison.repetitions[comparison.candidate_run]
    short = False
    for c in comparison.comparisons:
        rates = f"{_rate(c.baseline, planned_base):>7} {_rate(c.candidate, planned_cand):>7}"
        short = short or "*" in rates
        change = "     —" if c.drop is None else f"{float(-c.drop):+6.0%}"
        status = "sin juicio" if c.p_value is None else _SHOWN[c.status]
        lines.append(f"{c.scenario_id:<24} {rates} {change:>7} {_p(c.p_value)}  {status}")
    regressions, weak = len(comparison.regressions), len(comparison.weak_signals)
    total = len(comparison.comparisons)
    lines += [
        "-" * 72,
        f"{regressions} regresión(es) y {weak} señal(es) débil(es) en {total} escenario(s)",
    ]
    if short:
        lines.append("* menos repeticiones válidas que las previstas (D-001, regla 4)")
    for run_id, count in comparison.invalid.items():
        if count:
            lines.append(f"{run_id}: {count} repetición(es) inválida(s), sin juicio")
    if comparison.unmatched:
        unmatched = ", ".join(comparison.unmatched)
        lines.append(f"sin comparar (presentes en una sola corrida): {unmatched}")
    return "\n".join(lines)
