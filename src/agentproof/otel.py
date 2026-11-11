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
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from agentproof import __version__
from agentproof.schema import Trace, TraceEvent

SEMCONV_REPOSITORY = "open-telemetry/semantic-conventions-genai"
SEMCONV_COMMIT = "e6658f14c9d9ea0760825f029cb82e7673f48fab"
SEMCONV_DATE = "2026-11-06"

SPAN_KIND_INTERNAL = 1
STATUS_CODE_ERROR = 2
OTHER_ERROR = "_OTHER"
"""Fallback value of ``error.type`` when the error names no exception class."""
TOOL_ERROR = "tool_error"
"""``error.type`` of a tool call the trace marks with ``is_error``."""

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
        parent: str | None = None,
        error: str | None = None,
        error_type: str | None = None,
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
        if parent is not None:
            span["parentSpanId"] = parent
        if error is not None:
            span["attributes"] += _key_values({"error.type": error_type or _error_type(error)})
            span["status"] = {"code": STATUS_CODE_ERROR, "message": error}
        self.spans.append(span)
        return span_id


def _error_type(text: str) -> str:
    """Exception class of an error event (``Class: message``), else ``_OTHER``."""
    match = re.match(r"([A-Za-z_][\w.]*): ", text)
    return match.group(1) if match else OTHER_ERROR


@dataclass
class _Turn:
    """A user message and what the agent did until the next one."""

    number: int
    opening: TraceEvent
    events: list[TraceEvent] = field(default_factory=list)
    stop_reason: str = "completed"


def _split(trace: Trace) -> tuple[list[TraceEvent], list[_Turn]]:
    """Events that belong to the conversation itself, and the agent turns."""
    outside: list[TraceEvent] = []
    turns: list[_Turn] = []
    for event in trace.events:
        if event.kind == "user_message":
            turns.append(_Turn(len(turns) + 1, event))
        elif turns:
            turns[-1].events.append(event)
        else:
            outside.append(event)
    if turns and trace.termination == "simulator_error":
        last = turns[-1].events
        if last and last[-1].kind == "error":  # the simulated user failed after the turn
            outside.append(last.pop())
    if turns and trace.termination in ("step_limit", "agent_error"):
        turns[-1].stop_reason = "step_limit" if trace.termination == "step_limit" else "error"
    return outside, turns


def _last_error(events: list[TraceEvent]) -> str | None:
    errors = [e.text or "" for e in events if e.kind == "error"]
    return errors[-1] if errors else None


def _turn_attributes(trace: Trace, turn: _Turn) -> dict[str, Any]:
    replies = [
        {"type": "text", "content": e.text}
        for e in turn.events
        if e.kind == "agent_message" and e.text
    ]
    return {
        "gen_ai.operation.name": "invoke_agent",
        "gen_ai.agent.name": trace.agent,
        "gen_ai.agent.version": trace.variant,
        "gen_ai.conversation.id": trace.trace_id,
        "gen_ai.input.messages": [
            {"role": "user", "parts": [{"type": "text", "content": turn.opening.text or ""}]}
        ],
        "gen_ai.output.messages": [{"role": "assistant", "parts": replies}] if replies else None,
        "agentproof.turn": turn.number,
        "agentproof.step": turn.opening.step,
        "agentproof.turn.stop_reason": turn.stop_reason,
    }


def _tool_attributes(trace: Trace, event: TraceEvent) -> dict[str, Any]:
    return {
        "gen_ai.operation.name": "execute_tool",
        "gen_ai.tool.name": event.tool,
        "gen_ai.tool.type": "function",
        "gen_ai.tool.call.arguments": event.arguments,
        "gen_ai.tool.call.result": None if event.is_error else event.result,
        "gen_ai.agent.name": trace.agent,
        "gen_ai.conversation.id": trace.trace_id,
        "agentproof.step": event.step,
    }


def _as_text(raw: Any) -> str:
    if raw is None:
        return ""
    return raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)


def _add_tool_calls(spans: _Spans, trace: Trace, events: list[TraceEvent], parent: str) -> None:
    for event in events:
        if event.kind != "tool_call":
            continue
        spans.add(
            f"tool:{event.step}",
            f"execute_tool {event.tool}",
            event.ts,
            event.ts,
            _tool_attributes(trace, event),
            parent=parent,
            error=_as_text(event.result) if event.is_error else None,
            error_type=TOOL_ERROR,
        )


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
    outside, turns = _split(trace)
    conversation = spans.add(
        "conversation",
        "agentproof.conversation",
        trace.started_at,
        trace.ended_at,
        _conversation_attributes(trace),
        error=_last_error(outside),
    )
    _add_tool_calls(spans, trace, outside, conversation)
    for turn in turns:
        error = None
        if turn.stop_reason == "error":
            error = _last_error(turn.events) or "agent_error"
        turn_span = spans.add(
            f"turn:{turn.number}",
            f"invoke_agent {trace.agent}",
            turn.opening.ts,
            max([turn.opening.ts, *(e.ts for e in turn.events)]),
            _turn_attributes(trace, turn),
            parent=conversation,
            error=error,
        )
        _add_tool_calls(spans, trace, turn.events, turn_span)
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
