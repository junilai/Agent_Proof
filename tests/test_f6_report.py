"""The Spanish report of F6, with every part and the oracle it measured."""

from experiments.f6.labels import load
from experiments.f6.report import oracle_fingerprint, render, results
from tests.f6_fakes import keys, like_the_oracle, rating, store, write_all
from tests.test_preregistration import protocol


def noted(annotator, key, spec):
    return rating(4)(annotator, key, spec) | {"nota": "falta un criterio"}


def test_the_report_has_every_part(tmp_path):
    labels = load(store(), write_all(tmp_path, like_the_oracle(), noted), keys())
    shown = render(results(store(), labels))
    for title in ("## E2", "## Auditoría del oráculo", "## Desacuerdos (D-016)", "## E3"):
        assert title in shown
    assert "por traza: 40/40 (100.0 %) · κ de Cohen 1.00" in shown
    assert "Escenarios con mediana ≥ 4: 20/20 (100.0 %)" in shown
    assert f"Oráculo medido: reglas con huella {oracle_fingerprint()}" in shown
    assert "Notas de los anotadores: 60" in shown


def test_a_session_still_out_is_reported_as_pending(tmp_path):
    found = results(store(), load(store(), write_all(tmp_path, like_the_oracle()), keys()))
    assert found.e3 is None
    assert "Sesión 2: sin etiquetas todavía." in render(found)


def test_the_oracle_is_named_by_its_preregistered_fingerprint():
    assert oracle_fingerprint() == protocol()["Reglas del oráculo (código fuente)"]
