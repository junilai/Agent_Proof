"""The figures of the thesis, as vector PDF for print.

Colour follows the data's job: one blue ramp for magnitudes (heatmaps), and the
validated categorical slots, always in the same order and always with a second
encoding (marker shape, direct label or legend), for identities.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from fractions import Fraction
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from agentproof.store import Store  # noqa: E402
from experiments.figures import data  # noqa: E402
from experiments.figures.metrics import Classification  # noqa: E402

INK, SECONDARY, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100")
"""Categorical slots 1-4, in fixed order."""
RAMP = LinearSegmentedColormap.from_list(
    "azul",
    ["#f4f8fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
)
FAMILY_A = ("d1", "d4", "d6")
WIDTH = 6.3
"""Inches: the text width of the thesis."""

plt.rcParams.update(
    {
        "font.size": 8,
        "axes.titlesize": 8.5,
        "axes.labelsize": 8,
        "axes.edgecolor": AXIS,
        "axes.labelcolor": SECONDARY,
        "axes.titlecolor": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelcolor": SECONDARY,
        "ytick.labelcolor": SECONDARY,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "pdf.fonttype": 42,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.03,
    }
)


def _save(fig: Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)
    return path


def _cells(ax, values: Sequence[Sequence[float]], vmax: float, fmt=str) -> None:
    """A heatmap with the value printed in every cell, in ink that reads on its fill."""
    ax.imshow(values, cmap=RAMP, vmin=0, vmax=vmax, aspect="auto")
    for i, row in enumerate(values):
        for j, value in enumerate(row):
            light = value > 0.55 * vmax
            ax.text(j, i, fmt(value), ha="center", va="center", color="white" if light else INK)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)


def confusion_matrices(found: list[Classification], path: Path) -> Path:
    by = {(c.operator, c.framework): c for c in found}
    fig, axes = plt.subplots(2, 3, figsize=(WIDTH, 3.9))
    for i, framework in enumerate(("SDK", "LangGraph")):
        for j, op in enumerate(FAMILY_A):
            c, ax = by[(op, framework)], axes[i][j]
            _cells(ax, [[c.vp, c.fn], [c.fp, c.vn]], vmax=20)
            ax.set_xticks([0, 1], ["sí", "no"])
            ax.set_yticks([0, 1], ["sí", "no"])
            ax.set_title(f"{op.upper()} · {framework}")
            if i == 1:
                ax.set_xlabel("Regresión declarada")
            if j == 0:
                ax.set_ylabel("Manifestado (oráculo)")
    fig.tight_layout(h_pad=1.6, w_pad=1.2)
    return _save(fig, path)


STATUS = {
    "regresión": (SERIES[1], "^"),
    "señal débil": (SERIES[3], "s"),
    "ok": (SERIES[0], "o"),
}


def joint_rates(store: Store, path: Path) -> Path:
    fig, axes = plt.subplots(2, 3, figsize=(WIDTH, 4.5), sharex=True, sharey=True)
    jitter = random.Random(20261112)
    for i, exp in enumerate(data.EXPERIMENTS):
        for j, op in enumerate(FAMILY_A):
            ax = axes[i][j]
            ax.fill_between([-0.1, 0.6], [0.3, 1.0], [1.1, 1.1], color="#f0efec", lw=0)
            ax.plot([-0.1, 0.6], [0.3, 1.0], color=MUTED, lw=0.8, ls="--")
            for row in data.joint_rates(store, exp, op):
                if row.reference is None or row.candidate is None:
                    continue
                color, marker = STATUS.get(row.status or "", (MUTED, "x"))
                ax.scatter(
                    float(row.reference) + jitter.uniform(-0.035, 0.035),
                    float(row.candidate) + jitter.uniform(-0.035, 0.035),
                    s=26,
                    marker=marker,
                    facecolor=color if row.manifested else "white",
                    edgecolor=color,
                    linewidth=1.1,
                    zorder=3,
                )
            ax.set_xlim(-0.1, 1.1)
            ax.set_ylim(-0.1, 1.1)
            ax.set_xticks([0, 0.5, 1])
            ax.set_yticks([0, 0.5, 1])
            ax.grid(color=GRID, lw=0.5)
            ax.set_axisbelow(True)
            ax.set_title(f"{op.upper()} · {exp.framework}")
            if i == 1:
                ax.set_xlabel("Fallo en la línea base")
            if j == 0:
                ax.set_ylabel("Fallo en la candidata")
    handles = [
        plt.Line2D([], [], ls="", marker=m, color=c, markerfacecolor=c, label=s)
        for s, (c, m) in STATUS.items()
    ] + [
        plt.Line2D(
            [],
            [],
            ls="",
            marker="o",
            color=MUTED,
            markerfacecolor="white",
            label="sin relleno: no manifestado",
        ),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    return _save(fig, path)


def approval_heatmap(store: Store, path: Path) -> Path:
    names = data.cards(store)
    panels = [(exp, data.approval_by_scenario(store, exp)) for exp in data.EXPERIMENTS]
    scenarios = sorted(panels[0][1]["línea base"], key=lambda s: names[s])
    fig, axes = plt.subplots(
        1, 2, figsize=(WIDTH, 5.2), gridspec_kw={"width_ratios": [8, 4]}, sharey=True
    )
    for ax, (exp, table) in zip(axes, panels, strict=True):
        columns = list(table)
        values = [[float(table[c].get(s, Fraction(0))) * 5 for c in columns] for s in scenarios]
        _cells(ax, values, vmax=5, fmt=lambda v: str(round(v)))
        ax.set_xticks(range(len(columns)), columns, rotation=45, ha="right")
        ax.set_yticks(range(len(scenarios)), [names[s] for s in scenarios])
        ax.set_title(f"{exp.name} · {exp.framework}")
    fig.tight_layout(w_pad=0.6)
    return _save(fig, path)


def pass_k(store: Store, path: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.6), sharey=True)
    for ax, exp in zip(axes, data.EXPERIMENTS, strict=True):
        curves = data.pass_k(store, exp)
        ends = []
        for color, (label, curve) in zip(SERIES, curves.items(), strict=True):
            ks = sorted(curve)
            ys = [100 * float(curve[k]) for k in ks]
            ax.plot(ks, ys, color=color, lw=2, marker="o", ms=4)
            ends.append([ys[-1], label, ks[-1]])
        ends.sort()
        for n in range(1, len(ends)):  # direct labels never overlap
            ends[n][0] = max(ends[n][0], ends[n - 1][0] + 4.5)
        for y, label, k in ends:
            ax.annotate(
                label,
                (k, y),
                xytext=(8, 0),
                textcoords="offset points",
                va="center",
                color=SECONDARY,
            )
        ax.set_xticks(range(1, 6))
        ax.set_xlim(0.8, 6.2)
        ax.set_ylim(0, 80)
        ax.grid(axis="y", color=GRID, lw=0.5)
        ax.set_xlabel("k (repeticiones que deben aprobar)")
        ax.set_title(f"{exp.name} · {exp.framework}")
    axes[0].set_ylabel("pass$^k$ (%)")
    fig.tight_layout()
    return _save(fig, path)


DECISIONS = ("procede", "no procede", "escalamiento", "sin resolver", "ninguna")


def human_validation(store: Store, path: Path) -> Path:
    fig, (left, right) = plt.subplots(
        1, 2, figsize=(WIDTH, 2.7), gridspec_kw={"width_ratios": [2.2, 4]}
    )
    judge = data.judge_matrix(store)
    _cells(left, [[judge.get((p, m), 0) for m in (True, False)] for p in (True, False)], vmax=20)
    left.set_xticks([0, 1], ["aprueba", "reprueba"])
    left.set_yticks([0, 1], ["aprueba", "reprueba"])
    left.set_xlabel("Mayoría de los anotadores")
    left.set_ylabel("Evaluador")
    left.set_title("(a) E2: aprobación")

    audit = data.audit_matrix(store)
    rows = [r for r in (*DECISIONS, "sin mayoría") if any(k[0] == r for k in audit)]
    cols = [c for c in DECISIONS if any(k[1] == c for k in audit)]
    _cells(right, [[audit.get((r, c), 0) for c in cols] for r in rows], vmax=12)
    right.set_xticks(range(len(cols)), cols, rotation=20, ha="right")
    right.set_yticks(range(len(rows)), rows)
    right.set_xlabel("Oráculo")
    right.set_ylabel("Mayoría")
    right.set_title("(b) Auditoría: decisión")
    fig.tight_layout(w_pad=2)
    return _save(fig, path)


def ratings(store: Store, path: Path) -> Path:
    found = data.ratings(store)
    fig, ax = plt.subplots(figsize=(WIDTH * 0.62, 2.2))
    width = 0.26
    for n, (who, color) in enumerate(zip(sorted(found), SERIES, strict=False)):
        xs = [score + (n - 1) * width for score in range(1, 6)]
        ys = [found[who].get(score, 0) for score in range(1, 6)]
        ax.bar(xs, ys, width=width - 0.03, color=color, label=who)
    ax.set_xticks(range(1, 6))
    ax.set_xlabel("Calificación de fidelidad")
    ax.set_ylabel("Escenarios")
    ax.set_ylim(0, 20)
    ax.grid(axis="y", color=GRID, lw=0.5)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left")
    fig.tight_layout()
    return _save(fig, path)
