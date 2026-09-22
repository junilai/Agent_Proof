"""Comparison of two runs (§8).

A scenario regressed when its pass rate drops by at least 0.4, the minimum
effect size of the pre-registered criterion; F3 adds Fisher's exact test with
Benjamini-Hochberg on top. Rates are exact fractions, so a drop from 1.0 to 0.6
counts without rounding errors. Repetitions without a verdict (simulator
failures or judge errors) are invalid: counted and reported, never rated.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction

from agentproof.store import Store

MIN_DROP = Fraction(2, 5)


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
    regressed: bool

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

    @property
    def regressions(self) -> list[ScenarioComparison]:
        return [c for c in self.comparisons if c.regressed]

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
    comparisons = []
    for scenario_id in sorted(base.keys() & cand.keys()):
        b, c = base[scenario_id], cand[scenario_id]
        drop = None if b.rate is None or c.rate is None else b.rate - c.rate
        regressed = drop is not None and drop >= min_drop
        comparisons.append(ScenarioComparison(scenario_id, b, c, regressed))
    return RunComparison(
        baseline_run=baseline_run,
        candidate_run=candidate_run,
        comparisons=comparisons,
        invalid={baseline_run: base_invalid, candidate_run: cand_invalid},
        unmatched=sorted(base.keys() ^ cand.keys()),
    )


def _rate(count: PassCount) -> str:
    return "  —  " if count.rate is None else f"{float(count.rate):5.0%}"


def render_comparison(comparison: RunComparison) -> str:
    title = f"AgentProof: {comparison.baseline_run} -> {comparison.candidate_run}"
    header = f"{'escenario':<24} {'base':>6} {'cand':>6} {'cambio':>7}  estado"
    lines = [title, header, "-" * 60]
    for c in comparison.comparisons:
        rates = f"{_rate(c.baseline):>6} {_rate(c.candidate):>6}"
        change = "     —" if c.drop is None else f"{float(-c.drop):+6.0%}"
        status = "REGRESIÓN" if c.regressed else "ok"
        lines.append(f"{c.scenario_id:<24} {rates} {change:>7}  {status}")
    regressions, total = len(comparison.regressions), len(comparison.comparisons)
    lines += ["-" * 60, f"{regressions} regresión(es) en {total} escenario(s)"]
    for run_id, count in comparison.invalid.items():
        if count:
            lines.append(f"{run_id}: {count} repetición(es) inválida(s), sin juicio")
    if comparison.unmatched:
        unmatched = ", ".join(comparison.unmatched)
        lines.append(f"sin comparar (presentes en una sola corrida): {unmatched}")
    return "\n".join(lines)
