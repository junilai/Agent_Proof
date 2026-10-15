"""The eight conditions of the experiment (§5.4, §5.5).

``baseline-a`` is the reference every candidate is compared with. ``baseline-b``
is an independent run of the same agent, reserved for the negative control: any
scenario flagged when comparing the two baselines is a false positive caused by
the stochastic variability of the system.
"""

from dataclasses import dataclass
from typing import Literal

Role = Literal["reference", "negative_control", "candidate"]


@dataclass(frozen=True)
class Condition:
    name: str
    variant: str
    role: Role


REFERENCE = Condition("baseline-a", "baseline", "reference")
NEGATIVE_CONTROL = Condition("baseline-b", "baseline", "negative_control")

CONDITIONS: tuple[Condition, ...] = (
    REFERENCE,
    NEGATIVE_CONTROL,
    *(Condition(name, name, "candidate") for name in ("d1", "d2", "d3", "d4", "d5", "d6")),
)

CONDITIONS_BY_NAME: dict[str, Condition] = {c.name: c for c in CONDITIONS}


def candidates() -> list[Condition]:
    return [c for c in CONDITIONS if c.role == "candidate"]
