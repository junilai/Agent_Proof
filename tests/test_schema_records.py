from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from agentproof.schema import Verdict, run_id_for, scenario_id_for
from tests.factories import manifest, scenario, verdict


def test_scenario_id_is_derived_from_its_seed():
    assert scenario_id_for("tr-abc") == "sc-tr-abc"
    with pytest.raises(ValidationError):
        scenario(scenario_id="sc-otra-cosa")


@pytest.mark.parametrize("count", [1, 6])
def test_scenario_has_between_two_and_five_criteria(count):
    with pytest.raises(ValidationError):
        scenario(success_criteria=[f"criterio {i}" for i in range(count)])


def test_verdict_passes_only_if_every_criterion_is_met():
    assert verdict([True, True]).passed is True
    assert verdict([True, False]).passed is False


def test_verdict_round_trip_keeps_its_result():
    original = verdict([True, False])
    data = original.model_dump_json()
    assert '"passed":false' in data
    assert Verdict.model_validate_json(data) == original


def test_verdict_needs_at_least_one_criterion():
    with pytest.raises(ValidationError):
        verdict([])


@pytest.mark.parametrize("field", ["repetitions", "turn_budget"])
def test_manifest_counts_must_be_positive(field):
    with pytest.raises(ValidationError):
        manifest(**{field: 0})


def test_run_id_combines_condition_and_time():
    when = datetime(2026, 10, 2, 15, 30, 0, tzinfo=UTC)
    assert run_id_for("baseline-a", when) == "baseline-a-20261002-153000"
