"""The figures read the published results: these are the figures the thesis reports."""

from fractions import Fraction
from pathlib import Path

import pytest

from agentproof.store import Store
from experiments.figures import data

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def store():
    return Store(ROOT)


def test_detection_of_d4_in_both_frameworks(store):
    found = {(c.operator, c.framework): c for c in data.classifications(store)}
    assert len(found) == 8
    sdk, lg = found[("d4", "SDK")], found[("d4", "LangGraph")]
    assert (sdk.vp, sdk.fp, sdk.fn, sdk.vn) == (6, 1, 0, 13)
    assert (lg.vp, lg.fp, lg.fn, lg.vn) == (6, 2, 0, 12)
    assert found[("d6", "SDK")].fp_exposed == 5


def test_the_baseline_approves_two_thirds_in_e1(store):
    table = data.approval_by_scenario(store, data.E1)
    assert set(table) == {"línea base", "control", "D1", "D2", "D3", "D4", "D5", "D6"}
    rates = table["línea base"].values()
    assert len(rates) == 20 and sum(rates) / 20 == Fraction(67, 100)
    assert data.pass_k(store, data.E4)["línea base"][5] == Fraction(55, 100)


def test_the_judge_against_the_majority(store):
    assert data.judge_matrix(store) == {
        (True, True): 19,
        (True, False): 1,
        (False, True): 5,
        (False, False): 15,
    }


def test_the_five_warranty_claims_read_the_other_way(store):
    matrix = data.audit_matrix(store)
    assert matrix[("no procede", "escalamiento")] == 5
    assert sum(matrix.values()) == 30


def test_the_ratings_of_e3(store):
    found = data.ratings(store)
    assert sorted(found) == ["X1", "X2", "X3"]
    assert sum(found[w][5] for w in found) == 49
    assert sum(found[w][4] for w in found) == 11


def test_the_cost_components_of_each_experiment(store):
    names = [c.name for c in data.costs(store, data.E4)]
    assert names == ["usuario simulado", "agente", "evaluador"]
    assert [c.recorded for c in data.costs(store, data.E1)] == [800, 800, 800]
