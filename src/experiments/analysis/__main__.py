"""Detection metrics of one framework's runs.

    python -m experiments.analysis --data . --reference <run> --control <run> \\
        --candidate <run> [--candidate <run> ...]

The operator of each candidate is read from its manifest. Nothing is computed
while the oracle still has cases waiting for manual annotation.
"""

from __future__ import annotations

from pathlib import Path

import typer

from agentproof.store import Store
from experiments.analysis.summary import render_analysis, write_joint_failure_rates
from experiments.oracle.annotation import pending

app = typer.Typer(help="Métricas de detección de las corridas de un framework.")
DATA = typer.Option(Path("."), "--data", help="Carpeta que contiene corpus/ y results/.")
REFERENCE = typer.Option(..., "--reference", help="Corrida de baseline-a.")
CONTROL = typer.Option(..., "--control", help="Corrida de baseline-b.")
CANDIDATES = typer.Option(..., "--candidate", help="Corrida de una mutación; se repite.")


@app.command()
def main(
    reference: str = REFERENCE,
    control: str = CONTROL,
    candidate: list[str] = CANDIDATES,
    data: Path = DATA,
):
    """Imprime las métricas y escribe results/analysis/joint_failure_rates.csv."""
    store = Store(data)
    waiting = pending(store, [reference, *candidate])
    if waiting:
        typer.echo(
            f"{len(waiting)} caso(s) esperan anotación manual: "
            "python -m experiments.oracle.annotation --data .",
            err=True,
        )
        raise typer.Exit(1)
    typer.echo(render_analysis(store, reference, control, candidate))
    path = store.root / "results" / "analysis" / "joint_failure_rates.csv"
    write_joint_failure_rates(store, reference, candidate, path)
    typer.echo(f"\nDatos para las figuras: {path}")


if __name__ == "__main__":
    app()
