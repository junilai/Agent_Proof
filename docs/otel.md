# Mapeo de las trazas a OpenTelemetry

AgentProof guarda cada conversación en su propio esquema (`agentproof.schema.Trace`). `agentproof.otel` la traduce a spans de OpenTelemetry que siguen las convenciones semánticas de IA generativa (GenAI), en formato OTLP/JSON, sin depender del SDK de OpenTelemetry ni de ningún paquete nuevo. La traducción es una función pura (`trace_to_otlp`): no cambia la traza, no lee nada fuera de ella y da siempre la misma salida. La decisión que fija la versión de las convenciones es D-015.

## Versión de las convenciones

| | |
|---|---|
| Repositorio | [`open-telemetry/semantic-conventions-genai`](https://github.com/open-telemetry/semantic-conventions-genai). Las convenciones GenAI se mudaron ahí: `docs/gen-ai/README.md` de `open-telemetry/semantic-conventions` dice "Moved" y ya no se mantiene |
| Commit fijado | `e6658f14c9d9ea0760825f029cb82e7673f48fab`, del 6 de noviembre de 2026 (#692) |
| Versiones publicadas | Ninguna: el repositorio no tiene releases ni tags. Su `model/manifest.yaml` declara `schema_url: https://opentelemetry.io/schemas/gen-ai-dev/1.42.0-dev` y depende de las convenciones generales v1.45.0 |
| Estabilidad | Todo el conjunto está en *development* (`stability: development` en el manifiesto y en cada atributo y span que se usa). Solo `error.type` y `service.name`, que vienen de las convenciones generales, son estables |
| Archivos consultados | `model/gen-ai/spans.yaml` (spans `gen_ai.invoke_agent.internal` y `gen_ai.execute_tool`), `model/gen-ai/registry.yaml` (atributos), `model/gen-ai/gen-ai-input-messages.json` y `gen-ai-output-messages.json` (forma de los mensajes), `docs/gen-ai/gen-ai-agent-spans.md` y `docs/gen-ai/gen-ai-spans.md` ("Recording content on attributes") |

El commit queda también en la salida, como atributo `agentproof.semconv.commit` del *scope*. `tests/test_otel.py` tiene su propia tabla de los atributos estándar con su estabilidad en ese commit: si el código emite un atributo que no está en la tabla ni lleva el prefijo `agentproof.`, la prueba falla.

## Estructura

Una traza de AgentProof es una traza de OpenTelemetry (un `traceId`) con tres niveles de spans, todos de tipo `INTERNAL`:

```
agentproof.conversation                 (raíz: la conversación)
├── invoke_agent <agente>               (un turno: un mensaje del usuario y lo que hizo el agente)
│   ├── execute_tool lookup_order       (una llamada a herramienta)
│   └── execute_tool get_refund_policy
└── invoke_agent <agente>
    └── execute_tool create_ticket
```

- **Span raíz de la conversación.** Las convenciones no definen un span de conversación: la agrupan con `gen_ai.conversation.id`. Aun así se usa una raíz propia, sin `gen_ai.operation.name`, porque la conversación la conduce AgentProof (el usuario simulado o la persona), que está fuera del agente, y porque ahí van los datos de la traza que no son de ningún turno: la condición, la repetición, el motivo de terminación y el uso total. Sin raíz, un visor mostraría tantas trazas sueltas como turnos.
- **Un `invoke_agent` por turno.** Es el span `gen_ai.invoke_agent.internal`: el agente corre en el mismo proceso, y en las cuatro ediciones un modelo decide qué herramienta llamar, que es el caso en que la convención pide `invoke_agent` (no `invoke_workflow`). Un turno empieza en un mensaje del usuario y abarca los eventos hasta el siguiente.
- **Un `execute_tool` por llamada**, hijo de su turno. Una llamada que quedara fuera de todo turno colgaría de la raíz; en las trazas de AgentProof no ocurre.

**Ids.** El `traceId` (32 hex) y cada `spanId` (16 hex) son los primeros caracteres del SHA-256 de `agentproof:<trace_id>:<clave>`, con clave `trace`, `conversation`, `turn:<n>` o `tool:<step>`. Así la misma traza produce siempre el mismo documento.

**Tiempos.** La raíz va de `started_at` a `ended_at`. Un turno va del instante del mensaje del usuario al del último evento del turno. Un `execute_tool` dura cero: la traza guarda el instante en que se registró la llamada, que es cuando terminó el turno, no cuándo empezó ni cuánto tardó la herramienta.

## Tabla de mapeo

Estabilidad: **D** = *development*, **E** = estable. "—" = atributo propio, sin estándar.

### `Trace` (span raíz `agentproof.conversation`)

| Campo | Atributo | Estab. | Nota |
|---|---|---|---|
| `trace_id` | `gen_ai.conversation.id` | D | También en cada turno y cada herramienta |
| `usage.input_tokens` | `gen_ai.usage.input_tokens` | D | Uso total del agente en la conversación |
| `usage.output_tokens` | `gen_ai.usage.output_tokens` | D | Ídem |
| `usage.cost_usd` | `agentproof.usage.cost_usd` | — | Se omite si es desconocido |
| `simulator_usage.*` | `agentproof.simulator.usage.input_tokens`, `.output_tokens`, `.cost_usd` | — | El usuario simulado no es el agente |
| `kind` | `agentproof.trace.kind` | — | `seed` o `run` |
| `adapter` | `agentproof.adapter` | — | |
| `agent` | `agentproof.agent` | — | En los turnos es además `gen_ai.agent.name` |
| `variant` | `agentproof.variant` | — | En los turnos es además `gen_ai.agent.version` |
| `condition`, `run_id`, `scenario_id`, `repetition`, `card_id`, `attempt` | `agentproof.<campo>` | — | Se omiten si no existen (trazas semilla) |
| `termination` | `agentproof.termination` | — | |
| `agent_seconds`, `simulator_seconds` | `agentproof.agent_seconds`, `agentproof.simulator_seconds` | — | |
| `models` | `agentproof.models` | — | Valor estructurado, tal como está en la traza |
| `started_at`, `ended_at` | `startTimeUnixNano`, `endTimeUnixNano` | — | Campos del span |
| error del usuario simulado | `error.type` + estado `ERROR` | E | Ver "Errores" |

### Turno (span `invoke_agent <agent>`)

| Origen | Atributo | Estab. | Nota |
|---|---|---|---|
| — | `gen_ai.operation.name = invoke_agent` | D | Obligatorio |
| `agent` | `gen_ai.agent.name` | D | El nombre del span es `invoke_agent {gen_ai.agent.name}` |
| `variant` | `gen_ai.agent.version` | D | La variante es la versión del agente que se compara |
| `trace_id` | `gen_ai.conversation.id` | D | |
| `TraceEvent` `user_message` | `gen_ai.input.messages` | D | `[{"role": "user", "parts": [{"type": "text", "content": …}]}]` |
| `TraceEvent` `agent_message` del turno | `gen_ai.output.messages` | D | Un mensaje `assistant` con una parte `text` por evento, en orden; se omite si el turno no tiene texto |
| número del turno | `agentproof.turn` | — | Desde 1 |
| `step` del mensaje del usuario | `agentproof.step` | — | Para volver a la traza |
| `termination` en el último turno | `agentproof.turn.stop_reason` | — | `completed`, `step_limit` o `error`. Los turnos anteriores al último siempre son `completed` |
| error del agente | `error.type` + estado `ERROR` | E | Ver "Errores" |

### Llamada a herramienta (span `execute_tool <tool>`)

| Campo de `TraceEvent` | Atributo | Estab. | Nota |
|---|---|---|---|
| — | `gen_ai.operation.name = execute_tool` | D | |
| `tool` | `gen_ai.tool.name` | D | Nombre del dominio (`lookup_order`, `get_refund_policy`, `create_ticket`) |
| — | `gen_ai.tool.type = function` | D | Las herramientas son funciones que ejecuta la aplicación |
| `arguments` | `gen_ai.tool.call.arguments` | D | Objeto, como lo guardó la traza |
| `result` | `gen_ai.tool.call.result` | D | Solo si `is_error` es falso; objeto o texto, como lo guardó la traza |
| `is_error` | `error.type = tool_error` + estado `ERROR` | E | El resultado va en el mensaje del estado |
| `agent` de la traza | `gen_ai.agent.name` | D | |
| `trace_id` | `gen_ai.conversation.id` | D | |
| `step` | `agentproof.step` | — | |
| `ts` | `startTimeUnixNano` = `endTimeUnixNano` | — | |

### Recurso y *scope*

`service.name = agentproof` (estable) en el recurso; el *scope* se llama `agentproof.otel`, con la versión del paquete y los atributos `agentproof.semconv.repository` y `agentproof.semconv.commit`.

## Errores

- **Del agente.** Si la conversación terminó en `agent_error`, el último turno lleva el estado `ERROR`, con el texto del último evento `error` del turno como mensaje. `error.type` es la clase de la excepción, que `converse` escribe al comienzo del texto (`RuntimeError: …`); si no la hay, `_OTHER`, el valor de reserva de la convención.
- **Del usuario simulado.** Si la conversación terminó en `simulator_error`, el evento `error` final no es del agente: va a la raíz, no al turno. Un error antes del primer mensaje del usuario también va a la raíz.
- **De una herramienta.** `error.type = tool_error` en su span, sin `gen_ai.tool.call.result` (la convención reserva el resultado para las ejecuciones exitosas). No marca el turno: el agente recibe el error y sigue.
- **`step_limit` no es un error** (§5.4): queda en `agentproof.turn.stop_reason` y `agentproof.termination`, sin estado `ERROR`.

## Lo que no se mapea y por qué

| Atributo o span | Por qué no |
|---|---|
| Uso por turno (`gen_ai.usage.*` en `invoke_agent`) | La traza guarda solo el total de la conversación. Va en la raíz, una sola vez, para que sumar el uso de todos los spans dé el total sin contarlo dos veces |
| Spans de inferencia (`chat`) y `gen_ai.response.finish_reasons` | La traza no registra cada llamada al modelo, solo lo que el agente hizo en el turno |
| `gen_ai.request.model` | La traza no dice qué modelo usó la variante: `models` describe la configuración de todos los componentes (inductor, evaluador, usuario simulado, modelos del agente). Va entero en `agentproof.models` |
| `gen_ai.provider.name` | No es atributo del span `invoke_agent` interno; pertenece a los spans de inferencia, que no hay |
| `gen_ai.agent.id`, entidad `gen_ai.main_agent` | La convención pide un identificador estable asignado por un proveedor de agentes alojados; estos agentes corren en el proceso y no lo tienen |
| `gen_ai.tool.call.id` | Condicional a que el modelo lo haya dado, y la traza no lo guarda. No se inventa |
| `gen_ai.tool.description`, `gen_ai.tool.definitions`, `gen_ai.system_instructions` | No están en la traza: son de la edición del agente |
| `gen_ai.request.max_tokens`, `temperature` y demás parámetros | No están en la traza |
| Escenarios, veredictos del evaluador y fallas de evaluación | Son otros registros (`Scenario`, `Verdict`, `JudgeFailure`), no parte de la traza de la conversación |

Nada sale de fuera de la traza: ni la API key ni variables de entorno.

## Decisiones de interpretación

- **`gen_ai.conversation.id` es el `trace_id` de AgentProof.** La convención pide no usar como reserva un UUID nuevo ni el identificador de la traza de OpenTelemetry. El `trace_id` de AgentProof es el identificador que la aplicación da a la conversación, que es el caso en que la convención admite que la aplicación lo agregue.
- **`gen_ai.agent.version` es la variante.** AgentProof compara versiones del agente, y la variante (`baseline`, `d1`…`d6`) es exactamente eso. La variante sigue también en `agentproof.variant`.
- **`gen_ai.agent.name` es el campo `agent`**, la ruta de la fábrica del agente (por ejemplo `casestudy.editions.langgraph:builder`). Tiene baja cardinalidad, como exige la convención, aunque es un nombre técnico y no uno legible.
- **Los valores estructurados se emiten como `AnyValue`** (`kvlistValue`, `arrayValue`), no como texto JSON: la convención dice que los mensajes "MUST be recorded as AnyValue". Algunos visores aplanan o rechazan atributos estructurados.
- **Un resultado de herramienta en texto queda como texto.** El esquema de `gen_ai.tool.call.result` espera un objeto; `get_refund_policy` devuelve texto que no es JSON, y convertirlo en objeto sería inventar estructura.
- **Los mensajes son opcionales en la convención** (*opt-in*: `gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.tool.call.arguments`, `gen_ai.tool.call.result`). Se incluyen siempre, porque el contenido es lo que AgentProof evalúa y la traza ya lo guarda en local.

## Cómo exportar una traza

```bash
uv run python -m agentproof.otel results/runs/<corrida>/traces/<trace_id>.json > traza-otlp.json
```

El archivo es el cuerpo de una petición OTLP/HTTP con JSON. Para verlo en un visor local, por ejemplo un colector o Jaeger escuchando en el puerto 4318:

```bash
curl -X POST http://localhost:4318/v1/traces \
  -H 'Content-Type: application/json' --data @traza-otlp.json
```

La exportación se hace después de una corrida, sobre trazas guardadas, y a un destino local: ningún dato del agente sale a un servicio de terceros durante una corrida (spec de F4, §2).
