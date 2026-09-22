import json

from agentproof import models


def test_identifiers_match_the_planning_table():
    assert models.INDUCER.model == "claude-opus-5"
    assert models.JUDGE.model == "claude-opus-5"
    assert models.SIM_USER.model == "claude-haiku-4-5-20251001"
    assert models.TARGET_BASELINE_MODEL == "claude-sonnet-5"
    assert models.TARGET_DOWNGRADED_MODEL == "claude-haiku-4-5-20251001"


def test_judge_is_different_from_the_agent_it_grades():
    assert models.JUDGE.model not in {models.TARGET_BASELINE_MODEL, models.TARGET_DOWNGRADED_MODEL}


def test_reasoning_effort_is_pinned_where_the_model_accepts_it():
    assert models.INDUCER.effort == models.JUDGE.effort == "high"
    assert models.SIM_USER.effort is None


def test_snapshot_records_every_component_as_json():
    snap = models.snapshot()
    assert set(snap) == {"inducer", "judge", "sim_user", "target_baseline", "target_downgraded"}
    assert json.loads(json.dumps(snap)) == snap
    assert snap["judge"]["effort"] == "high"


def test_pinned_model_ids():
    assert models.pinned_model_ids() == {
        "claude-opus-5",
        "claude-sonnet-5",
        "claude-haiku-4-5-20251001",
    }
