"""E3: fidelity of the induced scenarios, rated by three annotators (pre-registration §6)."""

import pytest

from experiments.f6.e3 import e3
from experiments.f6.labels import load
from tests.f6_fakes import asked, keys, rating, store, write_all

SCENARIOS = sorted(asked(2))


def analysed(tmp_path, fill):
    return e3(load(store(), write_all(tmp_path, two=fill), keys()).scenarios)


def by_annotator(likert, correction=None):
    """Each annotator gives its own rating to every scenario."""
    correction = correction or {}
    return lambda annotator, key, spec: {
        "likert": likert[annotator](key) if callable(likert[annotator]) else likert[annotator],
        "correction": correction.get(annotator, False),
    }


def test_every_scenario_rated_five_has_no_variation_to_measure_agreement(tmp_path):
    result = analysed(tmp_path, rating(5))
    assert result.scenarios == 20
    assert result.median_at_least_4 == 20 and result.share_median_at_least_4 == 1
    assert result.alpha_ordinal is None
    assert result.distribution["todos"] == {1: 0, 2: 0, 3: 0, 4: 0, 5: 60}
    assert result.needs_correction == 0


def test_annotators_who_rate_alike_have_full_agreement(tmp_path):
    score = {s: 1 + n % 5 for n, s in enumerate(SCENARIOS)}
    same = {a: score.__getitem__ for a in ("X1", "X2", "X3")}
    result = analysed(tmp_path, by_annotator(same))
    assert result.alpha_ordinal == 1
    assert all(p.alpha_ordinal == 1 and p.exact == 20 for p in result.pairs.values())
    assert result.median_at_least_4 == sum(v >= 4 for v in score.values()) == 8


def test_systematic_disagreement_is_seen_in_the_median_the_pairs_and_alpha(tmp_path):
    split = by_annotator({"X1": 5, "X2": 1, "X3": 3}, {"X1": True, "X2": True})
    result = analysed(tmp_path, split)
    assert {s.median for s in result.per_scenario} == {3}
    assert result.median_at_least_4 == 0
    assert result.alpha_ordinal < 0
    assert result.pairs["X1-X3"].exact == 0 and result.pairs["X1-X3"].within_one == 0
    assert result.pairs["X1-X3"].mean_difference == 2
    assert result.distribution["X2"] == {1: 20, 2: 0, 3: 0, 4: 0, 5: 0}
    assert result.needs_correction == 20 and result.share_needs_correction == 1


def test_near_ratings_count_within_one_point(tmp_path):
    near = by_annotator({"X1": 4, "X2": 5, "X3": 5})
    result = analysed(tmp_path, near)
    assert result.pairs["X1-X2"].within_one == 20 and result.pairs["X1-X2"].exact == 0
    assert result.pairs["X1-X2"].mean_difference == pytest.approx(-1)
    assert result.median_at_least_4 == 20
