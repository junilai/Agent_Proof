from pathlib import Path

from agentproof.store import Store
from experiments.figures.__main__ import generate

ROOT = Path(__file__).resolve().parents[1]


def test_the_committed_figures_and_tables_are_the_generated_ones(tmp_path):
    """Nothing in thesis/generadas is edited by hand: regenerating changes no byte."""
    for path in generate(Store(ROOT), tmp_path):
        committed = ROOT / "thesis" / "generadas" / path.name
        assert committed.read_bytes() == path.read_bytes(), path.name


def test_the_classification_table_reports_precision_and_f1(tmp_path):
    generate(Store(ROOT), tmp_path)
    table = (tmp_path / "clasificacion.tex").read_text()
    assert "D4 & SDK & 6 & 1 & 0 & 13 & 86\\,\\% & 100\\,\\% & 0.92 & 7\\,\\% & 0 / 1" in table
    assert "D6 & LangGraph & 0 & 5 & 0 & 15 & 0\\,\\% & --- & --- & 25\\,\\% & 0 / 5" in table


def test_the_agent_of_e1_has_no_price_table_cost(tmp_path):
    generate(Store(ROOT), tmp_path)
    costs = (tmp_path / "costo.tex").read_text()
    assert "E1 & agente & 800 &" in costs and "& 14.5 & --- \\\\" in costs
    assert "E4 & agente & 400 &" in costs and "& 9.65 \\\\" in costs
