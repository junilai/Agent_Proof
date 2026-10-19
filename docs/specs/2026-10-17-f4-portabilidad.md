# F4 Portabilidad: especificación

- **Autor:** Jarod Tierra Medina
- **Fecha:** 17 de octubre de 2026
- **Estado:** borrador
- **Contexto:** fase F4 del [plan maestro](2026-09-21-plan-maestro.md). "§" remite a la [planificación](../planificacion.pdf). El protocolo vigente es el del tag `preregistro-v2` ([pre-registro](../preregistro.md)).

## 1. Alcance

F4 demuestra que AgentProof se incorpora a otros frameworks sin tocar su núcleo (§5.7), y deja listo el agente de E4. Construye tres ediciones nuevas del agente del caso de estudio con sus adaptadores, recalibra en cada una lo que depende del framework, mide cuánto costó incorporar cada adaptador y mapea el esquema de trazas a las convenciones GenAI de OpenTelemetry (§5).

**Hito:** E4 ejecutable (edición LangGraph calibrada, piloto de LangGraph hecho, enmienda 2 con su tag `preregistro-v3`) y tabla de costo de incorporación de los cuatro adaptadores.

**Fuera de F4:** la ejecución de E4 (F5; E1 ya terminó); la edición sin framework, que queda como ítem opcional y se decide al terminar smolagents; el capítulo del prototipo completo (T3), del que F4 solo escribe la sección de portabilidad y el anexo de OpenTelemetry.

## 2. Lo que F4 no puede romper

| Restricción | Cómo se garantiza |
|---|---|
| Ninguna pieza de la huella de `preregistro-v2` cambia sin una enmienda | `tests/test_preregistration.py` ya falla si cambia. Las refactorizaciones de F4 conservan los valores que la huella resume |
| El núcleo (`agentproof` fuera de `adapters/`) no se modifica para acomodar un framework (§5.7) | La guarda de arquitectura existente, más la medición de la sección 8, que cuenta los archivos del núcleo que cambia cada adaptador; se espera cero |
| La edición Claude Agent SDK y lo que E1 usa quedan como están | Los datos de E1 en `results/` no se modifican. Los nombres que registran los manifiestos de E1 (`casestudy.editions.claude_sdk:build_options`) no cambian |
| Cada edición aplica la misma definición de las mutaciones (§5.8) | Prueba de paridad por edición (sección 4) |
| Ningún dato del agente sale a un servicio de terceros durante una corrida | Cada adaptador se niega a abrir una sesión si está activo el envío de trazas o la telemetría de su framework (sección 3) |
| Un framework nunca es dependencia de la herramienta base (invariante 7) | Extras opcionales `agentproof[langgraph]`, `agentproof[crewai]` y `agentproof[smolagents]`, cada uno en su propio commit `build:` |

## 3. Contrato común de las ediciones y los adaptadores

**Edición** (`casestudy/editions/<framework>.py`): una aplicación normal de su framework, que no sabe que la evalúan. Toma del dominio el prompt (`system_prompt(mutation)`), las herramientas como funciones puras, la política que devuelve la herramienta (`mutation.policy`), el modelo (`mutation.model`) y las mutaciones. Expone `VARIANTS` y una función que construye el agente nativo para una variante.

**Descripciones de las herramientas.** Hoy viven en la edición Claude Agent SDK (`_LOOKUP`, `_POLICY`, `_TICKET`). Pasan al dominio para que las cuatro ediciones usen el mismo texto, y la edición Claude Agent SDK conserva esos nombres como alias. La huella "Herramientas y límite de pasos de la edición Claude Agent SDK" resume sus valores, que no cambian, así que no es una enmienda.

**Adaptador** (`agentproof/adapters/<framework>.py`): cumple la convención `session_factory(agent, variant) -> SessionFactory` y solo traduce. Para cada turno devuelve un `AgentTurn` con:

- `reply`: el texto que ve el cliente;
- `events`: los mensajes del agente y una `tool_call` por llamada, con el nombre del dominio (`lookup_order`, `get_refund_policy`, `create_ticket`), sus argumentos (`order_id`, `summary`), su resultado y `is_error`. Las herramientas internas del framework, como `final_answer` de smolagents, no se registran como llamadas;
- `stop_reason`: `step_limit` cuando se alcanza el límite de pasos, `error` ante un error del modelo o del framework, y `completed` en otro caso. Alcanzar el límite nunca es un error (§5.4);
- `usage`: los tokens del turno. Como estos frameworks no reportan costo, el adaptador lo calcula con la tabla de precios fechada (`agentproof.pricing`) y deja `None` si el modelo no tiene precio.

**Aislamiento.** Cada conversación empieza con memoria vacía. El adaptador no abre la sesión si `LANGSMITH_TRACING` o `LANGCHAIN_TRACING_V2` están activos, ni si la telemetría de CrewAI no está desactivada. El mensaje de error dice qué variable cambiar.

**Paridad del modelo.** Todas las ediciones usan el modelo de la variante a través de la integración propia de su framework con Anthropic. Los parámetros que el framework no fija por omisión igual que el SDK (tokens máximos de salida, razonamiento extendido) se fijan de forma explícita y se registran en D-012. El nombre de la integración y su versión quedan en la traza mediante el campo `agent` y el lockfile.

## 4. Pruebas que cada edición debe pasar

Se escriben antes que cada edición. Corren sin la API, con un modelo falso del propio framework (`GenericFakeChatModel` de LangChain, un `Model` falso de smolagents, un `LLM` falso de CrewAI). Cada prueba nombra la regla que verifica:

1. **Herramientas.** Con la línea base, el agente tiene exactamente `lookup_order`, `get_refund_policy` y `create_ticket`, con las descripciones del dominio. Una llamada de `lookup_order` llega a la traza con `tool="lookup_order"`, `arguments={"order_id": ...}` y el resultado del dominio.
2. **Las seis mutaciones, con la misma definición.** D1 no tiene `lookup_order`. D2 y D5 reciben `system_prompt(mutation)`. D3 usa `TARGET_DOWNGRADED_MODEL`. D4 devuelve `policy_text(CORRUPT_POLICY)`. D6 usa el límite calibrado. La línea base usa 10 pasos. `tests/test_editions_mutations.py` pasa a recorrer las cuatro ediciones.
3. **Límite de pasos.** Un modelo falso que pide herramientas sin parar se corta en el límite. El turno sale con `stop_reason="step_limit"`, sin evento de error, y la conversación sigue en el turno siguiente.
4. **Historial válido después de un corte.** Toda llamada a herramienta del historial tiene su resultado antes del siguiente mensaje del cliente. Si no, la API de Anthropic rechaza el turno siguiente.
5. **Memoria entre turnos.** El segundo turno ve el primero; una conversación nueva no ve la anterior.
6. **Errores.** Una herramienta que falla queda como `is_error=True` y el agente sigue. Un error del modelo termina el turno con `stop_reason="error"`.
7. **Aislamiento.** La sesión se niega a abrir con el envío de trazas activo (sección 3).
8. **De punta a punta sin API.** `converse` con el usuario falso de `tests/fakes.py` produce una traza válida, y el oráculo lee sus eventos igual que los de Claude Agent SDK.

Las pruebas en vivo (`@pytest.mark.live`) repiten las de F3 para cada framework: el agente consulta el pedido real, D1 no lo consulta, D4 enuncia la ventana de 90 días y D6 se corta solo en la conversación de tres llamadas.

## 5. Ediciones

### 5.1 LangGraph (crítica, la usa E4)

- **El bucle completo sobre `StateGraph`**, sin el constructor prefabricado (plan maestro, §7). Tiene un estado con los mensajes (reducer `add_messages`), un contador de llamadas al modelo en el turno y una marca de corte; un nodo del modelo; un nodo de herramientas, y aristas condicionales.
- **Límite de pasos.** Un paso es una llamada al modelo, como en `max_turns` de Claude Agent SDK. El contador vuelve a cero al empezar cada turno del cliente. La arista que sale del nodo de herramientas va a `END` y deja la marca cuando la siguiente llamada superaría el límite. El adaptador lee la marca en el estado final y la traduce a `step_limit`. El corte ocurre siempre después del nodo de herramientas (prueba 4).
- **Memoria.** Checkpointer nativo (`InMemorySaver`) con un `thread_id` por conversación. El adaptador envía solo el mensaje nuevo y lee los mensajes añadidos en el turno.
- **Forma de la edición.** Expone una función que devuelve el `StateGraph` sin compilar para una variante. El adaptador lo compila con su checkpointer, y así la misma definición sirve también fuera de AgentProof.
- **Modelo.** `ChatAnthropic` de `langchain-anthropic`.

### 5.2 CrewAI (crítica)

- **Rol, objetivo e historia** del agente salen del prompt de sistema del dominio, sin reescribirlo. Las herramientas se envuelven con el mecanismo nativo de CrewAI.
- **Conversación de varios turnos.** Se usa `Agent.kickoff(messages=...)` con el historial completo. La alternativa es un `Crew` con una `Task` por turno. Se elige en D-013, después de leer el código de la versión fijada: cómo observar las llamadas a herramientas (eventos o el resultado del kickoff) y cómo reconocer que se alcanzó `max_iter`. Si `kickoff` no deja observar las herramientas, se usa la alternativa.
- **Límite de pasos:** `max_iter`. Al alcanzarlo, CrewAI fuerza una respuesta final. Esa respuesta cuenta como comunicada, y el turno queda como `step_limit`.

### 5.3 smolagents (crítica)

- `ToolCallingAgent` con las herramientas del dominio, el prompt en `instructions`, memoria con `run(..., reset=False)` y el límite en `max_steps`.
- **Límite de pasos.** Al agotar `max_steps`, smolagents hace una llamada más, sin herramientas, para forzar una respuesta final, y el resultado queda con `state="max_steps_error"`. El adaptador lo traduce a `step_limit`. Como en CrewAI, esa respuesta forzada cuenta como comunicada.
- **Respuesta y herramientas internas.** `final_answer` es la respuesta al cliente, no una llamada del dominio. smolagents antepone su propio prompt de ReAct al del dominio. Es el uso nativo del framework y se declara en D-012.
- **Modelo:** `LiteLLMModel` con el modelo de la variante.

## 6. Recalibración por framework

**D6** (adenda a [D-003](../decisiones.md)). Se repite en cada framework la sonda de D-003: un turno con tres casos que necesitan una, dos y tres llamadas, y límites de 2, 3 y 4. El límite de D6 de cada edición es el menor que completa los casos de una y dos llamadas y trunca el de tres. Si ningún valor reproduce ese patrón, se para y se decide. `Mutation.step_limit = 2` sigue siendo la definición compartida ("dos pasos"). La edición registra su equivalente calibrado junto a su límite de la línea base, sin cambiar la pieza "Mutaciones" de la huella.

**Oráculo** (adenda a [D-005](../decisiones.md)).

- **LangGraph.** Se repite el procedimiento de D-005 con un turno de la línea base y de cada mutación de la familia A (D1, D4 y D6) sobre las situaciones de los lotes de ajuste y de reserva de D-005. Las respuestas se etiquetan a ciegas antes de correr las reglas.
- **CrewAI y smolagents.** Se etiquetan a ciegas los mensajes de su corrida de punta a punta.
- **Si aparece una clasificación al revés o un falso positivo sistemático.** Se corrige con una regla general, como enmienda. Como las reglas son compartidas, E1 se vuelve a puntuar con ellas (el oráculo es determinista y no usa la API) y se reportan las dos puntuaciones. Como los resultados de E1 ya se conocen, la regla nueva tiene que justificarse solo con las respuestas de LangGraph, y la tesis lo declara. Si no aparece ninguna, las reglas no se tocan y se reporta la tasa de acierto por framework.

## 7. Corridas en vivo y enmienda 2

Las corridas en vivo se hacen de a una, nunca en paralelo con otra corrida, y cada una se confirma antes de lanzarla.

| Corrida | Diseño | Costo estimado |
|---|---|---|
| Sondas de D6 | 3 casos × 3 límites, un turno, por framework | ~USD 0.1 cada una |
| Calibración del oráculo en LangGraph | ~30 respuestas de un turno | ~USD 0.4 |
| Piloto de LangGraph | como el piloto de F3: tc-01, 04, 06, 09 y 15 × 2 repeticiones × `baseline-a` y `d4`, con juicio | ~USD 2.3 |
| Punta a punta de CrewAI y de smolagents | el mismo diseño del piloto, una vez por framework | ~USD 2.3 cada una |

Total ≈ USD 8, con un techo de USD 12. Se anota en el ROADMAP con la lectura de la consola.

**Enmienda 2 (`preregistro-v3`)**, antes de E4 y después del piloto de LangGraph:

- se agrega a la huella la fila "Herramientas, límites, modelo y versiones de la edición LangGraph", que resume las descripciones, el límite de la línea base, el de D6, los parámetros del modelo y las versiones fijadas de `langgraph` y `langchain-anthropic`;
- se declara en la §8 del pre-registro con su motivo (la §3 ya anticipa la recalibración de D6) y su efecto esperado;
- si la recalibración del oráculo cambió reglas, entra en la misma enmienda.

Ninguna pieza que usa E1 cambia salvo en ese último caso. CrewAI y smolagents no entran en la huella, porque no alimentan ningún experimento pre-registrado.

## 8. Costo de incorporación (§5.7)

`python -m experiments.portability` imprime, para cada uno de los cuatro adaptadores:

- las líneas de código del adaptador y de la edición, sin contar líneas en blanco, comentarios ni docstrings;
- las líneas de sus pruebas;
- los archivos del núcleo modificados por los commits de ese framework, contados desde su pull request (`git diff --name-only` contra el merge anterior, sobre `src/agentproof` fuera de `adapters/`).

La regla de conteo se fija en D-014 antes de medir. La tabla va a la tesis, a la sección de portabilidad, generada por el comando y no escrita a mano. Claude Agent SDK se mide con el mismo comando, como referencia.

## 9. Mapeo a OpenTelemetry (§5)

- Tabla de cada campo de `Trace` y `TraceEvent` a su atributo `gen_ai.*`, en `docs/` y en un anexo de la tesis: la conversación es `gen_ai.conversation.id`, cada turno es un span `invoke_agent`, cada `tool_call` es un span `execute_tool` con `gen_ai.tool.name` y sus argumentos y resultado, y el uso va en `gen_ai.usage.input_tokens` y `gen_ai.usage.output_tokens`. Lo que no tiene atributo estándar, como el motivo de terminación, la condición o la repetición, va con prefijo `agentproof.*`.
- `agentproof/otel.py`: una función pura que convierte una `Trace` en spans OTLP/JSON, sin depender del SDK de OpenTelemetry. Las pruebas la verifican contra la versión de la convención fijada en D-015: el commit de `open-telemetry/semantic-conventions-genai`, que todavía no publica versiones, y el estado de estabilidad de la convención.
- Es código nuevo del núcleo, no una modificación para un framework, así que no cuenta en la sección 8.

## 10. Decisiones nuevas

| Decisión | Contenido |
|---|---|
| D-012 | Equivalencias por edición: qué es un paso, la memoria, los parámetros del modelo y el prompt adicional de cada framework |
| D-013 | Conversación de varios turnos en CrewAI |
| D-014 | Regla de conteo del costo de incorporación |
| D-015 | Versión de las convenciones GenAI y mapeo del esquema |
| Adenda a D-003 | Límite de D6 calibrado en cada framework |
| Adenda a D-005 | Calibración del oráculo por framework |

## 11. Orden de construcción

Una rama y un pull request por parte, con merge commit. Así la medición de la sección 8 cuenta los commits de cada framework por separado.

1. **A. LangGraph.** Preparativos (descripciones al dominio, extra `langgraph`, prueba de ediciones generalizada), pruebas de la sección 4, edición, adaptador y D-012. Con la API: sonda de D6, calibración del oráculo, piloto y enmienda 2 con su tag.
2. **B. CrewAI.** D-013, pruebas, edición, adaptador; con la API, sonda de D6 y la corrida de punta a punta.
3. **C. smolagents.** Igual que B.
4. **D. Cierre.** OpenTelemetry (D-015, no usa la API y puede adelantarse), medición del costo de incorporación (D-014), sección de portabilidad y anexo de la tesis, ROADMAP e hito.

## 12. Ajuste al ROADMAP

Los ítems de F4 ya existen. Se agregan la enmienda 2 con su tag `preregistro-v3` y el piloto de LangGraph como parte del hito ("E4 ejecutable"), y se anota que el oráculo se recalibra completo en LangGraph y con la corrida de punta a punta en CrewAI y smolagents.
