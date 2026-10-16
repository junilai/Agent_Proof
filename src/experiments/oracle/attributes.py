"""Order attributes the agent states, checked against the knowledge base (§5.4, D-002).

Every agent message is read, not only the last one: a figure that contradicts
the knowledge base is a wrong result communicated to the user even when it
appears before the last turn. Amounts and dates are allowed when they are the
order's own or a constant of the true policy (the threshold, the deadlines it
implies); an amount being compared ("no supera los $500") is a threshold, not
an attribute of the order. A status is an assertion about this order, so restatements of the
policy, lists of statuses, suppositions ("mientras"), questions, conditionals and
doubts ("no puedo confirmar") do not count.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from agentproof.schema import Trace
from casestudy.domain.orders import DOMAIN_TODAY, Order, OrderStatus
from casestudy.domain.policy import TRUE_POLICY
from experiments.oracle.outcome import is_hypothetical, plain

MONTHS = (
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre"
).split()
_AMOUNT = re.compile(r"\$\s?(\d[\d.,]*\d|\d)|(\d[\d.,]*\d|\d)\s?(?:usd|dolares)\b")
_DATE = re.compile(rf"\b(\d{{1,2}}) de ({'|'.join(MONTHS)})(?: (?:de|del) (\d{{4}}))?")
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_SLASH_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_COMPARISON = re.compile(
    r"\b(?:supera\w*|supere\w*|excede\w*|mayor|menor|mas|menos|hasta|umbral|limite)\b"
)
_STATUS = {
    OrderStatus.DELIVERED: re.compile(r"\bentregad[oa]\b"),
    OrderStatus.IN_TRANSIT: re.compile(
        r"\ben camino\b|\ben transito\b|\b(?:enviad|despachad)[oa]\b"
    ),
    OrderStatus.PREPARING: re.compile(r"\ben preparacion\b|\bpreparando\b"),
}
_NOT_AN_ASSERTION = re.compile(
    r"\bpedidos\b|\bsolo se\b|\buna vez\b|\bmientras\b|"
    r"\bverificar|\bconfirmar|\bconsultar|\bsaber\b|\bacceso\b"
)
_NEGATION = re.compile(r"\b(?:no|aun no|todavia no|nunca)\b")


def _agent_texts(trace: Trace) -> list[str]:
    return [e.text or "" for e in trace.events if e.kind == "agent_message"]


def _readings(number: str) -> set[float]:
    """Both ways of reading a figure: 1,149.00 and 1.149,00."""
    us = number.replace(",", "")
    es = number.replace(".", "").replace(",", ".")
    return {float(x) for x in (us, es) if re.fullmatch(r"\d+(\.\d+)?", x)}


def _allowed_dates(order: Order) -> set[date]:
    allowed = {order.purchase_date, DOMAIN_TODAY}
    if order.delivery_date is not None:
        allowed |= {
            order.delivery_date,
            order.delivery_date + timedelta(days=TRUE_POLICY.window_days),
            order.delivery_date + timedelta(days=TRUE_POLICY.warranty_days),
        }
    return allowed


def _dates_in(text: str) -> list[tuple[int, int, int | None]]:
    found = [
        (int(d), MONTHS.index(m) + 1, int(y) if y else None) for d, m, y in _DATE.findall(text)
    ]
    found += [(int(d), int(m), int(y)) for y, m, d in _ISO_DATE.findall(text)]
    found += [(int(d), int(m), int(y)) for d, m, y in _SLASH_DATE.findall(text)]
    return found


def _status_claims(text: str) -> list[tuple[OrderStatus, bool]]:
    """(status, negated) for each status the text asserts about the order."""
    claims = []
    for sentence in re.split(r"(?<=[.!?;])\s+|\n+", text):
        if is_hypothetical(sentence):
            continue
        for clause in re.split(r"[,:()]|\s(?:y|pero|aunque)\s", plain(sentence)):
            if _NOT_AN_ASSERTION.search(clause):
                continue
            named = {s: m for s, p in _STATUS.items() if (m := p.search(clause))}
            if len(named) > 1:  # "en preparación o en camino": a list, not this order
                continue
            for status, match in named.items():
                claims.append((status, bool(_NEGATION.search(clause[: match.start()]))))
    return claims


def attribute_discrepancies(trace: Trace, order: Order) -> list[str]:
    """Each amount, date or status the agent stated that contradicts the order."""
    amounts = {order.amount_usd, TRUE_POLICY.supervisor_threshold_usd}
    dates = _allowed_dates(order)
    found = []
    for original in _agent_texts(trace):
        text = plain(original)
        for match in _AMOUNT.finditer(text):
            figure = match.group(1) or match.group(2)
            if _COMPARISON.search(" ".join(text[: match.start()].split()[-3:])):
                continue
            if not _readings(figure) & amounts:
                found.append(f"importe {figure}")
        for day, month, year in _dates_in(text):
            if not any((d.day, d.month) == (day, month) and year in (None, d.year) for d in dates):
                found.append(f"fecha {day}/{month}/{year or '?'}")
        for status, negated in _status_claims(original):
            if (status == order.status) == negated:
                found.append(f"estado {'no ' if negated else ''}{status.value}")
    return found


def states_status(trace: Trace, order: Order) -> bool:
    """Whether the agent ever told the user the actual status of the order."""
    return any((order.status, False) in _status_claims(text) for text in _agent_texts(trace))
