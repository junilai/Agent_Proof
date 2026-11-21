"""The figures the thesis writes by hand match the ones the code computes.

The tables and figures of chapter 6 are generated (test_figures_tables.py); the
figures in the prose are not. Each claim below recomputes a key figure from
results/ (and, for F6, from the annotators' labels) and checks that the
sentence reporting it, as written in chapters 6 and 7, carries that value. A
change in the data or in the text that breaks one fails here.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import pytest

from agentproof.report import compare_runs
from agentproof.store import Store
from experiments.analysis.detection import detection, negative_control, sensitivity
from experiments.analysis.reliability import effect_size
from experiments.f6.labels import load
from experiments.f6.report import results
from experiments.figures import data
from experiments.figures.data import E1, E4

ROOT = Path(__file__).resolve().parents[1]
CHAPTERS = ROOT / "thesis" / "capitulos"
RESULTS = "06-resultados.tex"
CONCLUSIONS = "07-conclusiones.tex"

WORDS = {
    1: "uno",
    2: "dos",
    3: "tres",
    4: "cuatro",
    5: "cinco",
    6: "seis",
    7: "siete",
    8: "ocho",
    9: "nueve",
    10: "diez",
    11: "once",
    12: "doce",
    20: "veinte",
    25: "veinticinco",
}


def _written(chapter: str, *claims: str) -> None:
    """Every claim appears in the chapter, with its whitespace collapsed."""
    text = " ".join((CHAPTERS / chapter).read_text(encoding="utf-8").split())
    missing = [claim for claim in claims if claim not in text]
    assert missing == [], f"{chapter} no dice:\n" + "\n".join(missing)


def _pct(value: float | Fraction) -> str:
    return f"{round(100 * float(value))}\\,\\%"


def _pct1(value: float | Fraction) -> str:
    return f"{100 * float(value):.1f}\\,\\%"


def _approval(store: Store, run: str) -> Fraction:
    verdicts = store.verdicts(run)
    return Fraction(sum(v.passed for v in verdicts), len(verdicts))


def _drop(store: Store, exp, operator: str) -> int:
    """Points the suite's pass rate drops, as the analysis reports it."""
    effect = effect_size(store, exp.reference, exp.candidates[operator])
    return round(100 * (effect.reference - effect.candidate))


def _step_limits(store: Store, exp) -> int:
    return sum(t.termination == "step_limit" for t in store.run_traces(exp.candidates["d6"]))


def _complete_drops(store: Store, exp, operator: str) -> int:
    table = data.approval_by_scenario(store, exp)
    reference, candidate = table["línea base"], table[operator.upper()]
    return sum(reference[s] == 1 and candidate.get(s) == 0 for s in reference)


def _manifested(found) -> int:
    return len(found.true_positives + found.false_negatives)


def _counts(found) -> tuple[int, int, int]:
    return len(found.true_positives), len(found.false_positives), len(found.false_negatives)


@pytest.fixture(scope="module")
def store() -> Store:
    return Store(ROOT)


@pytest.fixture(scope="module")
def det(store):
    return {
        (exp.name, op): detection(store, exp.reference, run, op)
        for exp in data.EXPERIMENTS
        for op, run in exp.candidates.items()
        if op in data.WITH_PREDICATE
    }


@pytest.fixture(scope="module")
def f6() -> dict:
    return json.loads((ROOT / "results" / "f6" / "analisis.json").read_text(encoding="utf-8"))


def test_the_published_f6_analysis_is_the_one_the_labels_give(store, f6):
    """The human-validation figures are read from analisis.json: it must still be
    what the annotators' labels and the installed oracle produce."""
    labels = load(store, ROOT / "evidence/f6/etiquetas", ROOT / "evidence/f6/clave")
    assert json.loads(results(store, labels).model_dump_json()) == f6


def test_the_execution_figures_of_e1_and_e4(store):
    e1 = sum(len(store.run_traces(run)) for run in E1.runs)
    e4 = sum(len(store.run_traces(run)) for run in E4.runs)
    cut_e1, cut_e4 = _step_limits(store, E1), _step_limits(store, E4)
    _written(
        RESULTS,
        f"cinco repeticiones cada una: {e1} conversaciones",
        f"salvo {cut_e1} de D6, que se cortaron",
        f"{e4} conversaciones con su juicio",
        f"Se cortaron por el límite de pasos {cut_e4} conversaciones de D6",
        f"contra {cut_e1} en E1",
    )
    _written(CONCLUSIONS, f"suman {e1 + e4} conversaciones y {e1 + e4} juicios")


def test_the_approval_and_pass_k_of_the_baselines(store):
    e1, e4 = data.pass_k(store, E1)["línea base"], data.pass_k(store, E4)["línea base"]
    reference, control = _approval(store, E1.reference), _approval(store, E1.control)
    _written(
        RESULTS,
        f"La línea base de referencia aprueba el {_pct(reference)} de las repeticiones",
        f"corrido otra vez, también el {_pct(control)}",
        f"baja del {_pct(e1[1])} con $k = 1$ al {_pct(e1[5])} con $k = 5$",
        f"La línea base en LangGraph aprueba el {_pct(_approval(store, E4.reference))}",
        f"contra el {_pct(reference)} en Claude Agent SDK",
        f"baja al mismo {_pct(e4[5])} con $k = 5$",
    )
    assert _pct(e1[5]) == _pct(e4[5])


def test_the_detection_in_e1(store, det):
    d1, d4, d6 = (det[("E1", op)] for op in ("d1", "d4", "d6"))
    d3 = compare_runs(store, E1.reference, E1.candidates["d3"])
    assert d1.true_positives == d1.false_positives == d3.regressions == []
    assert _manifested(d6) == 0 and len(d4.false_positives) == 1
    assert negative_control(store, E1.reference, E1.control).flagged == []
    _written(
        RESULTS,
        f"las {WORDS[len(d4.true_positives)]} regresiones de su conjunto manifestado aparecen",
        f"D1 degrada la suite en {_drop(store, E1, 'd1')} puntos",
        f"tiene {WORDS[_manifested(d1)]} escenarios manifestados",
        f"{WORDS[_complete_drops(store, E1, 'd1')]} caen del 100\\,\\% al 0\\,\\%",
        f"D6 produce {WORDS[len(d6.false_positives)]} regresiones",
        f"la baja en {_drop(store, E1, 'd3')} puntos con {WORDS[len(d3.weak_signals)]} señales",
        f"en {_drop(store, E1, 'd1')} y {_drop(store, E1, 'd3')} puntos porcentuales",
        f"el oráculo identificó {WORDS[_manifested(d1)]} escenarios con la regresión",
    )


def test_the_detection_in_e4_against_e1(store, det):
    d1, d4, d6 = (det[("E1", op)] for op in ("d1", "d4", "d6"))
    d1_e4, d4_e4, d6_e4 = (det[("E4", op)] for op in ("d1", "d4", "d6"))
    assert d1_e4.true_positives == d1_e4.false_positives == [] and _manifested(d6_e4) == 0
    assert len(d4_e4.true_positives) == len(d4.true_positives)
    assert len(d4_e4.false_positives) == len(d4.false_positives) + 1  # "un falso positivo más"
    assert len(d6_e4.false_positives) == len(d6.false_positives)
    _written(
        RESULTS,
        f"con las mismas {WORDS[len(d4_e4.true_positives)]} regresiones verdaderas",
        f"en unos {WORDS[_drop(store, E4, 'd1')]} puntos",
        f"el oráculo identifica {WORDS[_manifested(d1_e4)]} escenarios con la regresión",
        f"D6 vuelve a producir {WORDS[len(d6_e4.false_positives)]} regresiones",
    )
    drops = [_drop(store, E1, "d1"), _drop(store, E4, "d1"), _drop(store, E1, "d3")]
    e1, e4 = WORDS[_manifested(d1)], WORDS[_manifested(d1_e4)]
    _written(
        CONCLUSIONS,
        f"las {WORDS[len(d4.true_positives)]} regresiones de su conjunto manifestado aparecieron",
        f"entre {min(drops)} y {max(drops)} puntos sin que se declarara",
        f"el oráculo identificó {e1} escenarios con la regresión manifestada en E1 y {e4} en E4",
        f"D1 se manifestó en {e1} escenarios en E1 y en {e4} en E4",
        f"las {WORDS[len(d6.false_positives)]} regresiones de D6 cuentan como falsos positivos",
    )


def test_the_classification_metrics_of_d4(det):
    def precision(found) -> str:
        tp, fp, _ = _counts(found)
        return _pct(Fraction(tp, tp + fp))

    def f1(found) -> str:
        tp, fp, fn = _counts(found)
        return f"{2 * tp / (2 * tp + fp + fn):.2f}"

    sdk, langgraph = det[("E1", "d4")], det[("E4", "d4")]
    _written(
        RESULTS,
        f"D4 tiene una precisión del {precision(sdk)} en Claude Agent SDK",
        f"y del {precision(langgraph)} en LangGraph, con un F1 de {f1(sdk)} y {f1(langgraph)}",
    )


def test_the_sensitivity_of_d1_to_the_threshold(store):
    manifested = [
        _manifested(found)
        for exp in data.EXPERIMENTS
        for found in sensitivity(store, exp.reference, exp.candidates["d1"], "d1")
    ]
    _written(RESULTS, f"entre {WORDS[min(manifested)]} y {WORDS[max(manifested)]} escenarios")


def test_the_figures_of_e2(store, f6):
    e2 = f6["e2"]
    judge = data.judge_matrix(store)
    tp, fp, fn = (judge.get(k, 0) for k in ((True, True), (True, False), (False, True)))
    agreed, total, kappa = (e2["judge_approval"][k] for k in ("agreed", "total", "kappa"))
    criteria = Fraction(e2["judge_criteria"]["agreed"], e2["judge_criteria"]["total"])
    natural = e2["natural"]
    _written(
        RESULTS,
        f"coincide con la mayoría en {agreed} de las {total} conversaciones",
        f"con $\\kappa = {kappa:.2f}$, y en el {_pct1(criteria)} de los criterios",
        f"una precisión del {_pct(Fraction(tp, tp + fp))}",
        f"un recall del {_pct(Fraction(tp, tp + fn))} y un F1 de {2 * tp / (2 * tp + fp + fn):.2f}",
        f"aprobó {natural['passed']} de las {natural['judged']} conversaciones",
        f"el {_pct1(natural['share'])}",
    )
    _written(CONCLUSIONS, f"en {agreed} de {total} conversaciones ($\\kappa = {kappa:.2f}$)")


def test_the_figures_of_e3(f6):
    e3 = f6["e3"]
    every = e3["distribution"]["todos"]
    exact = [p["exact"] for p in e3["pairs"].values()]
    alpha = f"${e3['alpha_ordinal']:.2f}$"
    assert e3["median_at_least_4"] == e3["scenarios"]
    assert all(p["within_one"] == p["total"] for p in e3["pairs"].values())
    _written(
        RESULTS,
        f"Los {WORDS[e3['scenarios']]} escenarios tienen una mediana de 4 o más",
        f"el {_pct(e3['share_median_at_least_4'])}, la métrica principal de E3",
        f"{every['5']} son 5 y {every['4']} son 4, y ninguna es menor",
        f"entre {min(exact)} y {max(exact)} de las veinte calificaciones son iguales",
        f"El $\\alpha$ de Krippendorff ordinal, en cambio, da {alpha}",
        f"las {sum(every.values())} calificaciones se concentran entre 4 y 5",
    )
    _written(CONCLUSIONS, f"fue negativo ({alpha})")


def test_the_figures_of_the_audit(store, f6):
    audit = f6["audit"]
    weighted = audit["weighted"]["decisión"]
    decision = audit["annotators"]["decision"]
    contradiction = audit["annotators"]["contradicts_base"]
    matrix = data.audit_matrix(store)
    diagonal = sum(n for (majority, oracle), n in matrix.items() if majority == oracle)
    assert round(3 * weighted["exacta"]) == 2  # "dos de cada tres"
    _written(
        RESULTS,
        f"con ticket en E1, que es de {audit['ticket_weight']:.3f}",
        f"ninguna de las {audit['audited']} trazas",
        f"la lee al revés en el {_pct1(weighted['al revés'])}",
        f"la diagonal concentra {diagonal} de las {sum(matrix.values())} trazas con decisión",
        f"Fleiss de {decision['fleiss']:.2f}, con {decision['unanimous']} de {decision['items']}",
        f"da un $\\kappa$ de {contradiction['fleiss']:.2f} aunque {contradiction['unanimous']}",
        f"de las {contradiction['items']} trazas son unánimes",
    )


def test_the_origin_of_the_disagreements(f6):
    cause = f6["disagreements"]["by_cause"]
    scope, rules, judge = (
        cause[k] for k in ("alcance distinto", "reglas del oráculo", "evaluador")
    )
    _written(
        RESULTS,
        f"En {WORDS[judge['cells']]}, el error es del evaluador",
        f"{scope['repetitions']} provienen de un alcance distinto",
        f"{rules['repetitions']} de las reglas del oráculo y {judge['repetitions']} del evaluador",
    )


def test_a_figure_the_thesis_does_not_write_fails():
    """A claim fails when its value differs from the text, not just when it is absent."""
    with pytest.raises(AssertionError, match="doce escenarios manifestados"):
        _written(RESULTS, "tiene doce escenarios manifestados")
