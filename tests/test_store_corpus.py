import json
from datetime import timedelta

import pytest

from agentproof.store import Store
from tests.factories import T0, scenario, trace


def test_seed_is_saved_as_readable_json(tmp_path):
    path = Store(tmp_path).save_seed(trace())
    assert path == tmp_path / "corpus" / "seeds" / "tr-000000000001.json"
    content = path.read_text(encoding="utf-8")
    assert "¿En qué le ayudo?" in content and json.loads(content)["kind"] == "seed"


def test_seeds_are_listed_in_recording_order(tmp_path):
    store = Store(tmp_path)
    store.save_seed(trace(trace_id="tr-b", started_at=T0 + timedelta(minutes=5)))
    store.save_seed(trace(trace_id="tr-a", started_at=T0))
    assert [t.trace_id for t in store.seeds()] == ["tr-a", "tr-b"]


def test_run_traces_are_never_saved_as_seeds(tmp_path):
    with pytest.raises(ValueError):
        Store(tmp_path).save_seed(trace(kind="run"))


def test_empty_store_has_no_seeds_or_scenarios(tmp_path):
    store = Store(tmp_path)
    assert store.seeds() == [] and store.scenarios() == []


def test_scenario_is_saved_once_unless_overwritten(tmp_path):
    store = Store(tmp_path)
    assert store.save_scenario(scenario()) is True
    assert store.save_scenario(scenario(user_goal="otro objetivo")) is False
    assert store.scenario("sc-tr-000000000001").user_goal != "otro objetivo"
    assert store.save_scenario(scenario(user_goal="otro objetivo"), overwrite=True) is True
    assert store.scenario("sc-tr-000000000001").user_goal == "otro objetivo"
    assert store.has_scenario("sc-tr-000000000001") and len(store.scenarios()) == 1


def test_missing_scenario_raises_key_error(tmp_path):
    with pytest.raises(KeyError):
        Store(tmp_path).scenario("sc-no-existe")


def test_writes_leave_no_temporary_files(tmp_path):
    store = Store(tmp_path)
    store.save_seed(trace())
    store.save_scenario(scenario())
    assert not list(tmp_path.rglob("*.tmp"))
