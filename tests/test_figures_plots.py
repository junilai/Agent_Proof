from pathlib import Path

from agentproof.store import Store
from experiments.figures import data, plots

ROOT = Path(__file__).resolve().parents[1]


def test_every_figure_is_drawn_from_the_results(tmp_path):
    store = Store(ROOT)
    drawn = [
        plots.confusion_matrices(data.classifications(store), tmp_path / "a.pdf"),
        plots.joint_rates(store, tmp_path / "b.pdf"),
        plots.approval_heatmap(store, tmp_path / "c.pdf"),
        plots.pass_k(store, tmp_path / "d.pdf"),
        plots.human_validation(store, tmp_path / "e.pdf"),
        plots.ratings(store, tmp_path / "f.pdf"),
    ]
    for path in drawn:
        assert path.read_bytes().startswith(b"%PDF")
