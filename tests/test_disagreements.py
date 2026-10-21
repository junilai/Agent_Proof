import random

from experiments.disagreements import (
    SEED,
    Cell,
    Disagreement,
    Rates,
    Repetition,
    cells,
    direction,
    origin,
    rates,
    to_annotate,
)


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


def test_one_cell_per_direction_with_a_drawn_discordant_repetition():
    reps = [rep("tr-1", True, True), rep("tr-2", False, False), rep("tr-3", False, False)]
    found = cells("candidata", "d1-run", reps, random.Random(SEED))
    assert [(c.direction, c.discordant) for c in found] == [
        ("oráculo falla, evaluador aprueba", 1),
        ("evaluador reprueba, oráculo no", 2),
    ]
    assert found[0].trace_id == "tr-1"
    assert found[1].trace_id in {"tr-2", "tr-3"}


def test_a_run_without_discordant_repetitions_has_no_cells():
    reps = [rep("tr-1", True, False), rep("tr-2", False, True)]
    assert cells("referencia", "base-run", reps, random.Random(SEED)) == []


def test_the_draw_does_not_depend_on_the_order_of_the_repetitions():
    reps = [rep(f"tr-{n}", True, True) for n in range(5)]
    drawn = cells("candidata", "run", reps, random.Random(SEED))
    assert cells("candidata", "run", reps[::-1], random.Random(SEED)) == drawn


def test_a_trace_drawn_for_two_operators_is_annotated_once():
    cell = Cell(
        run="referencia",
        run_id="base",
        direction="evaluador reprueba, oráculo no",
        discordant=2,
        trace_id="tr-9",
    )

    def found(operator):
        return Disagreement(
            operator=operator,
            kind="falso negativo",
            scenario_id="sc-1",
            reference=five(0, 2),
            candidate=five(2, 2),
            origin="traza",
            cells=[cell],
        )

    assert [t.trace_id for t in to_annotate([found("d1"), found("d2")])] == ["tr-9"]
