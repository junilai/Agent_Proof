from casestudy.domain.mutations import MUTATIONS
from experiments.conditions import (
    CONDITIONS,
    CONDITIONS_BY_NAME,
    NEGATIVE_CONTROL,
    REFERENCE,
    candidates,
)


def test_eight_conditions_with_unique_names():
    assert len(CONDITIONS) == 8 and len(CONDITIONS_BY_NAME) == 8


def test_one_reference_and_one_negative_control_of_the_baseline():
    roles = [c.role for c in CONDITIONS]
    assert roles.count("reference") == 1 and roles.count("negative_control") == 1
    assert (REFERENCE.name, REFERENCE.variant) == ("baseline-a", "baseline")
    assert (NEGATIVE_CONTROL.name, NEGATIVE_CONTROL.variant) == ("baseline-b", "baseline")


def test_every_candidate_applies_its_own_mutation():
    assert [c.name for c in candidates()] == ["d1", "d2", "d3", "d4", "d5", "d6"]
    assert all(c.variant == c.name for c in candidates())
    assert all(c.variant in MUTATIONS for c in CONDITIONS)
