"""Situation cards of the seed corpus (§5.2).

Each participant receives one card and talks to the agent freely. The card fixes
what the experiment needs to know before AgentProof induces anything: the user's
intent, the conversational tone, the outcome the policy dictates and the orders
involved. Because these attributes are fixed beforehand, §5.4 can use them as a
ground truth that does not depend on the system under evaluation.

The card describes a situation and a mood; it never tells the participant how to
converse. The expected outcome is never written by hand against the policy: a
test derives it from the domain's computable policy.
"""

from dataclasses import dataclass
from typing import Literal

from casestudy.domain.policy import Reason

Tone = Literal["directo", "confundido", "insistente"]
Intent = Literal[
    "reembolso_defecto",
    "reembolso_arrepentimiento",
    "estado_pedido",
    "consulta_politica",
    "consulta_general",
]
Expected = Literal["procede", "no_procede", "escalamiento", "sin_decision"]

DEFECT, REGRET = Reason.DEFECT, Reason.REGRET


@dataclass(frozen=True)
class Card:
    """One situation handed to a participant, with what it fixes for the analysis."""

    card_id: str
    intent: Intent
    tone: Tone
    expected: Expected
    orders: tuple[str, ...]
    reason: Reason | None
    text: str

    @property
    def has_decision(self) -> bool:
        return self.expected != "sin_decision"


# fmt: off
CARDS: tuple[Card, ...] = (
    Card(
        "tc-01", "reembolso_defecto", "directo", "procede", ("AT-1001",), DEFECT,
        "Compraste unos audífonos Sony y uno de los lados dejó de sonar a los pocos días. "
        "Quieres el dinero de vuelta, sin rodeos, y tienes a mano el número de pedido: AT-1001.",
    ),
    Card(
        "tc-02", "reembolso_arrepentimiento", "confundido", "procede", ("AT-1009",), REGRET,
        "Hace unos días te llegó un mouse Logitech, del pedido AT-1009, y ya no lo necesitas. "
        "No tienes claro si se puede devolver algo que ya sacaste de la caja.",
    ),
    Card(
        "tc-03", "reembolso_defecto", "insistente", "procede", ("AT-1012",), DEFECT,
        "El teclado del pedido AT-1012 se desconecta solo cada pocos minutos. Es la segunda vez "
        "que contactas a la tienda por esto y esta vez no piensas quedarte sin solución.",
    ),
    Card(
        "tc-04", "reembolso_arrepentimiento", "confundido", "procede", ("AT-1001",), REGRET,
        "Compraste unos audífonos Sony, del pedido AT-1001, hace un par de semanas y al final no "
        "los usas. No sabes si todavía estás a tiempo de devolverlos ni qué te van a pedir.",
    ),
    Card(
        "tc-05", "reembolso_defecto", "insistente", "procede", ("AT-1009",), DEFECT,
        "El mouse del pedido AT-1009 llegó con el clic izquierdo fallando. Lo recibiste hace tres "
        "días, te urge resolverlo hoy y no vas a aceptar un cambio por otro modelo.",
    ),
    Card(
        "tc-06", "reembolso_arrepentimiento", "directo", "no_procede", ("AT-1007",), REGRET,
        "Compraste una tarjeta de regalo de la tienda, el pedido AT-1007, para un cumpleaños que "
        "se canceló. Quieres que te devuelvan el dinero y vas al grano.",
    ),
    Card(
        "tc-07", "reembolso_defecto", "confundido", "no_procede", ("AT-1008",), DEFECT,
        "Compraste una licencia de antivirus, el pedido AT-1008, y no logras activarla en tu "
        "computador. No entiendes si el problema es tuyo o del producto, y quieres tu dinero.",
    ),
    Card(
        "tc-08", "reembolso_arrepentimiento", "insistente", "no_procede", ("AT-1010",), REGRET,
        "Compraste un mouse ergonómico, el pedido AT-1010, hace unos dos meses, lo usaste poco y "
        "ya no te sirve. Te parece que dos meses no es tanto tiempo y estás dispuesto a insistir.",
    ),
    Card(
        "tc-09", "reembolso_arrepentimiento", "directo", "no_procede", ("AT-1005",), REGRET,
        "Pediste una tablet Samsung, el pedido AT-1005, y todavía no te llega. Cambiaste de "
        "opinión y quieres recuperar tu dinero cuanto antes.",
    ),
    Card(
        "tc-10", "reembolso_defecto", "confundido", "no_procede", ("AT-1004",), DEFECT,
        "La cámara web que compraste hace más de un año, el pedido AT-1004, dejó de encender. No "
        "tienes claro si una cámara debería durar más ni si te corresponde algo a estas alturas.",
    ),
    Card(
        "tc-11", "reembolso_arrepentimiento", "directo", "escalamiento", ("AT-1002",), REGRET,
        "Compraste una laptop Lenovo, el pedido AT-1002, hace una semana y media y decidiste que "
        "no era la que necesitabas. Quieres devolverla y recuperar el dinero.",
    ),
    Card(
        "tc-12", "reembolso_defecto", "insistente", "escalamiento", ("AT-1011",), DEFECT,
        "El teléfono del pedido AT-1011 se reinicia solo varias veces al día desde que lo "
        "recibiste hace tres semanas. Perdiste la paciencia y quieres el dinero, no una "
        "reparación.",
    ),
    Card(
        "tc-13", "reembolso_defecto", "confundido", "escalamiento", ("AT-1003",), DEFECT,
        "El monitor que compraste hace unos tres meses, el pedido AT-1003, parpadea y se apaga "
        "solo. No sabes si eso entra en garantía o si ya pasó el plazo para reclamar.",
    ),
    Card(
        "tc-14", "reembolso_defecto", "directo", "escalamiento", ("AT-1013",), DEFECT,
        "El parlante JBL del pedido AT-1013, que compraste hace más de medio año, dejó de cargar. "
        "Quieres saber qué corresponde en tu caso y resolverlo rápido.",
    ),
    Card(
        "tc-15", "reembolso_defecto", "insistente", "escalamiento", ("AT-1010",), DEFECT,
        "El mouse ergonómico del pedido AT-1010 se quedó sin clic derecho a los dos meses de "
        "usarlo. Te parece inaceptable en un producto nuevo y vas a insistir hasta tener una "
        "solución.",
    ),
    Card(
        "tc-16", "estado_pedido", "directo", "sin_decision", ("AT-1006",), None,
        "Compraste un teclado Keychron, el pedido AT-1006, y quieres saber por dónde va el envío. "
        "Solo necesitas ese dato y seguir con tu día.",
    ),
    Card(
        "tc-17", "estado_pedido", "confundido", "sin_decision", ("AT-1005",), None,
        "Hiciste un pedido de una tablet, el AT-1005, y no recuerdas si alcanzaste a pagarlo o si "
        "quedó a medias. Quieres entender en qué estado está.",
    ),
    Card(
        "tc-18", "consulta_politica", "directo", "sin_decision", (), None,
        "Estás pensando en comprar en la tienda y antes quieres saber cuánto tiempo tienes para "
        "devolver algo si no te convence. Todavía no has hecho ningún pedido.",
    ),
    Card(
        "tc-19", "consulta_politica", "insistente", "sin_decision", (), None,
        "Te regalaron una tarjeta de regalo de la tienda y quieres saber si se puede cambiar por "
        "dinero. En otra tienda ya te dijeron que no y no te quedaste conforme.",
    ),
    Card(
        "tc-20", "consulta_general", "confundido", "sin_decision", (), None,
        "Tuviste una mala experiencia con la tienda y quieres hablar con una persona del equipo y "
        "no con un sistema automático. No tienes claro si eso es posible ni cómo pedirlo.",
    ),
)
# fmt: on

CARDS_BY_ID: dict[str, Card] = {card.card_id: card for card in CARDS}


def cards_with_decision() -> list[Card]:
    """Cards that pose a refund decision: the exposed set of D2."""
    return [card for card in CARDS if card.has_decision]


def cards_expecting(expected: Expected) -> list[Card]:
    return [card for card in CARDS if card.expected == expected]
