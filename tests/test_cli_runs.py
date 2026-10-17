from typer.testing import CliRunner

from agentproof import cli
from agentproof.store import Store
from tests.factories import manifest, scenario, verdict
from tests.fakes import ScriptedUser

runner = CliRunner()
AGENT = ["--adapter", "tests.fake_adapter", "--agent", "tests.fakes:echo_agent"]


def run(tmp_path, condition, *extra):
    args = ["run", *AGENT, "--condition", condition, "--repetitions", "5", "--data", str(tmp_path)]
    return runner.invoke(cli.app, [*args, *extra])


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


FIRST, SECOND, THIRD = "sc-tr-000000000001", "sc-tr-000000000002", "sc-tr-000000000003"


def three_scenarios(tmp_path, monkeypatch):
    store = Store(tmp_path)
    for n, scenario_id in enumerate((FIRST, SECOND, THIRD), start=1):
        store.save_scenario(scenario(scenario_id=scenario_id, seed_trace_id=f"tr-00000000000{n}"))
    monkeypatch.setattr(cli, "_simulated_user", lambda s: ScriptedUser(s.opening_message))
    return store


def test_a_run_can_be_limited_to_some_scenarios(tmp_path, monkeypatch):
    store = three_scenarios(tmp_path, monkeypatch)
    result = run(tmp_path, "baseline-a", "--scenario", THIRD, "--scenario", FIRST)
    assert result.exit_code == 0, result.output
    (run_id,) = store.runs()
    assert store.manifest(run_id).scenario_ids == [FIRST, THIRD]
    assert {t.scenario_id for t in store.run_traces(run_id)} == {FIRST, THIRD}
    assert resume(tmp_path, run_id).exit_code == 0
    assert len(store.run_traces(run_id)) == 10


def test_an_unknown_scenario_runs_nothing(tmp_path, monkeypatch):
    store = three_scenarios(tmp_path, monkeypatch)
    result = run(tmp_path, "baseline-a", "--scenario", FIRST, "--scenario", "sc-tr-x")
    assert result.exit_code == 1 and "sc-tr-x" in result.output
    assert store.runs() == []


def test_without_the_option_every_scenario_runs(tmp_path, monkeypatch):
    store = three_scenarios(tmp_path, monkeypatch)
    assert run(tmp_path, "baseline-a").exit_code == 0
    (run_id,) = store.runs()
    assert len(store.manifest(run_id).scenario_ids) == 3
