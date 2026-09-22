"""One structured call to a model, with the retry policy of the spec (§9).

Used by the inducer and the judge. A refused, truncated or malformed answer is
retried once; if the second attempt also fails, ``LLMCallError`` reaches the
caller, which records it. Transient API errors (429, 5xx) are already retried by
the Anthropic SDK. No automatic fallback to another model is ever enabled: the
measuring instrument must always be the same model.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from agentproof.models import CallSettings


class LLMCallError(RuntimeError):
    """The model refused, truncated or malformed its answer on every attempt."""


def structured_call[M: BaseModel, R](
    client: Any,
    settings: CallSettings,
    *,
    system: str,
    prompt: str,
    output_type: type[M],
    validate: Callable[[M], R],
    attempts: int = 2,
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
    problems: list[str] = []
    for _ in range(attempts):
        try:
            response = client.messages.parse(**request)
        except ValueError as exc:  # pydantic's ValidationError: the output broke the schema
            problems.append(f"salida inválida ({type(exc).__name__})")
            continue
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
