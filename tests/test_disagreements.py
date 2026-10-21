import json
import random
from pathlib import Path

from agentproof.store import Store
from experiments.disagreements import (
    SEED,
    Rates,
    Repetition,
    direction,
    disagreement_sample,
    disagrees,
    origin,
    pick,
    rates,
)

ROOT = Path(__file__).resolve().parent.parent
PUBLISHED = ROOT / "results" / "samples" / "desacuerdos.json"


def rep(trace_id, predicate_fails, judge_passed):
    return Repetition(trace_id=trace_id, predicate_fails=predicate_fails, judge_passed=judge_passed)


def five(oracle, judge):
    return Rates(repetitions=5, oracle=oracle, judge=judge)


def test_a_repetition_is_discordant_in_either_direction():
    assert direction(rep("tr-1", True, True)) == "oráculo falla, evaluador aprueba"
    assert direction(rep("tr-1", False, False)) == "evaluador reprueba, oráculo no"


def test_a_repetition_where_both_agree_or_the_oracle_is_undecided_is_not_discordant():
    assert direction(rep("tr-1", True, False)) is None
    assert direction(rep("tr-1", False, True)) is None
    assert direction(rep("tr-1", None, True)) is None
    assert direction(rep("tr-1", None, False)) is None


def test_rates_count_the_failures_of_each_mechanism():
    reps = [rep("tr-1", True, True), rep("tr-2", False, False), rep("tr-3", True, False)]
    assert rates(reps) == Rates(repetitions=3, oracle=2, judge=2)


def test_both_mechanisms_over_the_threshold_is_an_aggregation_origin():
    assert origin(five(0, 0), five(2, 5)) == "agregación"
    assert origin(five(0, 0), five(5, 5)) == "agregación"


def test_one_mechanism_over_the_threshold_is_a_trace_origin():
    assert origin(five(0, 0), five(5, 1)) == "traza"
    assert origin(five(4, 0), five(5, 5)) == "traza"


def test_the_threshold_is_inclusive():
    assert origin(five(0, 0), five(2, 1)) == "traza"
    assert origin(five(0, 0), five(2, 2)) == "agregación"


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


def test_the_published_sample_is_the_one_the_seed_draws():
    published = json.loads(PUBLISHED.read_text(encoding="utf-8"))
    store = Store(ROOT)
    candidates = sorted({t["run_id"] for t in published["traces"]})
    drawn = disagreement_sample(store, published["reference"], candidates)
    assert published["seed"] == SEED
    assert published["traces"] == [d.model_dump() for d in drawn]
