"""The metrics of a framework's runs, as text and as data for the figures (§5.5, §5.8).

Family A carries the main detection metrics; family B is reported apart with its
effect size; D3 only as an effect size over the whole suite (§5.4).
"""

from __future__ import annotations

import csv
from fractions import Fraction
from pathlib import Path

from agentproof.store import Store
from casestudy.domain.mutations import FAMILY_A, FAMILY_B
from experiments.analysis.detection import Detection, negative_control, sensitivity
from experiments.analysis.reliability import (
    EffectSize,
    effect_size,
    joint_failure_rates,
    pass_hat_k,
)
from experiments.oracle.predicates import OPERATORS_WITH_PREDICATE


def _pct(value: Fraction | None) -> str:
    return "—" if value is None else f"{float(value):.0%}"


def _effect(label: str, effect: EffectSize | None) -> str:
    if effect is None:
        return f"  efecto ({label}): —"
    return (
        f"  efecto ({label}): aprobación {_pct(effect.reference)} -> {_pct(effect.candidate)}, "
        f"caída {_pct(effect.drop)}"
    )


def _detection(detections: list[Detection]) -> list[str]:
    main = next(d for d in detections if d.threshold == Fraction(2, 5))
    unexposed, exposed = main.false_positives_unexposed, main.false_positives_exposed
    lines = [
        f"  VP {len(main.true_positives)} · FN {len(main.false_negatives)} · "
        f"FP {len(main.false_positives)} (no expuestos {len(unexposed)}, "
        f"expuestos {len(exposed)}) · VN {len(main.true_negatives)}",
        f"  TPR {_pct(main.tpr)} · FPR {_pct(main.fpr)}",
        "  sensibilidad: "
        + " · ".join(
            f"{float(d.threshold):.1f} -> TPR {_pct(d.tpr)}, FPR {_pct(d.fpr)}" for d in detections
        ),
    ]
    if main.weak_signals:
        lines.append(f"  señales débiles: {', '.join(main.weak_signals)}")
    if main.deviations:
        lines.append(f"  DESVÍO, sin repeticiones válidas: {', '.join(main.deviations)}")
    return lines


def render_analysis(store: Store, reference: str, control: str, candidates: list[str]) -> str:
    by_operator = {store.manifest(run_id).condition: run_id for run_id in candidates}
    lines = [f"Análisis: referencia {reference} · control {control}"]
    sections = (
        ("Familia A (métricas principales)", FAMILY_A),
        ("Familia B (aparte, con tamaño de efecto)", tuple(op for op in FAMILY_B if op != "d3")),
        ("D3 (solo tamaño de efecto, sin conjunto expuesto)", ("d3",)),
    )
    for title, family in sections:
        present = [op for op in family if op in by_operator]
        if present:
            lines += ["", title]
        for operator in present:
            run_id = by_operator[operator]
            lines.append(f"{operator.upper()} · {run_id}")
            if operator in OPERATORS_WITH_PREDICATE:
                detections = sensitivity(store, reference, run_id, operator)
                lines += _detection(detections)
                if operator in FAMILY_B:
                    exposed = detections[0].exposed
                    lines.append(
                        _effect("expuestos", effect_size(store, reference, run_id, exposed))
                    )
            lines.append(_effect("suite", effect_size(store, reference, run_id)))
    control_result = negative_control(store, reference, control)
    lines += [
        "",
        f"Control negativo: {len(control_result.flagged)} marcado(s) en "
        f"{control_result.compared} escenario(s), FPR {_pct(control_result.fpr)}",
        "",
        "pass^k",
    ]
    for run_id in (reference, control, *candidates):
        values = " · ".join(f"k={k} {_pct(v)}" for k, v in pass_hat_k(store, run_id).items())
        lines.append(f"  {run_id}: {values}")
    return "\n".join(lines)


def _rate(value: Fraction | None) -> str:
    return "" if value is None else f"{float(value):.4f}"


def write_joint_failure_rates(
    store: Store, reference: str, candidates: list[str], path: Path
) -> None:
    """One row per scenario and operator with a predicate, for the figures of the thesis."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            ["operator", "scenario_id", "reference", "candidate", "exposed", "manifested", "status"]
        )
        for run_id in candidates:
            operator = store.manifest(run_id).condition
            if operator not in OPERATORS_WITH_PREDICATE:
                continue
            for row in joint_failure_rates(store, reference, run_id, operator):
                writer.writerow(
                    [
                        operator,
                        row.scenario_id,
                        _rate(row.reference),
                        _rate(row.candidate),
                        row.exposed,
                        row.manifested,
                        row.status or "",
                    ]
                )
