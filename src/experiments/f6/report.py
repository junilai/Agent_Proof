"""The results of F6 together, as a Spanish report and as JSON."""

from __future__ import annotations

import hashlib
from importlib import resources

from pydantic import BaseModel

from agentproof.store import Store
from experiments.f6.attribution import Attribution, attribution
from experiments.f6.audit import Audit, audit
from experiments.f6.e2 import E2, Agreement, e2
from experiments.f6.e3 import E3, e3
from experiments.f6.labels import Labels


def oracle_fingerprint() -> str:
    """The fingerprint of the oracle's source, as §10 of the pre-registration computes it."""
    folder = resources.files("experiments") / "oracle"
    source = "".join(
        p.read_text()
        for p in sorted(folder.iterdir(), key=lambda p: p.name)
        if p.name.endswith(".py")
    )
    return hashlib.sha256(source.encode()).hexdigest()[:16]


class Note(BaseModel):
    annotator: str
    session: int
    key: str
    note: str


class Results(BaseModel):
    annotators: list[str]
    oracle: str
    """Fingerprint of the installed oracle's rules, to tell the oracle each run measured."""
    e2: E2 | None
    audit: Audit | None
    disagreements: Attribution | None
    e3: E3 | None
    notes: list[Note]


def results(store: Store, labels: Labels) -> Results:
    traces, scenarios = labels.traces, labels.scenarios
    notes = [
        Note(annotator=a, session=1, key=k, note=label.note)
        for a, found in traces.items()
        for k, label in found.items()
        if label.note
    ] + [
        Note(annotator=a, session=2, key=k, note=rating.note)
        for a, found in scenarios.items()
        for k, rating in found.items()
        if rating.note
    ]
    return Results(
        annotators=labels.annotators,
        oracle=oracle_fingerprint(),
        e2=e2(store, traces) if traces else None,
        audit=audit(store, traces) if traces else None,
        disagreements=attribution(store, traces) if traces else None,
        e3=e3(scenarios) if scenarios else None,
        notes=notes,
    )


def pct(part: float, whole: float) -> str:
    return "—" if not whole else f"{part:g}/{whole:g} ({100 * part / whole:.1f} %)"


def num(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def _agreement(name: str, found: Agreement) -> str:
    return f"{name}: {pct(found.agreed, found.total)} · κ de Cohen {num(found.kappa)}"


def _pairs(kappas: dict[str, float | None]) -> str:
    return ", ".join(f"{pair} {num(k)}" for pair, k in kappas.items())


def render_e2(found: E2) -> list[str]:
    lines = [
        "## E2: concordancia del evaluador",
        f"Pares: {found.pairs}. Aprobaciones por anotador: "
        + ", ".join(f"{a} {n}" for a, n in found.approvals.items())
        + f". Aprobadas por mayoría: {found.majority_approved}.",
        f"κ de Fleiss, aprobación: {num(found.fleiss_approval)}; "
        f"por criterio: {num(found.fleiss_criteria)}",
        f"κ de Cohen por pares, aprobación: {_pairs(found.cohen_approval)}",
        f"κ de Cohen por pares, por criterio: {_pairs(found.cohen_criteria)}",
        "Evaluador contra la mayoría:",
        "- " + _agreement("por traza", found.judge_approval),
        "- " + _agreement("por criterio", found.judge_criteria),
    ]
    for name, stratum in found.strata.items():
        lines.append(
            f"- estrato {name}: coincide en {pct(stratum.judge_agreed, stratum.pairs)}; "
            f"la mayoría aprueba {stratum.majority_approved}"
        )
    lines += [
        f"Trazas en que todos los criterios de mayoría dan otra aprobación que la mayoría: "
        f"{found.approval_of_majority_criteria_differs}",
        f"Proporción natural de aprobaciones en E1 (aparte): "
        f"{pct(found.natural.passed, found.natural.judged)}",
    ]
    return lines


def _table(table: dict[str, dict[str, int]]) -> list[str]:
    return [
        f"  {group}: " + (", ".join(f"{k} {n}" for k, n in counts.items()) or "—")
        for group, counts in table.items()
    ]


def render_audit(found: Audit, oracle: str) -> list[str]:
    lines = [
        "## Auditoría del oráculo",
        f"Oráculo medido: reglas con huella {oracle} (el instalado con este código).",
        f"Trazas auditadas: {found.audited}; fuera (tarjetas sin decisión ni pedido): "
        f"{len(found.left_out)}",
        "Total:",
        *_table(found.overall),
    ]
    for name, stratum in found.strata.items():
        lines += [f"Estrato {name} ({stratum.traces} trazas):", *_table(stratum.table)]
    lines.append(
        f"Ponderado por la proporción de trazas con ticket en E1 ({found.ticket_weight:.3f}):"
    )
    for group, shares in found.weighted.items():
        shown = ", ".join(
            f"{k} {'—' if v is None else f'{100 * v:.1f} %'}" for k, v in shares.items()
        )
        lines.append(f"  {group}: {shown or '—'}")
    lines.append(f"Decisiones sin mayoría (aparte): {len(found.without_majority)}")
    lines += [f"- {w.key}: {', '.join(w.votes)}" for w in found.without_majority]
    lines.append("Concordancia entre los anotadores:")
    for name, field in found.annotators.items():
        lines.append(
            f"- {name}: {field.items} trazas, unánimes {field.unanimous}, "
            f"κ de Fleiss {num(field.fleiss)}, κ de Cohen {_pairs(field.cohen)}"
        )
    return lines


def _causes(counts: dict[str, int]) -> str:
    return ", ".join(f"{cause} {n}" for cause, n in counts.items()) or "—"


def render_disagreements(found: Attribution) -> list[str]:
    attributed = sum(not c.apart for c in found.cells)
    lines = [
        "## Desacuerdos (D-016)",
        f"Celdas: {len(found.cells)}; atribuidas: {attributed}. Conteos ponderados por las "
        "repeticiones discordantes de cada celda.",
    ]
    for cause, count in found.by_cause.items():
        lines.append(f"- {cause}: {count.cells} celdas, {count.repetitions} repeticiones")
    lines.append(
        f"- reglas del oráculo y evaluador a la vez: {found.both.cells} celdas, "
        f"{found.both.repetitions} repeticiones"
    )
    for title, split in (
        ("Por operador", found.by_operator),
        ("Por corrida", found.by_run),
        ("Por dirección", found.by_direction),
    ):
        lines.append(f"{title}:")
        lines += [f"- {name}: {_causes(counts)}" for name, counts in split.items()]
    lines.append("Aparte:" + ("" if found.apart else " ninguna"))
    lines += [
        f"- {why}: {count.cells} celdas, {count.repetitions} repeticiones"
        for why, count in found.apart.items()
    ]
    lines.append("Celdas:")
    lines += [
        f"- {c.operator} {c.scenario_id} {c.run} ({c.direction}, {c.discordant}) {c.trace_id}: "
        + (", ".join(c.causes) if c.causes else f"aparte, {c.apart}")
        for c in found.cells
    ]
    return lines


def render_e3(found: E3) -> list[str]:
    lines = [
        "## E3: fidelidad de la inducción",
        f"Escenarios con mediana ≥ 4: {pct(found.median_at_least_4, found.scenarios)}",
        f"α de Krippendorff ordinal: {num(found.alpha_ordinal)}",
        "Comparaciones por pares:",
    ]
    for pair, p in found.pairs.items():
        lines.append(
            f"- {pair}: iguales {p.exact}/{p.total}, a un punto {p.within_one}/{p.total}, "
            f"diferencia media {p.mean_difference:+.2f}, α ordinal {num(p.alpha_ordinal)}"
        )
    lines.append("Distribución (1 a 5):")
    lines += [
        f"- {who}: " + " ".join(str(counts[p]) for p in sorted(counts))
        for who, counts in found.distribution.items()
    ]
    lines.append(
        f"Requerirían corrección (mayoría): {pct(found.needs_correction, found.scenarios)}"
    )
    lines += [
        f"- {s.scenario_id}: {' '.join(str(r) for r in s.ratings.values())} → mediana {s.median:g}"
        + (", corrección" if s.needs_correction else "")
        for s in found.per_scenario
    ]
    return lines


def render(found: Results) -> str:
    lines = [f"# F6: anotación humana ({', '.join(found.annotators)})", ""]
    if found.e2 and found.audit and found.disagreements:
        for part in (
            render_e2(found.e2),
            render_audit(found.audit, found.oracle),
            render_disagreements(found.disagreements),
        ):
            lines += [*part, ""]
    else:
        lines += ["Sesión 1: sin etiquetas todavía.", ""]
    lines += [*render_e3(found.e3), ""] if found.e3 else ["Sesión 2: sin etiquetas todavía.", ""]
    lines.append(f"Notas de los anotadores: {len(found.notes)}")
    lines += [f"- {n.annotator}, sesión {n.session}, {n.key}: {n.note}" for n in found.notes]
    return "\n".join(lines)
