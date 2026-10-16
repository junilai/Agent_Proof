from fractions import Fraction

import pytest

from agentproof.stats import benjamini_hochberg, fisher_exact


@pytest.mark.parametrize(
    ("repetitions", "expected"),
    [(3, Fraction(1, 10)), (4, Fraction(1, 35)), (5, Fraction(1, 126)), (6, Fraction(1, 462))],
)
def test_the_extreme_case_gives_the_p_values_of_the_planning(repetitions, expected):
    """§5.5: 0.100, 0.029, 0.0079 and 0.0022 when every repetition flips."""
    assert fisher_exact(repetitions, repetitions, 0, repetitions) == expected


def test_the_test_is_two_sided_and_symmetric():
    assert fisher_exact(5, 5, 0, 5) == fisher_exact(0, 5, 5, 5)
    assert fisher_exact(5, 5, 3, 5) == fisher_exact(3, 5, 5, 5) == Fraction(4, 9)


def test_equal_tables_and_empty_runs_carry_no_evidence():
    assert fisher_exact(3, 5, 3, 5) == 1
    assert fisher_exact(5, 5, 0, 0) == 1


def test_an_intermediate_table():
    """4/5 against 1/5: tables 0, 1, 4 and 5 of 252 weigh 1 + 25 + 25 + 1 (0.2063)."""
    assert fisher_exact(4, 5, 1, 5) == Fraction(26, 126)


def flips(count, others=20):
    """count scenarios that went from 5/5 to 0/5 among `others` comparisons."""
    p_values = {f"sc-{i:02d}": Fraction(1) for i in range(others)}
    p_values.update({f"sc-{i:02d}": fisher_exact(5, 5, 0, 5) for i in range(count)})
    return p_values


@pytest.mark.parametrize(("count", "rejected"), [(1, 0), (3, 0), (4, 4), (6, 6)])
def test_with_r_5_only_joint_regressions_survive_the_correction(count, rejected):
    """§5.5: 0.0079 needs at least four scenarios regressing together among twenty."""
    assert len(benjamini_hochberg(flips(count))) == rejected


def test_with_r_6_an_isolated_regression_survives():
    p_values = {f"sc-{i:02d}": Fraction(1) for i in range(20)}
    p_values["sc-00"] = fisher_exact(6, 6, 0, 6)
    assert benjamini_hochberg(p_values) == {"sc-00"}


def test_the_step_up_rule_rejects_everything_below_the_largest_k():
    """p(1) misses its own threshold (0.0125) but p(2) meets 0.025: both are rejected."""
    p_values = {"a": Fraction(2, 100), "b": Fraction(24, 1000), "c": Fraction(1, 2), "d": 1}
    assert benjamini_hochberg(p_values) == {"a", "b"}
    assert benjamini_hochberg({}) == set()
