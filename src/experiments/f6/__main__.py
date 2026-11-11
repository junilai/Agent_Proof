"""Analysis of the human annotation of F6 (pre-registration §4 and §6, D-016).

    python -m experiments.f6 --data . --labels <carpeta> --keys <carpeta>

Reads the label files the annotators returned and the keys written apart by
``experiments.annotators``, prints a Spanish report and writes the results as
JSON. A session without files is skipped; an incomplete one stops everything.
The oracle measured is the one installed with this code.
"""

from __future__ import annotations

from pathlib import Path

import typer

from agentproof.store import Store
from experiments.f6.labels import load
from experiments.f6.report import render, results

app = typer.Typer(help="Análisis de la anotación humana de F6.")
DATA = typer.Option(Path("."), "--data", help="Carpeta que contiene corpus/ y results/.")
LABELS = typer.Option(..., "--labels", help="Carpeta con etiquetas-<anotador>-sesion-<n>.json.")
KEYS = typer.Option(..., "--keys", help="Carpeta con la clave de cada sesión.")
OUT = typer.Option(None, "--out", help="JSON de resultados; por omisión results/f6/analisis.json.")


@app.command()
def main(labels: Path = LABELS, keys: Path = KEYS, data: Path = DATA, out: Path | None = OUT):
    """Imprime el reporte de E2, E3, la auditoría y los desacuerdos, y escribe el JSON."""
    store = Store(data)
    try:
        found = results(store, load(store, labels, keys))
    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error
    typer.echo(render(found))
    path = out or store.root / "results" / "f6" / "analisis.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(found.model_dump_json(indent=2) + "\n", encoding="utf-8")
    typer.echo(f"\nResultados: {path}")


if __name__ == "__main__":
    app()
