import pytest
from typer.testing import CliRunner

from agentproof import cli
from agentproof.cost import cost_summary, render_cost
from agentproof.models import SIM_USER
from agentproof.schema import Usage
from agentproof.store import Store
from tests.factories import manifest, scenario, trace, verdict

PRICES = {"inducer-model": (2.0, 10.0), SIM_USER.model: (1.0, 5.0), "claude-opus-5": (5.0, 25.0)}
RUN_ID = manifest().run_id


def measured_store(tmp_path, judged_by="claude-opus-5"):
    store = Store(tmp_path)
    store.save_scenario(
        scenario(induced_by="inducer-model", usage=Usage(input_tokens=1_000_000), seconds=30.0)
    )
    store.create_run(manifest())
    store.save_run_trace(
        trace(
            kind="run",
            trace_id="tr-new",
            usage=Usage(input_tokens=500, output_tokens=50, cost_usd=0.04),
            agent_seconds=12.0,
            simulator_usage=Usage(input_tokens=0, output_tokens=200_000),
            simulator_seconds=4.0,
        )
    )
    store.save_run_trace(trace(kind="run", trace_id="tr-old", repetition=2))
    store.save_verdict(
        verdict(
            [True],
            trace_id="tr-new",
            judged_by=judged_by,
            usage=Usage(input_tokens=100_000, output_tokens=10_000),
            seconds=20.0,
        )
    )
    return store


def test_each_component_is_priced_with_the_dated_table(tmp_path):
    inducer, simulator, agent, judge = cost_summary(measured_store(tmp_path), prices=PRICES)
    assert inducer.usd == pytest.approx(2.0) and inducer.mean_seconds == 30.0
    assert simulator.usd == pytest.approx(1.0)
    assert judge.usd == pytest.approx(0.5 + 0.25)
    assert agent.usd == pytest.approx(0.04) and agent.usage.input_tokens == 500


def test_artifacts_without_a_record_are_counted_apart_never_as_zero(tmp_path):
    _, simulator, agent, _ = cost_summary(measured_store(tmp_path), prices=PRICES)
    assert (simulator.recorded, simulator.unrecorded) == (1, 1)
    assert (agent.recorded, agent.unrecorded) == (1, 1)


def test_a_model_without_a_price_is_reported_not_guessed(tmp_path):
    components = cost_summary(measured_store(tmp_path, judged_by="otro-modelo"), prices=PRICES)
    judge = components[3]
    assert judge.usd is None and judge.unpriced == {"otro-modelo"}
    text = render_cost(components)
    assert "sin precio en la tabla: otro-modelo" in text and "parcial" in text


def test_the_command_prints_the_date_of_the_prices(tmp_path):
    measured_store(tmp_path)
    result = CliRunner().invoke(cli.app, ["cost", "--data", str(tmp_path), "--run", RUN_ID])
    assert result.exit_code == 0, result.output
    assert "precios al 2026-10-16" in result.output and "evaluador" in result.output
    unknown = CliRunner().invoke(cli.app, ["cost", "--data", str(tmp_path), "--run", "x"])
    assert unknown.exit_code == 1
