import pytest

from agentproof.store import Store
from tests.factories import RUN_FIELDS, manifest, trace, verdict

RUN_ID = RUN_FIELDS["run_id"]


def test_run_is_created_once(tmp_path):
    store = Store(tmp_path)
    folder = store.create_run(manifest())
    assert folder == tmp_path / "results" / "runs" / RUN_ID
    assert store.manifest(RUN_ID) == manifest() and store.runs() == [RUN_ID]
    with pytest.raises(FileExistsError):
        store.create_run(manifest())


def test_unknown_run_raises_key_error(tmp_path):
    store = Store(tmp_path)
    with pytest.raises(KeyError):
        store.manifest("no-existe")
    with pytest.raises(KeyError):
        store.save_run_trace(trace(kind="run"))
    with pytest.raises(KeyError):
        store.save_verdict(verdict([True]))


def test_seed_traces_cannot_be_saved_in_a_run(tmp_path):
    store = Store(tmp_path)
    store.create_run(manifest())
    with pytest.raises(ValueError):
        store.save_run_trace(trace())


def test_run_traces_are_listed_by_scenario_and_repetition(tmp_path):
    store = Store(tmp_path)
    store.create_run(manifest())
    store.save_run_trace(trace(kind="run", trace_id="tr-2", repetition=2))
    store.save_run_trace(trace(kind="run", trace_id="tr-1", repetition=1))
    assert [t.repetition for t in store.run_traces(RUN_ID)] == [1, 2]
    assert (tmp_path / "results" / "runs" / RUN_ID / "traces" / "tr-1.json").exists()


def test_verdicts_are_idempotent_per_trace(tmp_path):
    store = Store(tmp_path)
    store.create_run(manifest())
    store.save_verdict(verdict([True, False]))
    store.save_verdict(verdict([True, True]))
    assert [v.passed for v in store.verdicts(RUN_ID)] == [True]
    assert store.has_verdict(RUN_ID, "tr-000000000002")
    assert not store.has_verdict(RUN_ID, "tr-otra")
