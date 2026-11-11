"""OpenTelemetry GenAI view of an AgentProof trace, as OTLP/JSON (D-015).

A pure translation: it reads one ``Trace`` and returns the OTLP/JSON document
(resourceSpans -> scopeSpans -> spans) that an OTLP collector accepts, without
the OpenTelemetry SDK. Attribute names follow the GenAI semantic conventions
at the pinned commit below; whatever has no standard attribute goes under the
``agentproof.`` prefix. Ids derive from the trace id, so the output is
reproducible.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

from agentproof import __version__
from agentproof.schema import Trace

SEMCONV_REPOSITORY = "open-telemetry/semantic-conventions-genai"
SEMCONV_COMMIT = "e6658f14c9d9ea0760825f029cb82e7673f48fab"
SEMCONV_DATE = "2026-11-06"

SPAN_KIND_INTERNAL = 1

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _nanos(moment: datetime) -> str:
    return str((moment - _EPOCH) // timedelta(microseconds=1) * 1000)


def _hex_id(trace_id: str, key: str, length: int) -> str:
    return hashlib.sha256(f"agentproof:{trace_id}:{key}".encode()).hexdigest()[:length]


def any_value(raw: Any) -> dict[str, Any]:
    """OTLP/JSON AnyValue of a JSON-like Python value; ``None`` is the empty value."""
    if raw is None:
        return {}
    if isinstance(raw, bool):
        return {"boolValue": raw}
    if isinstance(raw, int):
        return {"intValue": str(raw)}
    if isinstance(raw, float):
        return {"doubleValue": raw}
    if isinstance(raw, str):
        return {"stringValue": raw}
    if isinstance(raw, dict):
        return {"kvlistValue": {"values": _key_values(raw)}}
    if isinstance(raw, list | tuple):
        return {"arrayValue": {"values": [any_value(item) for item in raw]}}
    return {"stringValue": str(raw)}


def _key_values(attributes: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"key": key, "value": any_value(raw)} for key, raw in attributes.items() if raw is not None
    ]


class _Spans:
    """Builds the spans of one trace, all sharing its OTLP trace id."""

    def __init__(self, trace: Trace) -> None:
        self.source = trace.trace_id
        self.trace_id = _hex_id(trace.trace_id, "trace", 32)
        self.spans: list[dict[str, Any]] = []

    def add(
        self,
        key: str,
        name: str,
        start: datetime,
        end: datetime,
        attributes: dict[str, Any],
    ) -> str:
        span_id = _hex_id(self.source, key, 16)
        span: dict[str, Any] = {
            "traceId": self.trace_id,
            "spanId": span_id,
            "name": name,
            "kind": SPAN_KIND_INTERNAL,
            "startTimeUnixNano": _nanos(start),
            "endTimeUnixNano": _nanos(end),
            "attributes": _key_values(attributes),
        }
        self.spans.append(span)
        return span_id


def _conversation_attributes(trace: Trace) -> dict[str, Any]:
    return {
        "gen_ai.conversation.id": trace.trace_id,
        "gen_ai.usage.input_tokens": trace.usage.input_tokens,
        "gen_ai.usage.output_tokens": trace.usage.output_tokens,
        "agentproof.usage.cost_usd": trace.usage.cost_usd,
        "agentproof.simulator.usage.input_tokens": trace.simulator_usage.input_tokens,
        "agentproof.simulator.usage.output_tokens": trace.simulator_usage.output_tokens,
        "agentproof.simulator.usage.cost_usd": trace.simulator_usage.cost_usd,
        "agentproof.trace.kind": trace.kind,
        "agentproof.adapter": trace.adapter,
        "agentproof.agent": trace.agent,
        "agentproof.variant": trace.variant,
        "agentproof.condition": trace.condition,
        "agentproof.run_id": trace.run_id,
        "agentproof.scenario_id": trace.scenario_id,
        "agentproof.repetition": trace.repetition,
        "agentproof.card_id": trace.card_id,
        "agentproof.attempt": trace.attempt,
        "agentproof.termination": trace.termination,
        "agentproof.agent_seconds": trace.agent_seconds,
        "agentproof.simulator_seconds": trace.simulator_seconds,
        "agentproof.models": trace.models,
    }


def trace_to_otlp(trace: Trace) -> dict[str, Any]:
    """OTLP/JSON document with the spans of one conversation."""
    spans = _Spans(trace)
    spans.add(
        "conversation",
        "agentproof.conversation",
        trace.started_at,
        trace.ended_at,
        _conversation_attributes(trace),
    )
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": _key_values({"service.name": "agentproof"})},
                "scopeSpans": [
                    {
                        "scope": {
                            "name": "agentproof.otel",
                            "version": __version__,
                            "attributes": _key_values(
                                {
                                    "agentproof.semconv.repository": SEMCONV_REPOSITORY,
                                    "agentproof.semconv.commit": SEMCONV_COMMIT,
                                }
                            ),
                        },
                        "spans": spans.spans,
                    }
                ],
            }
        ]
    }
