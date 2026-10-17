"""Section 9 of the pre-registration is the output of the command, never hand-written."""

from pathlib import Path

from agentproof.store import Store
from experiments.preregistration import VALIDATION, pilot, render, rows, validation

ROOT = Path(__file__).resolve().parent.parent
SECTION = "## 9. Conjuntos expuestos del corpus\n\n"


def test_section_9_is_what_the_command_prints():
    text = (ROOT / "docs" / "preregistro.md").read_text(encoding="utf-8")
    start = text.index(SECTION) + len(SECTION)
    end = text.index("\n\n## 10.")
    assert text[start:end] == render(Store(ROOT)), (
        "Regenere la sección 9 con: uv run python -m experiments.preregistration --data ."
    )


def test_the_exposed_sets_match_the_coverage_of_the_corpus():
    table = rows(Store(ROOT))
    counts = {op: sum(op in r.exposed for r in table) for op in ("d1", "d2", "d4", "d5", "d6")}
    assert len(table) == 20
    assert counts == {"d1": 17, "d2": 15, "d4": 17, "d5": 5, "d6": 11}


def test_the_draws_are_fixed_and_stay_inside_each_pool():
    table = rows(Store(ROOT))
    assert pilot(table) == pilot(table) and len(pilot(table)) == 5
    drawn = validation(table)
    assert list(drawn) == [condition for condition, _ in VALIDATION]
    for condition, chosen in drawn.items():
        assert len(set(chosen)) == len(chosen)
        assert condition == "baseline" or all(condition in r.exposed for r in chosen)
    assert len(drawn["d5"]) == 5 and all(
        len(drawn[c]) == 10 for c in ("baseline", "d1", "d2", "d4")
    )
