"""Blind packages of F6: what each trace asks, and that nothing gives the condition away."""

import json
import re
from functools import cache
from pathlib import Path

from agentproof.models import pinned_model_ids
from agentproof.store import Store
from agentproof.transcript import render_transcript
from experiments.annotators import _messages, page, session_one, session_two, write_packages
from experiments.oracle.annotation import seed_and_card

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "results" / "samples"


@cache
def store():
    return Store(ROOT)


@cache
def one():
    return session_one(store())


def sample(name, key):
    found = json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))[key]
    return {f"{t['run_id']}/{t['trace_id']}" for t in found}


def trace(key):
    run_id, trace_id = key.split("/")
    return next(t for t in store().run_traces(run_id) if t.trace_id == trace_id)


def test_each_trace_of_the_three_samples_is_one_item():
    e2, audit, disagreements = (
        sample("e2", "pairs"),
        sample("auditoria", "traces"),
        sample("desacuerdos", "to_annotate"),
    )
    keys = [item["key"] for item in one()]
    left_out = (e2 | audit | disagreements) - set(keys)
    assert len(keys) == len(set(keys)) == 94
    assert len(left_out) == 4 and left_out <= audit - e2 - disagreements
    seeds = {s.trace_id: s for s in store().seeds()}
    cards = {seed_and_card(seeds, trace(k).scenario_id)[1] for k in left_out}
    assert all(not card.has_decision and not card.orders for card in cards)


def test_each_item_asks_what_its_samples_need():
    criteria = sample("e2", "pairs") | sample("desacuerdos", "to_annotate")
    facts = sample("auditoria", "traces") | sample("desacuerdos", "to_annotate")
    for item in one():
        scenario = store().scenario(trace(item["key"]).scenario_id)
        expected = scenario.success_criteria if item["key"] in criteria else []
        assert item["criteria"] == expected
        _, card = seed_and_card({s.trace_id: s for s in store().seeds()}, scenario.scenario_id)
        asked = ["decision"] * card.has_decision + ["contradicts_base"] * bool(card.orders)
        asked += ["answers_card"] * (card.intent == "estado_pedido")
        assert item["facts"] == (asked if item["key"] in facts else [])
        assert item["criteria"] or item["facts"], item["key"]


def test_tool_calls_are_shown_only_where_the_judge_criteria_are_asked():
    """The judge read them; the D-010 sheet hides them because they reveal the mutation."""
    for item in one():
        shown = any(m["who"] == "HERRAMIENTA" for m in item["messages"])
        made = any(e.kind == "tool_call" for e in trace(item["key"]).events)
        assert shown == (bool(item["criteria"]) and made)


def test_the_transcript_is_the_one_the_judge_reads():
    item = next(i for i in one() if i["criteria"])
    shown = "\n".join(f"[{m['who']}] {m['text']}" for m in _messages(trace(item["key"]), True))
    assert shown == render_transcript(trace(item["key"]))


def test_e3_shows_every_scenario_next_to_its_seed():
    items = session_two(store())
    assert sorted(i["key"] for i in items) == sorted(s.scenario_id for s in store().scenarios())
    assert all(i["criteria"] and i["messages"] for i in items)


def test_the_order_is_fixed_by_the_seed_and_the_items_are_opaque():
    assert [i["key"] for i in session_one(store())] == [i["key"] for i in one()]
    assert [i["item"] for i in one()] == [f"c{n:02d}" for n in range(1, 95)]


def test_the_page_gives_nothing_away(tmp_path):
    html = page(1, "X1", one())
    for item in one():
        run_id, trace_id = item["key"].split("/")
        assert trace_id not in html and run_id not in html
    for word in ("baseline", "d1-", "d4-", "variant", "condition", "veredicto"):
        assert word not in html
    assert not any(model in html for model in pinned_model_ids())
    assert re.search(r"__DATA__", html) is None


def test_the_key_is_written_apart_from_the_pages(tmp_path):
    written = write_packages(store(), tmp_path, ["X1", "X2"])
    assert {p.relative_to(tmp_path).as_posix() for p in written} == {
        "clave/sesion-1.json",
        "clave/sesion-2.json",
        "X1/sesion-1.html",
        "X1/sesion-2.html",
        "X2/sesion-1.html",
        "X2/sesion-2.html",
    }
    key = json.loads((tmp_path / "clave" / "sesion-1.json").read_text())
    assert key == {item["item"]: item["key"] for item in one()}
