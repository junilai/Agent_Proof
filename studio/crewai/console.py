"""A terminal conversation with the CrewAI edition of the case-study agent.

CrewAI has no local UI for a single agent, so this console plays that part: each
customer message is one turn of the AgentProof session, and it prints every tool
call with its arguments and result, the reply, and how the turn ended. VARIANT
picks the mutation (baseline by default). CrewAI's telemetry and execution
traces are turned off before CrewAI is imported.
"""

import os

os.environ.update(
    CREWAI_DISABLE_TELEMETRY="true",
    OTEL_SDK_DISABLED="true",
    CREWAI_DISABLE_TRACKING="true",
    CREWAI_TRACING_ENABLED="false",
)

import asyncio  # noqa: E402
import json  # noqa: E402
from collections.abc import Callable, Iterator  # noqa: E402

from agentproof.adapters.crewai import CrewAISession  # noqa: E402
from agentproof.session import AgentTurn  # noqa: E402
from casestudy.editions.crewai import builder  # noqa: E402


def build_session(variant: str | None = None, model=None) -> CrewAISession:
    return CrewAISession(builder(variant or os.environ.get("VARIANT", "baseline"), model=model))


def render(turn: AgentTurn, limit: int) -> list[str]:
    lines = []
    calls = [e for e in turn.events if e.kind == "tool_call"]
    for event in turn.events:
        if event.kind == "tool_call":
            arguments = json.dumps(event.arguments, ensure_ascii=False)
            result = json.dumps(event.result, ensure_ascii=False)
            mark = "  [error]" if event.is_error else ""
            lines += [f"  → {event.tool} {arguments}{mark}", f"    ← {result}"]
        elif event.kind == "error":
            lines.append(f"  ! {event.text}")
    lines.append(f"agente> {turn.reply}")
    plural = "llamada" if len(calls) == 1 else "llamadas"
    usage = turn.usage
    cost = f"USD {usage.cost_usd:.4f}" if usage and usage.cost_usd is not None else "sin precio"
    tokens = f"{usage.input_tokens}/{usage.output_tokens}" if usage else "0/0"
    lines.append(
        f"  [{turn.stop_reason} · {len(calls)} {plural} a herramientas · límite: {limit} rondas"
        f" · tokens {tokens} · {cost} según la tabla]"
    )
    return lines


async def chat(session: CrewAISession, lines: Iterator[str], write: Callable[[str], None]) -> None:
    async with session:
        for line in lines:
            if not line.strip():
                continue
            turn = await session.send(line)
            for text in render(turn, session.agent.max_iter):
                write(text)


def _typed() -> Iterator[str]:
    while True:
        try:
            yield input("cliente> ")
        except EOFError:
            return


if __name__ == "__main__":
    session = build_session()
    print(f"Edición CrewAI, variante {os.environ.get('VARIANT', 'baseline')}. Ctrl-D para salir.")
    asyncio.run(chat(session, _typed(), print))
