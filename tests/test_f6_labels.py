"""Loading the label files of F6: complete, or refused with every gap named."""

import json

import pytest

from experiments.f6.labels import load
from tests.f6_fakes import ANNOTATORS, asked, constant, keys, rating, store, write_all


def test_complete_files_give_every_trace_and_scenario_per_annotator(tmp_path):
    labels = load(store(), write_all(tmp_path, constant(), rating(4, True)), keys())
    assert labels.annotators == list(ANNOTATORS)
    for annotator in ANNOTATORS:
        assert set(labels.traces[annotator]) == set(asked(1))
        assert set(labels.scenarios[annotator]) == set(asked(2))
    key = next(k for k, spec in asked(1).items() if spec["criteria"] and spec["facts"])
    label = labels.traces["X1"][key]
    assert label.criteria == (True,) * len(asked(1)[key]["criteria"])
    assert label.contradicts_base is False
    assert labels.scenarios["X2"][next(iter(asked(2)))].likert == 4


def test_a_field_the_item_does_not_ask_is_ignored(tmp_path):
    folder = write_all(tmp_path, constant())
    labels = load(store(), folder, keys())
    key = next(k for k, spec in asked(1).items() if not spec["facts"])
    assert labels.traces["X1"][key].decision is None


def test_a_session_without_files_is_left_empty(tmp_path):
    labels = load(store(), write_all(tmp_path, constant()), keys())
    assert labels.scenarios == {}


def edit(path, change):
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_missing_items_and_empty_fields_are_named(tmp_path):
    folder = write_all(tmp_path, constant(), rating())
    path = folder / "etiquetas-X2-sesion-1.json"
    rows = json.loads(path.read_text(encoding="utf-8"))["labels"]
    key = json.loads((keys() / "sesion-1.json").read_text(encoding="utf-8"))
    with_decision = next(r for r in rows if "decision" in asked(1)[key[r["item"]]]["facts"])
    with_criteria = next(r for r in rows if r["criteria"])

    def change(data):
        data["labels"] = [r for r in data["labels"] if r["item"] != rows[0]["item"]]
        for r in data["labels"]:
            if r["item"] == with_decision["item"]:
                r["decision"] = None
            if r["item"] == with_criteria["item"]:
                r["criteria"][-1] = None

    edit(path, change)
    edit(folder / "etiquetas-X3-sesion-2.json", lambda d: d["labels"][0].update(likert=6))
    with pytest.raises(ValueError) as error:
        load(store(), folder, keys())
    message = str(error.value)
    assert "etiquetas-X2-sesion-1.json" in message and "etiquetas-X3-sesion-2.json" in message
    assert f"falta el ítem {rows[0]['item']}" in message
    if with_decision["item"] != rows[0]["item"]:
        assert f"{with_decision['item']}: falta decision" in message
    assert f"falta el criterio {len(with_criteria['criteria'])}" in message
    assert "likert debe ser un entero de 1 a 5" in message


def test_a_wrong_value_or_an_unknown_item_is_refused(tmp_path):
    folder = write_all(tmp_path, constant())
    path = folder / "etiquetas-X1-sesion-1.json"
    edit(path, lambda d: d["labels"].append({"item": "c999", "criteria": []}))
    with pytest.raises(ValueError, match="ítem desconocido c999"):
        load(store(), folder, keys())
    write_all(tmp_path, constant(decision="quizá"))
    with pytest.raises(ValueError, match="decision no es una de"):
        load(store(), folder, keys())


def test_three_annotators_are_required_in_each_session(tmp_path):
    folder = write_all(tmp_path, constant())
    (folder / "etiquetas-X3-sesion-1.json").unlink()
    with pytest.raises(ValueError, match="sesión 1: se esperan 3 anotadores"):
        load(store(), folder, keys())


def test_the_file_name_and_its_content_must_agree(tmp_path):
    folder = write_all(tmp_path, constant())
    edit(folder / "etiquetas-X1-sesion-1.json", lambda d: d.update(annotator="X9"))
    with pytest.raises(ValueError, match="dice ser de X9, sesión 1"):
        load(store(), folder, keys())


def test_the_same_annotators_label_both_sessions(tmp_path):
    folder = write_all(tmp_path, constant(), rating())
    path = folder / "etiquetas-X3-sesion-2.json"
    edit(path, lambda d: d.update(annotator="X4"))
    path.rename(folder / "etiquetas-X4-sesion-2.json")
    with pytest.raises(ValueError, match="no son los mismos anotadores"):
        load(store(), folder, keys())
