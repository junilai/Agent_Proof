"""The F6 analysis from the command line: the JSON and the refusals."""

import json

from typer.testing import CliRunner

from experiments.f6.__main__ import app
from experiments.f6.report import oracle_fingerprint
from tests.f6_fakes import ROOT, keys, like_the_oracle, rating, write_all, write_labels


def run(labels, out):
    args = ["--data", str(ROOT), "--labels", str(labels), "--keys", str(keys())]
    return CliRunner().invoke(app, [*args, "--out", str(out)])


def test_the_report_is_printed_and_every_result_written_as_json(tmp_path):
    labels = write_all(tmp_path / "etiquetas", like_the_oracle(), rating(4))
    result = run(labels, tmp_path / "analisis.json")
    assert result.exit_code == 0, result.output
    assert "## E2" in result.output and "## E3" in result.output
    found = json.loads((tmp_path / "analisis.json").read_text())
    assert set(found) == {"annotators", "oracle", "e2", "audit", "disagreements", "e3", "notes"}
    assert found["oracle"] == oracle_fingerprint()
    assert found["e2"]["pairs"] == 40 and found["e3"]["scenarios"] == 20
    assert found["disagreements"]["by_cause"]["alcance distinto"]["repetitions"] == 75


def test_incomplete_labels_stop_the_analysis_and_write_nothing(tmp_path):
    labels = tmp_path / "etiquetas"
    write_labels(labels, "X1", 1, like_the_oracle())
    result = run(labels, tmp_path / "analisis.json")
    assert result.exit_code == 1
    assert "se esperan 3 anotadores" in result.output
    assert not (tmp_path / "analisis.json").exists()
