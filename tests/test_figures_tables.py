from pathlib import Path

import pytest

from agentproof.store import Store
from experiments.figures.__main__ import generate

ROOT = Path(__file__).resolve().parents[1]
PUBLISHED = ROOT / "thesis" / "generadas"


@pytest.fixture(scope="module")
def fresh(tmp_path_factory):
    out = tmp_path_factory.mktemp("generadas")
    return {path.name: path for path in generate(Store(ROOT), out)}


def test_every_generated_file_is_published(fresh):
    assert sorted(fresh) == sorted(p.name for p in PUBLISHED.iterdir())


def test_the_published_tables_are_the_generated_ones(fresh):
    """No table is edited by hand. The PDFs are not compared byte by byte: their bytes
    can depend on the platform's font rendering, not on the data."""
    for name, path in fresh.items():
        if name.endswith(".tex"):
            assert (PUBLISHED / name).read_text() == path.read_text(), name


def test_the_classification_table_reports_precision_and_f1(fresh):
    table = fresh["clasificacion.tex"].read_text()
    assert "D4 & SDK & 6 & 1 & 0 & 13 & 86\\,\\% & 100\\,\\% & 0.92 & 7\\,\\% & 0 / 1" in table
    assert "D6 & LangGraph & 0 & 5 & 0 & 15 & 0\\,\\% & --- & --- & 25\\,\\% & 0 / 5" in table


def test_the_agent_of_e1_has_no_price_table_cost(fresh):
    costs = fresh["costo.tex"].read_text()
    assert "E1 & agente & 800 &" in costs and "& 14.5 & --- \\\\" in costs
    assert "E4 & agente & 400 &" in costs and "& 9.65 \\\\" in costs
