"""Agreement statistics of F6, checked against published values."""

import pytest

from experiments.f6.agreement import cohen_matrix, fleiss_kappa, krippendorff_alpha, majority

# Fleiss (1971), as reproduced in most references: 10 subjects, 14 raters, 5 categories.
FLEISS_COUNTS = [
    (0, 0, 0, 0, 14),
    (0, 2, 6, 4, 2),
    (0, 0, 3, 5, 6),
    (0, 3, 9, 2, 0),
    (2, 2, 8, 1, 1),
    (7, 7, 0, 0, 0),
    (3, 2, 6, 3, 0),
    (2, 5, 3, 2, 2),
    (6, 5, 2, 1, 0),
    (0, 2, 2, 3, 7),
]

# Krippendorff, "Computing Krippendorff's alpha-reliability" (2011): 4 observers, 12 units.
_ = None
KRIPPENDORFF_UNITS = [
    (1, 1, _, 1),
    (2, 2, 3, 2),
    (3, 3, 3, 3),
    (3, 3, 3, 3),
    (2, 2, 2, 2),
    (1, 2, 3, 4),
    (4, 4, 4, 4),
    (1, 1, 2, 1),
    (2, 2, 2, 2),
    (_, 5, 5, 5),
    (_, _, 1, 1),
    (_, 3, _, _),
]


def expand(counts):
    return [[category for category, n in enumerate(row) for _ in range(n)] for row in counts]


def test_fleiss_kappa_matches_the_published_example():
    assert fleiss_kappa(expand(FLEISS_COUNTS)) == pytest.approx(0.210, abs=5e-4)


def test_fleiss_kappa_is_one_with_perfect_agreement_and_negative_when_raters_split():
    assert fleiss_kappa([[True] * 3, [False] * 3, [True] * 3]) == 1
    assert fleiss_kappa([[True, False, True], [False, True, False]]) < 0


def test_fleiss_kappa_is_undefined_when_chance_explains_everything():
    assert fleiss_kappa([[True] * 3, [True] * 3]) is None
    assert fleiss_kappa([]) is None


def test_fleiss_kappa_needs_the_same_raters_for_every_item():
    with pytest.raises(ValueError):
        fleiss_kappa([[True, True, False], [True, False]])


@pytest.mark.parametrize(
    ("metric", "published"), [("nominal", 0.743), ("ordinal", 0.815), ("interval", 0.849)]
)
def test_krippendorff_alpha_matches_the_published_example(metric, published):
    assert krippendorff_alpha(KRIPPENDORFF_UNITS, metric) == pytest.approx(published, abs=5e-4)


def test_krippendorff_alpha_is_one_with_perfect_agreement():
    assert krippendorff_alpha([(4, 4, 4), (5, 5, 5), (2, 2, 2)]) == 1


def test_krippendorff_alpha_is_undefined_without_variation_or_pairable_values():
    assert krippendorff_alpha([(5, 5, 5), (5, 5, 5)]) is None
    assert krippendorff_alpha([(5, _, _), (_, 4, _)]) is None
    assert krippendorff_alpha([]) is None


def test_ordinal_alpha_weighs_distant_disagreements_more_than_near_ones():
    near = krippendorff_alpha([(4, 5, 5), (1, 1, 1), (3, 3, 3), (5, 5, 5)])
    far = krippendorff_alpha([(1, 5, 5), (1, 1, 1), (3, 3, 3), (5, 5, 5)])
    assert 1 > near > far


def test_ordinal_alpha_ignores_unused_categories():
    """Ordinal distances depend on how many values fall between two ranks, not on the gap."""
    assert krippendorff_alpha([(1, 2), (2, 2), (1, 1)]) == krippendorff_alpha(
        [(1, 5), (5, 5), (1, 1)]
    )


def test_krippendorff_alpha_refuses_an_unknown_metric():
    with pytest.raises(ValueError):
        krippendorff_alpha(KRIPPENDORFF_UNITS, "ratio")


def test_cohen_matrix_has_every_pair_of_raters_once():
    labels = {"X1": [True, False, True], "X2": [True, False, True], "X3": [False, True, False]}
    matrix = cohen_matrix(labels)
    assert set(matrix) == {("X1", "X2"), ("X1", "X3"), ("X2", "X3")}
    assert matrix["X1", "X2"] == 1 and matrix["X1", "X3"] < 0


def test_majority_needs_more_than_half_of_the_votes():
    assert majority([True, True, False]) is True
    assert majority(["procede", "ninguna", "procede"]) == "procede"
    assert majority(["procede", "ninguna", "escalamiento"]) is None
