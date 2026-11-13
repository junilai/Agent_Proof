"""The generated tables of the thesis, as LaTeX tabulars; captions stay in the chapter."""

from __future__ import annotations

from fractions import Fraction

from agentproof.cost import ComponentCost
from experiments.figures.metrics import Classification

ORDER = (
    ("d1", "SDK"),
    ("d1", "LangGraph"),
    ("d4", "SDK"),
    ("d4", "LangGraph"),
    ("d6", "SDK"),
    ("d6", "LangGraph"),
    ("d2", "SDK"),
    ("d5", "SDK"),
)


CLASSIFICATION_WIDTHS = [0.3, 0.8, 0.25, 0.25, 0.25, 0.25, 0.62, 0.48, 0.35, 0.4, 0.75]


def _pct(value: Fraction | None) -> str:
    return "---" if value is None else f"{round(100 * value)}\\,\\%"


def _dec(value: Fraction | None) -> str:
    return "---" if value is None else f"{float(value):.2f}"


def _cols(widths: list[float]) -> str:
    return "|" + "|".join(f">{{\\raggedright\\arraybackslash}}p{{{w}in}}" for w in widths) + "|"


def classification_table(found: list[Classification]) -> str:
    by = {(c.operator, c.framework): c for c in found}
    head = [
        "Op.",
        "Framework",
        "VP",
        "FP",
        "FN",
        "VN",
        "Precisión",
        "Recall",
        "F1",
        "FPR",
        "FP no exp. / exp.",
    ]
    lines = [
        f"\\begin{{tabular}}{{{_cols(CLASSIFICATION_WIDTHS)}}}",
        "  \\hline",
        "  " + " & ".join(f"\\textbf{{{h}}}" for h in head) + " \\\\ \\hline",
    ]
    for key in ORDER:
        c = by[key]
        cells = [
            c.operator.upper(),
            c.framework,
            c.vp,
            c.fp,
            c.fn,
            c.vn,
            _pct(c.precision),
            _pct(c.recall),
            _dec(c.f1),
            _pct(c.fpr),
            f"{c.fp_unexposed} / {c.fp_exposed}",
        ]
        lines.append("  " + " & ".join(str(x) for x in cells) + " \\\\ \\hline")
    lines.append("\\end{tabular}")
    return "\n".join(lines) + "\n"


def _int(n: int) -> str:
    return f"{n:,}".replace(",", "\\,")


def cost_table(experiments: list[tuple[str, bool, list[ComponentCost]]]) -> str:
    """Rows per experiment; an agent with prompt caching has no price-table cost (D-007)."""
    head = [
        "Exp.",
        "Componente",
        "Registros",
        "Tokens de entrada",
        "Tokens de salida",
        "s medios",
        "USD (tabla)",
    ]
    lines = [
        f"\\begin{{tabular}}{{{_cols([0.4, 1.05, 0.65, 0.85, 0.8, 0.55, 0.6])}}}",
        "  \\hline",
        "  " + " & ".join(f"\\textbf{{{h}}}" for h in head) + " \\\\ \\hline",
    ]
    for name, cached, components in experiments:
        for c in components:
            usd = "---" if (c.name == "agente" and cached) or c.usd is None else f"{c.usd:.2f}"
            seconds = "---" if c.mean_seconds is None else f"{c.mean_seconds:.1f}"
            cells = [
                name,
                c.name,
                _int(c.recorded),
                _int(c.usage.input_tokens),
                _int(c.usage.output_tokens),
                seconds,
                usd,
            ]
            lines.append("  " + " & ".join(cells) + " \\\\ \\hline")
    lines.append("\\end{tabular}")
    return "\n".join(lines) + "\n"
