"""D-016: each drawn discordance attributed from the majority of three annotators."""

import json

import pytest

from experiments.f6.attribution import attribute, attribution
from experiments.f6.labels import load
from tests.f6_fakes import ROOT, constant, keys, like_the_oracle, store, write_all

SAMPLE = json.loads((ROOT / "results" / "samples" / "desacuerdos.json").read_text())
CELLS = [c for d in SAMPLE["disagreements"] for c in d["cells"]]
OK, BAD = "oráculo falla, evaluador aprueba", "evaluador reprueba, oráculo no"


@pytest.mark.parametrize(
    ("oracle", "labels", "judge", "passed", "causes"),
    [
        (True, False, True, True, ["reglas del oráculo"]),
        (False, False, False, True, ["evaluador"]),
        (True, False, True, False, ["reglas del oráculo", "evaluador"]),
        (True, True, True, True, ["alcance distinto"]),
        (False, False, False, False, ["alcance distinto"]),
    ],
)
def test_each_discordance_goes_to_the_mechanism_the_labels_contradict(
    oracle, labels, judge, passed, causes
):
    assert attribute(oracle, labels, judge, passed) == (causes, None)


def test_a_repetition_that_no_longer_disagrees_or_that_no_one_settles_goes_apart():
    assert attribute(False, False, True, True) == ([], "ya no es discordante")
    assert attribute(None, True, True, True) == ([], "el oráculo no lo resuelve")
    assert attribute(True, None, True, True) == ([], "las etiquetas no lo resuelven")


def analysed(tmp_path, fill):
    return attribution(store(), load(store(), write_all(tmp_path, fill), keys()).traces)


def test_every_drawn_cell_is_attributed_once_with_its_weight(tmp_path):
    result = analysed(tmp_path, like_the_oracle())
    assert len(result.cells) == len(CELLS) == 23
    assert [c.discordant for c in result.cells] == [c["discordant"] for c in CELLS]
    attributed = [c for c in result.cells if not c.apart]
    assert result.by_cause["alcance distinto"].cells == len(attributed)
    assert result.by_cause["alcance distinto"].repetitions == sum(c.discordant for c in attributed)


def test_annotators_who_read_like_the_oracle_and_the_judge_leave_only_scope(tmp_path):
    result = analysed(tmp_path, like_the_oracle())
    for cell in result.cells:
        assert cell.causes in (["alcance distinto"], []), cell
        assert cell.labels_passed == cell.judge_passed


def test_annotators_who_find_every_criterion_met_blame_the_judge_where_it_failed(tmp_path):
    result = analysed(tmp_path, _all_met())
    for cell in result.cells:
        assert cell.labels_passed
        if not cell.apart:
            assert ("evaluador" in cell.causes) == (not cell.judge_passed)
    assert result.by_cause["evaluador"].cells > 0


def _all_met():
    base = like_the_oracle()

    def fill(annotator, key, spec):
        return base(annotator, key, spec) | {"criteria": [True] * len(spec["criteria"])}

    return fill


def test_a_fact_every_annotator_reads_against_the_rules_blames_the_rules(tmp_path):
    result = analysed(tmp_path, constant(decision="ninguna", contradicts=True, met=False))
    d1 = [c for c in result.cells if c.operator == "d1" and not c.apart]
    assert d1 and all(c.labels_fails for c in d1)
    for cell in d1:
        assert ("reglas del oráculo" in cell.causes) == (cell.oracle_fails is False)


def test_counts_are_split_by_operator_run_and_direction(tmp_path):
    result = analysed(tmp_path, like_the_oracle())
    for split in (result.by_operator, result.by_run, result.by_direction):
        assert sum(counts.get("alcance distinto", 0) for counts in split.values()) == (
            result.by_cause["alcance distinto"].repetitions
        )
    assert set(result.by_direction) <= {OK, BAD}
