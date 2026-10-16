from typer.testing import CliRunner

from agentproof import cli
from agentproof.store import Store
from tests.factories import manifest, scenario, verdict
from tests.fakes import ScriptedUser

runner = CliRunner()
AGENT = ["--adapter", "tests.fake_adapter", "--agent", "tests.fakes:echo_agent"]


def run(tmp_path, condition):
    args = ["run", *AGENT, "--condition", condition, "--repetitions", "5", "--data", str(tmp_path)]
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
    assert len(store.run_traces(base)) == 5 and store.manifest(base).repetitions == 5

    def fake_judge(sc, trace):
        """5/5 against 0/5 in the only scenario: significant (p = 0.0079) and a drop of 1."""
        passed = trace.run_id == base
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


def resume(tmp_path, run_id):
    return runner.invoke(cli.app, ["resume", "--run", run_id, "--data", str(tmp_path)])


def test_a_finished_run_resumes_to_nothing(tmp_path, monkeypatch):
    Store(tmp_path).save_scenario(scenario())
    monkeypatch.setattr(cli, "_simulated_user", lambda s: ScriptedUser(s.opening_message))
    assert run(tmp_path, "baseline-a").exit_code == 0
    store = Store(tmp_path)
    (run_id,) = store.runs()
    assert store.manifest(run_id).scenario_ids == [scenario().scenario_id]
    result = resume(tmp_path, run_id)
    assert result.exit_code == 0, result.output
    assert len(store.run_traces(run_id)) == 5


def test_resuming_refuses_when_the_protocol_changed(tmp_path, monkeypatch):
    Store(tmp_path).save_scenario(scenario())
    monkeypatch.setattr(cli, "_simulated_user", lambda s: ScriptedUser(s.opening_message))
    assert run(tmp_path, "baseline-a").exit_code == 0
    (run_id,) = Store(tmp_path).runs()
    monkeypatch.setattr(cli.models, "snapshot", lambda: {"judge": "otro"})
    result = resume(tmp_path, run_id)
    assert result.exit_code == 1 and "mezclaría dos protocolos" in result.output


def test_runs_older_than_the_scenario_list_cannot_resume(tmp_path):
    Store(tmp_path).create_run(manifest())
    result = resume(tmp_path, manifest().run_id)
    assert result.exit_code == 1 and "no registró sus escenarios" in result.output
    assert resume(tmp_path, "x").exit_code == 1
