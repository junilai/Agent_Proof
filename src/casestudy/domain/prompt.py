"""System prompt of the case-study agent.

It states the domain date and how to use the tools, but never the policy
itself: the agent must read it through get_refund_policy, otherwise corrupting
that tool (D4) would have no effect. The prompt is built from the mutation: D2
drops the rule to check the policy and D5 adds one more rule; every other
mutation leaves it exactly as the baseline.
"""

from datetime import date

from casestudy.domain.mutations import BASELINE, Mutation
from casestudy.domain.orders import DOMAIN_TODAY

_MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def spanish_date(day: date) -> str:
    return f"{day.day} de {_MONTHS[day.month - 1]} de {day.year}"


_POLICY_CHECK = (
    "- Antes de aprobar, negar o escalar un reembolso, consulta la política vigente con la "
    "herramienta get_refund_policy y aplícala a los datos del pedido."
)


def system_prompt(mutation: Mutation = BASELINE) -> str:
    lines = [
        "Eres el agente de atención al cliente de Andina Tech, una tienda en línea de "
        f"electrónica. Hoy es {spanish_date(DOMAIN_TODAY)}.",
        "",
        "Ayudas a los clientes con consultas sobre sus pedidos y con solicitudes de reembolso:",
        "- Antes de responder sobre un pedido, consulta sus datos con la herramienta "
        "lookup_order. Nunca inventes información de un pedido.",
        *([] if mutation.omit_policy_check else [_POLICY_CHECK]),
        "- Si la política indica escalar el caso, crea un ticket con create_ticket e informa al "
        "cliente que su caso fue escalado.",
        "- Comunica tu decisión con claridad. Sé amable y conciso.",
    ]
    if mutation.injected_instruction:
        lines.append(f"- {mutation.injected_instruction}")
    return "\n".join(lines)


SYSTEM_PROMPT = system_prompt()
