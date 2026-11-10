import hashlib
import json
import random
from functools import cache
from pathlib import Path

from agentproof.store import Store
from experiments.disagreements import (
    SEED,
    Cell,
    Disagreement,
    Rates,
    Repetition,
    cells,
    direction,
    disagreements,
    origin,
    rates,
    to_annotate,
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


@cache
def published():
    return json.loads(PUBLISHED.read_text(encoding="utf-8"))


def in_e1(operator, scenario_id):
    """A disagreement of E1 as published."""
    return next(
        d
        for d in published()["disagreements"]
        if d["operator"] == operator and d["scenario_id"] == scenario_id
    )


FROZEN_SHA256 = "1a9656e3481e93a418107aaea8ed4d088a5b5819de7ed08352ec2c98b42ce6bc"
RESOLVED_BY_AMENDMENT_2 = {("d2", "sc-tr-69b396c04669")}
"""Read the wrong way by the oracle of preregistro-v2 (LangGraph calibration, D-005)."""


def test_the_published_sample_is_frozen_on_the_original_scoring_of_e1():
    """Drawn with the seed and the oracle of preregistro-v2; amendment 2 does not redraw it.

    The draw goes through the disagreements in order, so removing one would change the
    traces drawn for later ones. With the code at that tag, the seed reproduces the file.
    """
    assert hashlib.sha256(PUBLISHED.read_bytes()).hexdigest() == FROZEN_SHA256
    assert published()["seed"] == SEED


def _without_draws(found):
    return {
        **found,
        "cells": [{k: v for k, v in c.items() if k != "trace_id"} for c in found["cells"]],
    }


def test_amendment_2_only_removes_the_disagreement_it_resolved():
    sample = published()
    found = disagreements(Store(ROOT), sample["reference"], sample["candidates"])
    expected = [
        _without_draws(d)
        for d in sample["disagreements"]
        if (d["operator"], d["scenario_id"]) not in RESOLVED_BY_AMENDMENT_2
    ]
    assert [_without_draws(d.model_dump()) for d in found] == expected


def test_d1_d707_has_discordant_repetitions_and_an_aggregation_origin():
    """First example of the tutor: oracle 2/5, judge 5/5 in the candidate."""
    found = in_e1("d1", "sc-tr-d707df857e02")
    assert (found["candidate"]["oracle"], found["candidate"]["judge"]) == (2, 5)
    assert found["origin"] == "agregación"
    assert [(c["run"], c["direction"], c["discordant"]) for c in found["cells"]] == [
        ("candidata", "evaluador reprueba, oráculo no", 3)
    ]


def test_d4_e326_counts_the_discordances_of_the_reference():
    """Second example of the tutor: oracle 4/5, judge 0/5 in the reference."""
    found = in_e1("d4", "sc-tr-e326cdcb18af")
    assert (found["reference"]["oracle"], found["reference"]["judge"]) == (4, 0)
    assert [(c["run"], c["direction"], c["discordant"]) for c in found["cells"]] == [
        ("referencia", "oráculo falla, evaluador aprueba", 4)
    ]


def test_only_one_disagreement_has_no_discordant_repetition():
    without = [d["scenario_id"] for d in published()["disagreements"] if not d["cells"]]
    assert without == ["sc-tr-3ee71ca0bdcf"]
