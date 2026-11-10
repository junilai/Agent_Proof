# La edición LangGraph en LangGraph Studio

LangGraph Studio muestra el grafo del agente del caso de estudio y permite conversar con él viendo cada paso: qué nodo corre, qué herramientas pide el modelo, qué devuelven y cómo cambia el estado (los mensajes, el contador de llamadas al modelo y el corte por límite de pasos). La edición es `src/casestudy/editions/langgraph.py`; Studio la abre tal cual, sin cambiar nada de ella.

## Cómo abrirlo

Desde la raíz del repositorio:

```bash
uv sync --extra langgraph --group studio
cd studio/langgraph
uv run --env-file ../../.env langgraph dev --no-browser
```

Después, en Chrome, abrir <https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024>. Safari bloquea la conexión a `localhost`: con Safari, agregar `--tunnel` al comando.

- **Variante.** Por omisión se abre la línea base. Para ver una mutación, definir `VARIANT` antes de arrancar, por ejemplo `VARIANT=d6 uv run … langgraph dev --no-browser` para ver el corte tras dos llamadas al modelo.
- **API.** Ver el grafo no usa la API. Conversar con el agente sí: cada turno cuesta lo mismo que en el experimento (Claude Sonnet 5), y la clave se lee de `.env`.
- **Trazas.** `langgraph.json` desactiva el envío de trazas a LangSmith (`LANGSMITH_TRACING=false`) y la telemetría de la CLI. Las conversaciones quedan en el servidor local.

## Lo que se ve

```
__start__ → start → model ⇄ tools → cut → __end__
                      └──────────────────→ __end__
```

- `start` pone el contador de llamadas en cero al comenzar cada turno del cliente.
- `model` llama al modelo con el prompt del dominio delante de la historia; si pide herramientas, sigue a `tools`, y si no, el turno termina.
- `tools` ejecuta las herramientas del dominio. Después, si el contador llegó al límite (10, o 2 en D6), el turno pasa a `cut` y termina como `step_limit`; si no, vuelve a `model`.

Las equivalencias con la edición Claude Agent SDK están en [D-012](../../docs/decisiones.md).

## Cuándo no usarlo

Studio nunca corre durante una tanda del experimento: cerrarlo antes de `agentproof run`. El adaptador, además, se niega a correr si el envío de trazas está activo.
