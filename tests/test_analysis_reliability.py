from fractions import Fraction

from agentproof.store import Store
from experiments.analysis.reliability import (
    effect_size,
    failure_frequencies,
    joint_failure_rates,
    pass_hat_k,
)
from tests.factories import manifest, trace, verdict
from tests.test_analysis_detection import CANDIDATE, REFERENCE, populated, sc

RUN = "d2-20261016-150000"


def test_pass_hat_k_is_the_chance_that_k_repetitions_all_pass(tmp_path):
    """One scenario at 5/5 and one at 4/5: the second gives 4/5, 3/5, 2/5, 1/5 and 0."""
    store = Store(tmp_path)
    store.create_run(manifest(run_id=RUN, condition="d2", repetitions=5))
    for scenario_id, outcomes in (("sc-a", [True] * 5), ("sc-b", [True] * 4 + [False])):
        for repetition, passed in enumerate(outcomes, start=1):
            trace_id = f"tr-{scenario_id[-1]}{repetition:011d}"
            store.save_run_trace(
                trace("run", trace_id=trace_id, run_id=RUN, scenario_id=scenario_id)
            )
            store.save_verdict(
                verdict([passed], trace_id=trace_id, run_id=RUN, scenario_id=scenario_id)
            )
    second = [Fraction(4, 5), Fraction(3, 5), Fraction(2, 5), Fraction(1, 5), Fraction(0)]
    assert pass_hat_k(store, RUN) == {k: (1 + p) / 2 for k, p in enumerate(second, start=1)}


def test_the_joint_distribution_covers_every_scenario_with_its_raw_rates(tmp_path):
    rows = {
        r.scenario_id: r
        for r in joint_failure_rates(populated(tmp_path), REFERENCE, CANDIDATE, "d4")
    }
    assert list(rows) == [sc(n) for n in range(1, 7)]
    assert (rows[sc(2)].reference, rows[sc(2)].candidate) == (0, Fraction(2, 5))
    assert rows[sc(2)].manifested and rows[sc(2)].status == "ok"
    assert not rows[sc(3)].exposed and rows[sc(3)].status == "regresión"
    assert rows[sc(6)].status == "señal débil"


def test_failure_frequencies_of_the_exposed_candidate(tmp_path):
    rows = joint_failure_rates(populated(tmp_path), REFERENCE, CANDIDATE, "d4")
    exposed = [r for r in rows if r.exposed]
    assert failure_frequencies(exposed) == {Fraction(0): 2, Fraction(2, 5): 1, Fraction(1): 1}


def test_the_effect_size_over_the_suite_and_over_the_exposed_set(tmp_path):
    store = populated(tmp_path)
    suite = effect_size(store, REFERENCE, CANDIDATE)
    assert suite is not None and suite.drop == Fraction(17, 30)
    assert suite.per_scenario[sc(6)] == Fraction(2, 5)
    exposed = effect_size(store, REFERENCE, CANDIDATE, [sc(1), sc(2), sc(4), sc(6)])
    assert exposed is not None and (exposed.reference, exposed.drop) == (1, Fraction(3, 5))
    assert effect_size(store, REFERENCE, CANDIDATE, []) is None
