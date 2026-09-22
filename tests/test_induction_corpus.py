from agentproof.induction import induce_missing
from agentproof.store import Store
from tests.factories import scenario, trace


def fake_induce(seed):
    return scenario(scenario_id=f"sc-{seed.trace_id}", seed_trace_id=seed.trace_id)


def test_induces_each_seed_once(tmp_path):
    store = Store(tmp_path)
    store.save_seed(trace(trace_id="tr-a"))
    store.save_seed(trace(trace_id="tr-b"))
    first = induce_missing(store, induce=fake_induce)
    second = induce_missing(store, induce=fake_induce)
    assert sorted(first.created) == ["sc-tr-a", "sc-tr-b"] and first.kept == []
    assert second.created == [] and sorted(second.kept) == ["sc-tr-a", "sc-tr-b"]
    assert len(store.scenarios()) == 2


def test_a_failed_seed_is_reported_and_the_rest_continue(tmp_path):
    store = Store(tmp_path)
    store.save_seed(trace(trace_id="tr-a"))
    store.save_seed(trace(trace_id="tr-b"))

    def flaky(seed):
        if seed.trace_id == "tr-a":
            raise RuntimeError("el modelo no respondió")
        return fake_induce(seed)

    summary = induce_missing(store, induce=flaky)
    assert summary.created == ["sc-tr-b"]
    assert summary.failed == {"sc-tr-a": "RuntimeError: el modelo no respondió"}
    assert not store.has_scenario("sc-tr-a")
