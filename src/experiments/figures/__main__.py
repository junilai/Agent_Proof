"""Every generated figure and table of the thesis, with one command and no API call.

python -m experiments.figures --data . --out thesis/generadas
"""

from __future__ import annotations

from pathlib import Path

import typer

from agentproof.store import Store
from experiments.figures import data, plots, tables

app = typer.Typer(help="Figuras y tablas generadas de la tesis.")
DATA = typer.Option(Path("."), "--data", help="Carpeta que contiene corpus/ y results/.")
OUT = typer.Option(Path("thesis/generadas"), "--out", help="Carpeta de salida.")


def generate(store: Store, out: Path) -> list[Path]:
    found = data.classifications(store)
    written = [
        plots.confusion_matrices(found, out / "matrices-confusion.pdf"),
        plots.joint_rates(store, out / "tasas-conjuntas.pdf"),
        plots.approval_heatmap(store, out / "aprobacion-escenarios.pdf"),
        plots.pass_k(store, out / "pass-k.pdf"),
        plots.human_validation(store, out / "validacion-humana.pdf"),
        plots.ratings(store, out / "calificaciones-e3.pdf"),
    ]
    texts = {
        "clasificacion.tex": tables.classification_table(found),
        "costo.tex": tables.cost_table(
            [(exp.name, exp.framework == "SDK", data.costs(store, exp)) for exp in data.EXPERIMENTS]
        ),
    }
    for name, text in texts.items():
        (out / name).write_text(text, encoding="utf-8")
        written.append(out / name)
    return written


@app.command()
def main(data_dir: Path = DATA, out: Path = OUT):
    """Escribe las figuras (PDF) y las tablas (LaTeX) que la tesis incluye."""
    for path in generate(Store(data_dir), out):
        typer.echo(f"escrito: {path}")


if __name__ == "__main__":
    app()
