"""Outcome the agent communicated, extracted by rules (§5.4, D-002).

The vocabulary is closed: the refund proceeds, it does not proceed, or the case
is escalated. A sentence counts only when it states a fact: questions and
conditional sentences are skipped, and a term preceded by a negation or by a
purpose ("para escalar", "puedo escalar") is not an escalation. An escalation
prevails over the other two, because escalating usually also says that the
direct refund does not proceed. Approval and denial in the same message, with no
escalation, is not guessed: it is unresolved and goes to manual annotation.
"""

from __future__ import annotations

import re
import unicodedata
from enum import Enum

from casestudy.domain.policy import Decision


class Unresolved(Enum):
    UNRESOLVED = "sin resolver"


UNRESOLVED = Unresolved.UNRESOLVED
type Extracted = Decision | Unresolved | None

_SENTENCES = re.compile(r"(?<=[.!?;])\s+|\n+")
_CLAUSES = re.compile(r"[,:()]|\s(?:y|pero|aunque|sin embargo|asi que|por lo que|porque|ya que)\s")
_CONDITIONAL = re.compile(r"(?<!\w)si(?!\w)|¿")
_WINDOW = 6

_NOUN = re.compile(r"reembols|devoluci|devolver\w* (?:el|tu|su) dinero")
_ESCALATION = re.compile(
    r"\bescal(?:o|e|are|ado|ada|ar|arlo|arla|arlos|ando|amos|aremos)\b|\btck-|"
    r"\breclamo de garantia\b|\b(?:el|tu|un|su|del) ticket\b"
)
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


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.replace("*", "").lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _preceding_words(clause: str, start: int) -> set[str]:
    return set(re.findall(r"\w+", clause[:start])[-_WINDOW:])


def _clause_signals(clause: str, has_noun: bool) -> set[Decision]:
    signals: set[Decision] = set()
    if _OUT_OF_SCOPE.search(clause):
        return signals
    for match in _ESCALATION.finditer(clause):
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


def decision_in(text: str) -> Extracted:
    """The decision a single agent message states, if it states one."""
    signals: set[Decision] = set()
    for sentence in _SENTENCES.split(text):
        if _CONDITIONAL.search(sentence.lower()):
            continue
        plain = _plain(sentence)
        has_noun = bool(_NOUN.search(plain))
        for clause in _CLAUSES.split(plain):
            signals |= _clause_signals(clause, has_noun)
    if Decision.ESCALATED in signals:
        return Decision.ESCALATED
    if len(signals) > 1:
        return UNRESOLVED
    return signals.pop() if signals else None
