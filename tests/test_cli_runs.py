from typer.testing import CliRunner

from agentproof import cli
from agentproof.store import Store
from tests.factories import scenario, verdict
from tests.fakes import ScriptedUser

runner = CliRunner()
AGENT = ["--adapter", "tests.fake_adapter", "--agent", "tests.fakes:echo_agent"]


def run(tmp_path, condition):
    args = ["run", *AGENT, "--condition", condition, "--repetitions", "2", "--data", str(tmp_path)]
    return runner.invoke(cli.app, args)


def judge(tmp_path, run_id):
    return runner.invoke(cli.app, ["judge", "--run", run_id, "--data", str(tmp_path)])


def report(tmp_path, baseline, candidate):
    args = ["report", "--baseline", baseline, "--candidate", candidate, "--data", str(tmp_path)]
    return runner.invoke(cli.app, args)


def test_run_needs_scenarios(tmp_path):
    assert run(tmp_path, "baseline-a").exit_code == 1


def test_run_then_judge_then_report(tmp_path, monkeypatch):
    Store(tmp_path).save_scenario(scenario())
    monkeypatch.setattr(cli, "_simulated_user", lambda s: ScriptedUser(s.opening_message))
    for condition in ("baseline-a", "baseline-b"):
        result = run(tmp_path, condition)
        assert result.exit_code == 0, result.output
    store = Store(tmp_path)
    base, cand = store.runs()
    assert len(store.run_traces(base)) == 2 and store.manifest(base).repetitions == 2

    def fake_judge(sc, trace):
        passed = trace.run_id == base or trace.repetition == 1
        return verdict(
            [passed], trace_id=trace.trace_id, run_id=trace.run_id, scenario_id=sc.scenario_id
        )

    monkeypatch.setattr(cli, "_judge", fake_judge)
    for run_id in (base, cand):
        assert judge(tmp_path, run_id).exit_code == 0
    result = report(tmp_path, base, cand)
    assert result.exit_code == 2 and "REGRESIÓN" in result.output


def test_unknown_runs_are_usage_errors(tmp_path):
    assert judge(tmp_path, "x").exit_code == 1
    assert report(tmp_path, "x", "y").exit_code == 1
