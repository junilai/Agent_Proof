"""One structured call to a model, with the retry policy of the spec (§9).

Used by the inducer and the judge. A refused, truncated or malformed answer is
retried once; if the second attempt also fails, ``LLMCallError`` reaches the
caller, which records it. Transient API errors (429, 5xx) are already retried by
the Anthropic SDK. No automatic fallback to another model is ever enabled: the
measuring instrument must always be the same model. A ``Meter`` collects the
tokens and seconds of every call, failed attempts included, since they are
paid as well (D-007).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from agentproof.models import CallSettings
from agentproof.schema import Usage


class LLMCallError(RuntimeError):
    """The model refused, truncated or malformed its answer on every attempt."""


def usage_of(response: Any) -> Usage:
    """Tokens the API reported for a response; zero when it reported none."""
    reported = getattr(response, "usage", None)
    return Usage(
        input_tokens=getattr(reported, "input_tokens", 0) or 0,
        output_tokens=getattr(reported, "output_tokens", 0) or 0,
    )


@dataclass
class Meter:
    """Tokens and seconds of every call a component made."""

    usage: Usage = field(default_factory=Usage)
    seconds: float = 0.0

    def add(self, response: Any, started: float) -> None:
        self.usage += usage_of(response)
        self.seconds += time.perf_counter() - started


def structured_call[M: BaseModel, R](
    client: Any,
    settings: CallSettings,
    *,
    system: str,
    prompt: str,
    output_type: type[M],
    validate: Callable[[M], R],
    attempts: int = 2,
    meter: Meter | None = None,
) -> R:
    request: dict[str, Any] = {
        "model": settings.model,
        "max_tokens": settings.max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
        "output_format": output_type,
    }
    if settings.effort is not None:
        request["output_config"] = {"effort": settings.effort}
    meter = meter if meter is not None else Meter()
    problems: list[str] = []
    for _ in range(attempts):
        started = time.perf_counter()
        try:
            response = client.messages.parse(**request)
        except ValueError as exc:  # pydantic's ValidationError: the output broke the schema
            meter.add(None, started)
            problems.append(f"salida inválida ({type(exc).__name__})")
            continue
        meter.add(response, started)
        if response.stop_reason in ("refusal", "max_tokens"):
            problems.append(f"stop_reason={response.stop_reason}")
            continue
        if response.parsed_output is None:
            problems.append("sin salida estructurada")
            continue
        try:
            return validate(response.parsed_output)
        except ValueError as exc:
            problems.append(f"validación: {exc}")
    raise LLMCallError(f"{settings.model}: " + "; ".join(problems))
