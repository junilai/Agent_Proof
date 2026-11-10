# La edición CrewAI en una consola local

CrewAI no ofrece una interfaz como LangGraph Studio para un agente suelto: CrewAI Studio, el panel de AMP y su visor de trazas son servicios en la nube que piden iniciar sesión y envían los datos del agente a CrewAI, y `crewai chat` conversa con un `Crew` completo a través de otro modelo, no con nuestro agente. Por eso esta carpeta trae una consola de terminal mínima, `console.py`, que conversa con el agente del caso de estudio turno a turno y muestra lo que hace en cada uno. La edición es `src/casestudy/editions/crewai.py`; la consola la usa tal cual, a través de la misma sesión del adaptador que usa AgentProof.

## Cómo abrirla

Desde la raíz del repositorio:

```bash
uv sync --extra crewai
uv run --env-file .env python studio/crewai/console.py
```

Cada línea que se escribe es un mensaje del cliente; Ctrl-D termina la conversación.

- **Variante.** Por omisión se abre la línea base. Para ver una mutación, definir `VARIANT` antes de arrancar, por ejemplo `VARIANT=d6 uv run --env-file .env python studio/crewai/console.py` para ver el corte tras dos rondas de herramientas.
- **API.** Cada turno llama al modelo y cuesta lo mismo que en el experimento (Claude Sonnet 5, o Claude Haiku 4.5 en D3); la clave se lee de `.env`. La consola muestra el costo del turno según la tabla de precios, pero el proveedor de Anthropic de CrewAI usa siempre caché de prompts, así que el costo facturado es el de la consola de Anthropic.
- **Telemetría.** La consola define `CREWAI_DISABLE_TELEMETRY=true`, `OTEL_SDK_DISABLED=true`, `CREWAI_DISABLE_TRACKING=true` y `CREWAI_TRACING_ENABLED=false` antes de importar CrewAI, y la sesión se niega a abrir si alguna de las dos vías (telemetría o envío de trazas) quedara activa. Nada sale de la máquina salvo las llamadas a la API de Anthropic.

## Lo que se ve

Un turno de ejemplo (las cifras son ilustrativas):

```
cliente> ¿Dónde está mi pedido AT-1001?
  → lookup_order {"order_id": "AT-1001"}
    ← {"pedido": "AT-1001", "estado": "entregado", …}
agente> Tu pedido AT-1001 fue entregado el 21 de septiembre.
  [completed · 1 llamada a herramientas · límite: 10 rondas · tokens 2310/85 · USD 0.0055 según la tabla]
```

- Cada `→` es una llamada a una herramienta del dominio con sus argumentos, y cada `←` su resultado; `[error]` marca una herramienta que falló.
- La última línea dice cómo terminó el turno: `completed`, `step_limit` (se alcanzaron las rondas de `max_iter`, 10, o 2 en D6, y CrewAI pidió una respuesta final sin herramientas, que es la que ve el cliente) o `error`.
- CrewAI imprime además sus propios recuadros de inicio y fin de cada turno, que incluyen el prompt del agente; quedan en la terminal.

Las equivalencias con las otras ediciones se registran en las decisiones del proyecto ([docs/decisiones.md](../../docs/decisiones.md)).

## Cuándo no usarla

La consola nunca corre durante una tanda del experimento: cerrarla antes de `agentproof run`, para que su gasto no se mezcle con el de la tanda en la consola de Anthropic.
