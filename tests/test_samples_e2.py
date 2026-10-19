import json
from collections import Counter

from typer.testing import CliRunner

from agentproof.store import Store
from experiments.samples import app, e2_sample
from tests.factories import manifest, trace, verdict


def judged_run(store, variant, scenarios, judged=True):
    """A run of ``variant`` with one passed and one failed trace per scenario."""
    condition = "baseline-a" if variant == "baseline" else variant
    run_id = f"{condition}-20261018-000000"
    store.create_run(manifest(run_id=run_id, condition=condition, variant=variant))
    n = 0
    for s in range(scenarios):
        for passed in (True, False):
            n += 1
            trace_id = f"tr-{variant[-1]}{s:02d}{n:09d}"
            store.save_run_trace(
                trace(
                    "run",
                    trace_id=trace_id,
                    run_id=run_id,
                    condition=condition,
                    variant=variant,
                    scenario_id=f"sc-tr-{s:012d}",
                    repetition=n,
                )
            )
            if judged:
                store.save_verdict(
                    verdict(
                        [passed], trace_id=trace_id, run_id=run_id, scenario_id=f"sc-tr-{s:012d}"
                    )
                )
    return run_id


def caps_held(pairs, cap):
    for stratum in ("aprobado", "reprobado"):
        mine = [p for p in pairs if p.stratum == stratum]
        assert max(Counter(p.scenario_id for p in mine).values()) <= cap
        assert max(Counter(p.variant for p in mine).values()) <= cap


def test_balanced_strata_under_both_caps(tmp_path):
    store = Store(tmp_path)
    runs = [judged_run(store, v, scenarios=4) for v in ("d1", "d2", "d3", "d4")]
    sample = e2_sample(store, runs, size=4, cap=1, contingency=2)
    assert Counter(p.stratum for p in sample.pairs) == {"aprobado": 4, "reprobado": 4}
    assert sample.caps == {"aprobado": 1, "reprobado": 1} and sample.per_stratum == 4
    caps_held(sample.pairs, 1)


def test_too_few_versions_raise_the_cap_of_that_stratum(tmp_path):
    """With two versions a cap of one fills only two pairs: the contingency raises it."""
    store = Store(tmp_path)
    runs = [judged_run(store, v, scenarios=4) for v in ("d1", "d2")]
    sample = e2_sample(store, runs, size=4, cap=1, contingency=2)
    assert sample.caps == {"aprobado": 2, "reprobado": 2} and sample.per_stratum == 4
    caps_held(sample.pairs, 2)


def test_if_still_short_both_strata_shrink_to_the_smaller(tmp_path):
    store = Store(tmp_path)
    runs = [judged_run(store, "d1", scenarios=4)]
    sample = e2_sample(store, runs, size=4, cap=1, contingency=2)
    assert sample.per_stratum == 2
    assert Counter(p.stratum for p in sample.pairs) == {"aprobado": 2, "reprobado": 2}


def test_traces_without_a_verdict_are_not_pairs(tmp_path):
    store = Store(tmp_path)
    runs = [judged_run(store, "d1", scenarios=3), judged_run(store, "d2", 3, judged=False)]
    sample = e2_sample(store, runs, size=10, cap=5, contingency=5)
    assert {p.variant for p in sample.pairs} == {"d1"}


def test_the_draw_is_reproducible(tmp_path):
    store = Store(tmp_path)
    runs = [judged_run(store, v, scenarios=5) for v in ("d1", "d2", "d3")]
    assert e2_sample(store, runs, size=3, cap=1, contingency=2) == e2_sample(
        store, list(reversed(runs)), size=3, cap=1, contingency=2
    )


def test_the_command_writes_both_samples(tmp_path):
    store = Store(tmp_path)
    for v in ("baseline", "d1"):
        judged_run(store, v, scenarios=3)
    result = CliRunner().invoke(app, ["--data", str(tmp_path)])
    assert result.exit_code == 0, result.output
    audit = json.loads((tmp_path / "results" / "samples" / "auditoria.json").read_text())
    e2 = json.loads((tmp_path / "results" / "samples" / "e2.json").read_text())
    assert audit["seed"] == 20261021 and len(audit["traces"]) == 10
    assert audit["ticket_share"]["d1"] == [0, 6]
    assert e2["seed"] == 20261018 and e2["per_stratum"] == 6
