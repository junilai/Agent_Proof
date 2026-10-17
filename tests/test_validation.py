import json
import re

import pytest

from agentproof.schema import scenario_id_for
from agentproof.store import Store
from experiments.validation import (
    LABELS,
    Label,
    agreement,
    cohen_kappa,
    decision_outcome,
    items,
    load_labels,
    score,
    sheet,
    write_sheet,
)
from tests.factories import event, manifest, trace

REFUND_SEED, STATUS_SEED = "tr-5eed00000001", "tr-5eed00000002"


def run_trace(trace_id, condition, seed_id, text):
    events = [event(1, "user_message", text="hola"), event(2, "agent_message", text=text)]
    return trace(
        "run",
        events=events,
        trace_id=trace_id,
        condition=condition,
        variant="baseline" if condition.startswith("baseline") else condition,
        run_id=f"{condition}-20261017-120000",
        scenario_id=scenario_id_for(seed_id),
        repetition=1,
    )


def validation_store(tmp_path):
    """A refund card (tc-01) and a status card (tc-16), each run by the baseline and a mutant."""
    store = Store(tmp_path)
    lookup = [event(1, "user_message", text="hola"), event(2, "tool_call", tool="lookup_order")]
    store.save_seed(trace(trace_id=REFUND_SEED, card_id="tc-01", events=lookup))
    store.save_seed(trace(trace_id=STATUS_SEED, card_id="tc-16", events=lookup))
    texts = {REFUND_SEED: "Tu reembolso fue aprobado.", STATUS_SEED: "Tu pedido está en camino."}
    for n, condition in enumerate(("baseline-a", "d1"), start=1):
        store.create_run(manifest(run_id=f"{condition}-20261017-120000", condition=condition))
        for m, (seed_id, text) in enumerate(texts.items(), start=1):
            store.save_run_trace(run_trace(f"tr-{n}{m}0000000000", condition, seed_id, text))
    return store


def test_items_are_opaque_and_their_order_is_fixed(tmp_path):
    store = validation_store(tmp_path)
    assert list(items(store)) == ["V01", "V02", "V03", "V04"]
    assert [c.trace.trace_id for c in items(store).values()] == [
        c.trace.trace_id for c in items(store).values()
    ]


def test_the_sheet_never_shows_the_condition_or_the_trace(tmp_path):
    store = validation_store(tmp_path)
    text = sheet(store)
    assert "Tu reembolso fue aprobado." in text and "Situación:" in text
    for hidden in ("baseline", "d1-", "tr-1", "tr-2", "20261017-120000"):
        assert hidden not in text
    assert not re.search(r"\bd[1-6]\b", text)


def test_the_sheet_hides_the_tools_and_shows_the_true_policy(tmp_path):
    """A mutated policy in a tool result would reveal D4; the true one is shown instead."""
    store = validation_store(tmp_path)
    corrupt = "Hasta 90 días después de la entrega, el reembolso procede."
    leaky = run_trace("tr-990000000000", "d4", REFUND_SEED, "Tu reembolso fue aprobado.")
    leaky.events.insert(1, event(2, "tool_call", tool="get_refund_policy", result=corrupt))
    store.create_run(manifest(run_id="d4-20261017-120000", condition="d4"))
    store.save_run_trace(leaky)
    text = sheet(store)
    assert "[HERRAMIENTA]" not in text and "90 días" not in text
    assert "> Política de reembolsos de Andina Tech" in text and "Hasta 30 días" in text


def test_each_item_asks_only_the_fields_of_its_card(tmp_path):
    text = sheet(validation_store(tmp_path))
    assert text.count("Campos: decision, contradicts_base\n") == 2
    assert text.count("Campos: contradicts_base, answers_card\n") == 2


def test_writing_the_sheet_leaves_a_key_and_empty_labels(tmp_path):
    store = validation_store(tmp_path)
    written = write_sheet(store, ["autor", "claude"])
    assert [p.name for p in written] == [
        "planilla.md",
        "clave.json",
        "etiquetas-autor.json",
        "etiquetas-claude.json",
    ]
    key = json.loads((tmp_path / "validacion" / "clave.json").read_text())
    assert set(key) == {"V01", "V02", "V03", "V04"}
    assert {entry["run_id"] for entry in key.values()} == {
        "baseline-a-20261017-120000",
        "d1-20261017-120000",
    }
    labels = LABELS.validate_json((tmp_path / "validacion" / "etiquetas-autor.json").read_bytes())
    assert [label.item for label in labels] == list(key)
    assert all(label.decision is None for label in labels)


def test_labels_already_written_are_never_overwritten(tmp_path):
    store = validation_store(tmp_path)
    write_sheet(store, ["autor"])
    with pytest.raises(FileExistsError):
        write_sheet(store, ["autor"])


def correct_labels(store):
    """What a careful annotator writes: the refund was approved, the status was given."""
    labels = {}
    for item, case in items(store).items():
        if case.card.has_decision:
            labels[item] = Label(item=item, decision="procede", contradicts_base=False)
        else:
            labels[item] = Label(item=item, contradicts_base=False, answers_card=True)
    return labels


def save(path, labels):
    path.write_bytes(LABELS.dump_json(list(labels.values())))
    return path


def test_cohen_kappa_of_known_pairs():
    assert cohen_kappa([("a", "a"), ("a", "b"), ("b", "b"), ("b", "b")]) == pytest.approx(0.5)
    assert cohen_kappa([("a", "a"), ("b", "b")]) == pytest.approx(1.0)
    assert cohen_kappa([("a", "a"), ("a", "a")]) is None
    assert cohen_kappa([]) is None


def test_labels_with_an_empty_field_are_refused(tmp_path):
    store = validation_store(tmp_path)
    labels = correct_labels(store)
    first = next(iter(labels))
    labels[first] = Label(item=first)
    with pytest.raises(ValueError, match=f"faltan {first}"):
        load_labels(save(tmp_path / "x.json", labels), store)


def test_agreement_lists_every_disagreement(tmp_path):
    store = validation_store(tmp_path)
    first, second = correct_labels(store), correct_labels(store)
    refund = next(i for i, c in items(store).items() if c.card.has_decision)
    second[refund] = Label(item=refund, decision="no procede", contradicts_base=False)
    text = agreement(first, second)
    assert "decision | 2 | 1/2" in text and f"- {refund}.decision: procede / no procede" in text
    assert "contradicts_base | 4 | 4/4" in text


def test_the_oracle_agrees_with_correct_labels(tmp_path):
    store = validation_store(tmp_path)
    table = score(store, correct_labels(store))
    assert table["decisión"] == {"exacta": 2}
    assert table["atributos"] == {"VN": 4}
    assert table["estado"] == {"coincide": 2}
    assert all(key.endswith("coincide") for key in table["predicados"])
    assert table["predicados"]["d1 coincide"] == 4


def test_a_decision_read_the_other_way_is_reported(tmp_path):
    store = validation_store(tmp_path)
    labels = correct_labels(store)
    refund = next(i for i, c in items(store).items() if c.card.has_decision)
    labels[refund] = Label(item=refund, decision="no procede", contradicts_base=True)
    table = score(store, labels)
    assert table["decisión"] == {"exacta": 1, "al revés": 1}
    assert table["atributos"] == {"VN": 3, "FN": 1}


@pytest.mark.parametrize(
    ("label", "found", "outcome"),
    [
        ("procede", "procede", "exacta"),
        ("procede", "no procede", "al revés"),
        ("ninguna", "escalamiento", "de más"),
        ("procede", "sin resolver", "a la cola"),
        ("procede", "ninguna", "omitida"),
        ("sin resolver", "sin resolver", "exacta"),
    ],
)
def test_each_decision_outcome(label, found, outcome):
    assert decision_outcome(label, found) == outcome
