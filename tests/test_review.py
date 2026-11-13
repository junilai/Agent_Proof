import pytest
from pydantic import ValidationError

from agentproof import review as curation
from agentproof.store import Store
from tests.factories import T0, scenario, trace


def corpus(root, n=2):
    store = Store(root)
    for i in range(1, n + 1):
        seed_id = f"tr-{i:012d}"
        store.save_seed(trace(trace_id=seed_id))
        store.save_scenario(scenario(scenario_id=f"sc-{seed_id}", seed_trace_id=seed_id))
    return store


def snapshot(root):
    return {p.relative_to(root): p.read_text() for p in sorted(root.rglob("*.json"))}


def test_the_copy_has_the_seeds_and_the_induced_scenarios(tmp_path):
    source = corpus(tmp_path / "data")
    copy = Store(tmp_path / "curada")
    curation.start(source, copy)
    assert [s.trace_id for s in copy.seeds()] == [s.trace_id for s in source.seeds()]
    assert copy.scenarios() == source.scenarios()
    assert curation.reviews(copy) == {}


def test_the_copy_never_goes_in_the_same_folder(tmp_path):
    source = corpus(tmp_path)
    with pytest.raises(ValueError):
        curation.start(source, Store(tmp_path))


def test_a_correction_keeps_the_scenario_and_records_the_reviewer():
    original = scenario()
    fixed = curation.corrected(
        original,
        goal="Otro objetivo",
        opening=original.opening_message,
        criteria=["Uno", "Dos", "Tres"],
        reviewer="autor",
        now=T0,
    )
    assert (fixed.scenario_id, fixed.seed_trace_id) == (
        original.scenario_id,
        original.seed_trace_id,
    )
    assert fixed.user_goal == "Otro objetivo"
    assert fixed.success_criteria == ["Uno", "Dos", "Tres"]
    assert fixed.induced_by == "claude-opus-5; revisado por autor"


def test_a_correction_still_needs_two_to_five_criteria():
    with pytest.raises(ValidationError):
        curation.corrected(
            scenario(), goal="g", opening="o", criteria=["Solo uno"], reviewer="autor", now=T0
        )
