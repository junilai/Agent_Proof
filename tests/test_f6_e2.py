"""E2: the judge against the majority of three annotators (pre-registration §6)."""

import json

import pytest

from experiments.f6.e2 import e2, natural_approval
from experiments.f6.labels import load
from tests.f6_fakes import ROOT, constant, keys, like_the_judge, store, write_all

PAIRS = json.loads((ROOT / "results" / "samples" / "e2.json").read_text())["pairs"]


def analysed(tmp_path, fill):
    return e2(store(), load(store(), write_all(tmp_path, fill), keys()).traces)


def test_annotators_who_read_like_the_judge_agree_with_it_fully(tmp_path):
    result = analysed(tmp_path, like_the_judge())
    assert result.pairs == 40
    assert result.fleiss_approval == 1 and result.fleiss_criteria == 1
    assert set(result.cohen_approval.values()) == {1}
    assert result.majority_approved == 20
    assert (result.judge_approval.agreed, result.judge_approval.total) == (40, 40)
    assert result.judge_approval.kappa == 1
    assert result.judge_criteria.agreed == result.judge_criteria.total > 40
    assert {s: (r.pairs, r.judge_agreed) for s, r in result.strata.items()} == {
        "aprobado": (20, 20),
        "reprobado": (20, 20),
    }


def test_one_annotator_reading_against_the_others_lowers_their_agreement_only(tmp_path):
    result = analysed(tmp_path, like_the_judge(inverted=frozenset({"X2"})))
    assert result.fleiss_approval < 1
    assert result.cohen_approval["X1-X3"] == 1
    assert result.cohen_approval["X1-X2"] <= 0 and result.cohen_criteria["X2-X3"] < 0
    assert result.judge_approval.agreed == 40


def test_when_every_annotator_approves_the_judge_agrees_only_where_it_passed(tmp_path):
    result = analysed(tmp_path, constant(met=True))
    assert result.fleiss_approval is None  # no variation: chance explains it all
    assert result.approvals == {"X1": 40, "X2": 40, "X3": 40}
    assert result.majority_approved == 40
    assert result.judge_approval.agreed == 20 and result.judge_approval.kappa == 0
    assert result.strata["aprobado"].judge_agreed == 20
    assert result.strata["reprobado"].judge_agreed == 0


def test_each_trace_keeps_its_stratum_votes_and_verdict(tmp_path):
    result = analysed(tmp_path, like_the_judge(inverted=frozenset({"X1", "X2"})))
    assert [(t.key, t.stratum) for t in result.traces] == [
        (f"{p['run_id']}/{p['trace_id']}", p["stratum"]) for p in PAIRS
    ]
    for t in result.traces:
        assert t.judge_passed == (t.stratum == "aprobado")
        assert t.approvals == {
            "X1": t.approvals["X1"],
            "X2": t.approvals["X1"],
            "X3": t.judge_passed,
        }
    assert result.judge_criteria.agreed == 0
    assert result.strata["aprobado"].judge_agreed == 0


def test_the_natural_approval_of_e1_is_reported_apart():
    natural = natural_approval(store())
    assert (natural.passed, natural.judged) == (413, 800)
    assert natural.share == pytest.approx(413 / 800)
