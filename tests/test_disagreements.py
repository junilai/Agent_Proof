import random

from experiments.disagreements import SEED, Repetition, disagrees, pick


def rep(trace_id, predicate_fails, judge_passed):
    return Repetition(trace_id=trace_id, predicate_fails=predicate_fails, judge_passed=judge_passed)


def test_a_false_negative_disagrees_when_the_oracle_fails_and_the_judge_passes():
    assert disagrees("falso negativo", rep("tr-1", True, True))
    assert not disagrees("falso negativo", rep("tr-1", True, False))
    assert not disagrees("falso negativo", rep("tr-1", False, True))
    assert not disagrees("falso negativo", rep("tr-1", None, True))


def test_a_false_positive_disagrees_when_the_judge_fails_and_the_oracle_does_not():
    assert disagrees("falso positivo", rep("tr-1", False, False))
    assert not disagrees("falso positivo", rep("tr-1", True, False))
    assert not disagrees("falso positivo", rep("tr-1", False, True))
    assert not disagrees("falso positivo", rep("tr-1", None, False))


def test_only_a_repetition_that_disagrees_is_drawn():
    reps = [rep("tr-1", True, False), rep("tr-2", True, True), rep("tr-3", False, True)]
    assert pick("falso negativo", reps, random.Random(SEED)) == "tr-2"


def test_without_a_disagreeing_repetition_it_is_of_aggregation():
    reps = [rep("tr-1", True, False), rep("tr-2", False, True)]
    assert pick("falso negativo", reps, random.Random(SEED)) is None


def test_the_draw_does_not_depend_on_the_order_of_the_repetitions():
    reps = [rep(f"tr-{n}", True, True) for n in range(5)]
    drawn = pick("falso negativo", reps, random.Random(SEED))
    assert pick("falso negativo", reps[::-1], random.Random(SEED)) == drawn
