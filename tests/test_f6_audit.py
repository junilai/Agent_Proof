"""The oracle audit on E1 against the majority of three annotators (pre-registration §4)."""

from collections import Counter

import pytest

from experiments.f6.audit import audit, weighted
from experiments.f6.labels import load
from experiments.validation import decision_outcome
from tests.f6_fakes import keys, like_the_oracle, oracle_reading, store, write_all


def analysed(tmp_path, fill):
    return audit(store(), load(store(), write_all(tmp_path, fill), keys()).traces)


def total(table, group, key):
    return sum(t.table.get(group, {}).get(key, 0) for t in table.strata.values())


def test_annotators_who_read_like_the_oracle_find_no_error(tmp_path):
    result = analysed(tmp_path, like_the_oracle())
    assert result.audited == 36 and len(result.left_out) == 4
    assert {s: r.traces for s, r in result.strata.items()} == {"con ticket": 23, "sin ticket": 13}
    for group, bad in (("decisión", "al revés"), ("atributos", "FP"), ("atributos", "FN")):
        assert total(result, group, bad) == 0
    assert set(result.overall["decisión"]) <= {"exacta"}
    for op in ("d1", "d2", "d4", "d5", "d6"):
        assert "difiere" not in result.overall[f"predicado {op}"]
    assert result.without_majority == []


def test_every_count_is_split_by_stratum_and_the_overall_adds_them(tmp_path):
    result = analysed(tmp_path, like_the_oracle())
    for group, counts in result.overall.items():
        for key, n in counts.items():
            assert n == total(result, group, key)


def test_a_majority_that_contradicts_the_oracle_is_counted_against_it(tmp_path):
    flipped = {"contradicts_base": True, "decision": "ninguna"}
    result = analysed(tmp_path, like_the_oracle(X1=flipped, X2=flipped))
    with_order = [t for t in result.traces if t.majority["contradicts_base"] is not None]
    said = sum(oracle_reading(t.key)["contradicts_base"] for t in with_order)
    expected = {"FN": len(with_order) - said, "VP": said}
    assert result.overall["atributos"] == {k: n for k, n in expected.items() if n}
    decided = [t for t in result.traces if t.majority["decision"] is not None]
    expected = Counter(
        decision_outcome("ninguna", oracle_reading(t.key)["decision"]) for t in decided
    )
    assert result.overall["decisión"] == dict(expected)


def test_a_decision_without_majority_is_reported_apart(tmp_path):
    split = {"X1": "procede", "X2": "no procede", "X3": "escalamiento"}
    result = analysed(tmp_path, like_the_oracle(decisions=split))
    # only the outcomes no single decision could change survive: the oracle read none
    assert set(result.overall["decisión"]) <= {"a la cola", "omitida"}
    apart = {w.key for w in result.without_majority}
    assert apart and all(w.field == "decision" for w in result.without_majority)
    assert apart <= {t.key for t in result.traces if t.majority["decision"] is None}
    assert all(
        w.votes == ["procede", "no procede", "escalamiento"] for w in result.without_majority
    )


def test_annotator_agreement_is_measured_per_field(tmp_path):
    result = analysed(tmp_path, like_the_oracle(X2={"contradicts_base": True}))
    assert result.annotators["decision"].unanimous == result.annotators["decision"].items
    attributes = result.annotators["contradicts_base"]
    assert attributes.cohen["X1-X3"] in (1, None) and attributes.cohen["X1-X2"] < 1


def test_the_weight_of_each_stratum_is_its_share_in_e1(tmp_path):
    result = analysed(tmp_path, like_the_oracle())
    assert result.ticket_weight == pytest.approx(402 / 800)


def test_weighted_proportions_mix_the_strata_by_their_share():
    ticket = {"decisión": {"exacta": 3, "al revés": 1}}
    none = {"decisión": {"exacta": 2}}
    mixed = weighted(ticket, none, 0.5)
    assert mixed["decisión"] == {"al revés": pytest.approx(0.125), "exacta": pytest.approx(0.875)}


def test_a_group_missing_in_one_stratum_has_no_weighted_proportion():
    assert weighted({"estado": {"coincide": 2}}, {}, 0.5)["estado"] == {"coincide": None}


def test_each_predicate_is_weighted_within_its_own_operator(tmp_path):
    result = analysed(tmp_path, like_the_oracle())
    assert "predicados" not in result.overall
    in_both = [
        op
        for op in ("d1", "d2", "d4", "d5", "d6")
        if all(s.table[f"predicado {op}"] for s in result.strata.values())
    ]
    assert in_both
    for op in in_both:
        assert sum(result.weighted[f"predicado {op}"].values()) == pytest.approx(1), op
