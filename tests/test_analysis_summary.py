import csv

from agentproof.store import Store
from experiments.analysis.summary import render_analysis, write_joint_failure_rates
from tests.factories import manifest
from tests.test_analysis_detection import (
    APPROVED,
    CANDIDATE,
    CONTROL,
    REFERENCE,
    SCENARIOS,
    populated,
    repetitions,
)

D3 = "d3-20261016-160000"


def with_d3(store: Store) -> Store:
    store.create_run(manifest(run_id=D3, condition="d3", repetitions=5))
    for n in SCENARIOS:
        repetitions(store, D3, n, [APPROVED] * 5, [True] * 4 + [n != 1])
    return store


def test_each_family_is_reported_apart(tmp_path):
    text = render_analysis(with_d3(populated(tmp_path)), REFERENCE, CONTROL, [CANDIDATE, D3])
    family_a, d3 = text.split("D3 (solo tamaño de efecto")
    assert "D4 · " in family_a and "TPR 50% · FPR 50%" in family_a
    assert "FP 2 (no expuestos 1, expuestos 1)" in family_a
    assert "0.6 -> TPR 100%, FPR 40%" in family_a
    assert "caída 3%" in d3 and "TPR" not in d3.split("Control negativo")[0]
    assert "Control negativo: 1 marcado(s) en 6 escenario(s)" in d3


def test_the_joint_rates_are_written_for_the_operators_with_a_predicate(tmp_path):
    store = with_d3(populated(tmp_path))
    path = tmp_path / "joint.csv"
    write_joint_failure_rates(store, REFERENCE, [CANDIDATE, D3], path)
    rows = list(csv.DictReader(path.open()))
    assert len(rows) == 6 and {r["operator"] for r in rows} == {"d4"}
    assert rows[1]["candidate"] == "0.4000" and rows[1]["manifested"] == "True"
