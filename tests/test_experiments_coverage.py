from agentproof.store import Store
from experiments.coverage import coverage, render_coverage
from tests.factories import event, trace


def seed(card_id, tools=(), **overrides):
    events = [event(1, "user_message", text="hola")]
    events += [event(i, "tool_call", tool=tool) for i, tool in enumerate(tools, start=2)]
    return trace(card_id=card_id, events=events, **overrides)


def store_with(tmp_path, *seeds):
    store = Store(tmp_path)
    for one in seeds:
        store.save_seed(one)
    return store


def test_counts_what_is_recorded_and_what_is_missing(tmp_path):
    store = store_with(tmp_path, seed("tc-01", ["lookup_order"], trace_id="tr-a"))
    report = coverage(store)
    assert report.recorded["tc-01"] == 1
    assert "tc-01" not in report.pending and "tc-20" in report.pending
    assert len(report.pending) == 19


def test_seeds_without_a_known_card_are_reported(tmp_path):
    store = store_with(tmp_path, seed(None, trace_id="tr-a"), seed("tc-99", trace_id="tr-b"))
    report = coverage(store)
    assert report.problems == {"tr-a": "sin tarjeta", "tr-b": "tarjeta desconocida: tc-99"}


def test_the_trace_operators_split_into_exposed_and_control(tmp_path):
    store = store_with(
        tmp_path,
        seed("tc-01", ["lookup_order", "get_refund_policy", "create_ticket"], trace_id="tr-a"),
        seed("tc-16", ["lookup_order"], trace_id="tr-b"),
        seed("tc-20", [], trace_id="tr-c"),
    )
    report = coverage(store)
    assert report.exposed["D1"] == ["tr-a", "tr-b"] and report.control["D1"] == ["tr-c"]
    assert report.exposed["D4"] == ["tr-a"] and report.control["D4"] == ["tr-b", "tr-c"]
    assert report.exposed["D6"] == ["tr-a"] and report.control["D6"] == ["tr-b", "tr-c"]


def test_the_rendering_warns_about_empty_sets_and_problems(tmp_path):
    store = store_with(tmp_path, seed("tc-01", ["lookup_order"], trace_id="tr-a"))
    text = render_coverage(coverage(store))
    assert "1 de 20" in text and "tc-02" in text
    assert "D4" in text and "vacío" in text
