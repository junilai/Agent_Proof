from typer.testing import CliRunner

from experiments.analysis.__main__ import app
from tests.test_analysis_detection import (
    AMBIGUOUS,
    CANDIDATE,
    CONTROL,
    DENIED,
    EXPOSED,
    REFERENCE,
    SCENARIOS,
    populated,
)


def analyse(tmp_path, *candidates):
    args = ["--data", str(tmp_path), "--reference", REFERENCE, "--control", CONTROL]
    for run_id in candidates:
        args += ["--candidate", run_id]
    return CliRunner().invoke(app, args)


def test_the_command_prints_the_metrics_and_writes_the_joint_rates(tmp_path):
    populated(tmp_path)
    result = analyse(tmp_path, CANDIDATE)
    assert result.exit_code == 0, result.output
    assert "Familia A" in result.output and "pass^k" in result.output
    assert (tmp_path / "results" / "analysis" / "joint_failure_rates.csv").exists()


def test_the_command_refuses_while_cases_wait_for_annotation(tmp_path):
    scenarios = SCENARIOS | {1: (EXPOSED, [AMBIGUOUS] + [DENIED] * 4, [False] * 5)}
    populated(tmp_path, scenarios)
    result = analyse(tmp_path, CANDIDATE)
    assert result.exit_code == 1 and "1 caso(s) esperan anotación manual" in result.output
    assert not (tmp_path / "results" / "analysis").exists()
