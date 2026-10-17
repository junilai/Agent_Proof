"""Outcome the agent communicated, extracted by rules (§5.4, D-002).

The vocabulary is closed: the refund proceeds, it does not proceed, or the case
is escalated. A sentence counts only when it states a fact: questions and
conditional sentences are skipped (also what the customer should do later: "una
vez recibido", "luego", "deberías"), and a term preceded by a negation or by a
purpose ("para escalar", "puedo escalar") is not an escalation. An offer bound
to a pending condition ("con esa confirmación, escalo tu caso") is conditional
too. An escalation prevails over the other two, because escalating usually also
says that the direct refund does not proceed.

D-009: the vocabulary is about the refund. A ticket counts only when the message
creates or escalates it; a later mention of an existing ticket states nothing
new. An escalation for another matter (logistics, activation, a delay, the time a
refund takes, technical support) is not an escalation of the refund, unless the
message ties it to the refund: a warranty claim, the amount threshold, an
exception someone will consider, or someone who will review or decide the refund.
Recasting the request as another matter ("no se trata de un reembolso…, sino…")
while escalating leaves the refund open: it is unresolved. Approval and denial in
the same message, with no escalation, is not guessed either. Unresolved messages
go to manual annotation.
"""

from __future__ import annotations

import re
import unicodedata
from enum import Enum

from agentproof.schema import Trace
from casestudy.domain.policy import Decision


class Unresolved(Enum):
    UNRESOLVED = "sin resolver"


UNRESOLVED = Unresolved.UNRESOLVED
type Extracted = Decision | Unresolved | None

_SENTENCES = re.compile(r"(?<=[.!?;])\s+|\n+")
_CLAUSES = re.compile(r"[,:()]|\s(?:y|pero|aunque|sin embargo|asi que|por lo que|porque|ya que)\s")
_CONDITIONAL = re.compile(
    r"(?<!\w)si(?!\w)|¿|\bcon es[ao]s? (?:confirmación|datos|información)\b|\ben cuanto\b|"
    r"\buna vez\b|\bluego\b|\bdeber[ií]as?\b|\bde lo contrario\b"
)
_WINDOW = 6

_NOUN = re.compile(r"reembols|devoluci|devolver\w* (?:el|tu|su) dinero")
_ESCALATION = re.compile(
    r"\bescal(?:o|e|are|ados?|adas?|ar|arse|arlo|arla|arlos|ando|amos|aremos)\b|"
    r"\breclamo de garantia\b"
)
_TICKET = re.compile(r"\btck-|\b(?:el|tu|un|su|del) ticket\b")
_TICKET_CREATED = re.compile(r"\b(?:cree|creado|crear|genere|generado|registre|abri)\b")
_APPROVAL = re.compile(
    r"\b(?:procede|aprobad[oa]|aprobe|apruebo|autorizad[oa]|procesad[oa]|procese)\b"
)
_DENIAL = re.compile(
    r"\b(?:aplica|corresponde|califica|cumple|es posible|son reembolsables|es reembolsable|"
    r"se reembolsan?|(?:puedo|podemos|puede|podre|podria) (?:procesar|aprobar|realizar|hacer|"
    r"ofrecer|otorgar|reembolsar|devolver\w*|gestionar|emitir))\b"
)
_NEGATION = {"no", "ni", "sin", "tampoco", "nunca"}
_HYPOTHETICAL = {"para", "puedo", "podemos", "podria", "podre", "necesitaria", "quieres", "desea"}
_OUT_OF_SCOPE = re.compile(r"parcial|credito")
_OTHER_MATTER = re.compile(
    r"soporte tecnico|equipo tecnico|equipo de soporte|logistic|devolucion fisica|"
    r"proceso (?:exacto )?de devolucion|activacion|atraso|demora|retraso|\benvio\b|"
    r"acreditacion|tiempo de procesamiento"
)
_EXCEPTION = re.compile(r"\bexcepcion\b")
_REVIEWS_REFUND = re.compile(
    r"\b(?:evalu|revis|decid|decision|aprob|autoriz)\w*\b[^.?!\n]{0,40}\breembols"
)
_THRESHOLD = (
    r"(?:(?:us)?\$\s?|usd\s?)500(?:[.,]00)?\b|\b500(?:[.,]00)? (?:usd|dolares)\b|\bumbral\b"
)
_ABOVE = re.compile(
    rf"\b(?:supera\w*|excede\w*|mayor (?:a|de)|superior a|mas de) (?:los |el |a )?(?:{_THRESHOLD})"
)
_RECAST = re.compile(r"\bno (?:se trata de|corresponde a) un (?:caso de )?reembols\w*[^.]*\bsino\b")


def plain(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.replace("*", "").lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _preceding_words(clause: str, start: int) -> set[str]:
    return set(re.findall(r"\w+", clause[:start])[-_WINDOW:])


def _clause_signals(clause: str, has_noun: bool) -> set[Decision]:
    signals: set[Decision] = set()
    if _OUT_OF_SCOPE.search(clause):
        return signals
    escalations = list(_ESCALATION.finditer(clause))
    if _TICKET_CREATED.search(clause):
        escalations += _TICKET.finditer(clause)
    for match in escalations:
        if not _preceding_words(clause, match.start()) & (_NEGATION | _HYPOTHETICAL):
            signals.add(Decision.ESCALATED)
    if not has_noun:
        return signals
    for match in _APPROVAL.finditer(clause):
        negated = _preceding_words(clause, match.start()) & _NEGATION
        signals.add(Decision.DENIED if negated else Decision.APPROVED)
    for match in _DENIAL.finditer(clause):
        if _preceding_words(clause, match.start()) & _NEGATION:
            signals.add(Decision.DENIED)
    return signals


def _affirmed(pattern: re.Pattern[str], text: str) -> bool:
    """Some match of the pattern that the three words before it do not negate."""
    negations = _NEGATION | {"ningun", "ninguna"}
    return any(
        not set(re.findall(r"\w+", text[: m.start()])[-3:]) & negations
        for m in pattern.finditer(text)
    )


def _names_refund_escalation(text: str) -> bool:
    """A warranty claim, an amount above the threshold, or someone who will weigh the refund."""
    if "reclamo de garantia" in text:
        return True
    return any(_affirmed(p, text) for p in (_ABOVE, _EXCEPTION, _REVIEWS_REFUND))


def is_hypothetical(sentence: str) -> bool:
    """Questions and conditional sentences state no fact; "sí" keeps its accent here."""
    return bool(_CONDITIONAL.search(sentence.lower()))


def decision_in(text: str) -> Extracted:
    """The decision a single agent message states, if it states one."""
    signals: set[Decision] = set()
    text = text.replace("*", "")
    whole = plain(text)
    for sentence in _SENTENCES.split(text):
        if is_hypothetical(sentence):
            continue
        text_plain = plain(sentence)
        has_noun = bool(_NOUN.search(text_plain))
        for clause in _CLAUSES.split(text_plain):
            signals |= _clause_signals(clause, has_noun)
    if Decision.ESCALATED in signals and _RECAST.search(whole):
        return UNRESOLVED
    if _OTHER_MATTER.search(whole) and not _names_refund_escalation(whole):
        signals.discard(Decision.ESCALATED)
    if Decision.ESCALATED in signals:
        return Decision.ESCALATED
    if len(signals) > 1:
        return UNRESOLVED
    return signals.pop() if signals else None


def communicated_decision(trace: Trace) -> Extracted:
    """D-002: the decision of the most recent agent message that states one."""
    for event in reversed(trace.events):
        if event.kind == "agent_message":
            found = decision_in(event.text or "")
            if found is not None:
                return found
    return None
