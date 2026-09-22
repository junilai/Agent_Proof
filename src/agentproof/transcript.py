"""Blind transcript of a trace: the only view of a conversation that the inducer
and the judge ever read (§5.1).

It contains the messages, the tool calls with their results and the errors, and
never the model, condition, variant, run, agent or timestamps. Pinned model
identifiers are masked even inside text, so a degraded model (D3) cannot give
itself away through an error message.
"""

import json
from typing import Any

from agentproof.models import pinned_model_ids
from agentproof.schema import Trace

MODEL_MASK = "[modelo]"
_LABELS = {"user_message": "USUARIO", "agent_message": "AGENTE", "error": "ERROR"}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _mask_models(text: str) -> str:
    for model_id in sorted(pinned_model_ids(), key=len, reverse=True):
        text = text.replace(model_id, MODEL_MASK)
    return text


def render_transcript(trace: Trace) -> str:
    lines = []
    for event in trace.events:
        if event.kind == "tool_call":
            call = f"{event.tool}({_json(event.arguments or {})})"
            line = f"[HERRAMIENTA] {call} -> {_json(event.result)}"
            if event.is_error:
                line += " (error)"
        else:
            line = f"[{_LABELS[event.kind]}] {event.text or ''}"
        lines.append(_mask_models(line))
    return "\n".join(lines)
