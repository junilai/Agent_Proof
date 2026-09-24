# F1 Esqueleto de punta a punta: especificación

- **Autor:** Jarod Tierra Medina
- **Fecha:** 21 de septiembre de 2026
- **Estado:** aprobado
- **Contexto:** fase F1 del [plan maestro](2026-09-21-plan-maestro.md). "§" remite a la [planificación](../planificacion.pdf).

## 1. Alcance

F1 construye la versión mínima pero completa del pipeline, con un solo framework (Claude Agent SDK): grabar una conversación, inducir su escenario, reejecutarlo con un usuario simulado, juzgar cada ejecución y comparar dos corridas con un código de salida apto para integración continua.

**Hito:** una conversación real grabada por el autor → un escenario inducido → dos corridas del **mismo** agente (`baseline-a` y `baseline-b`), con dos repeticiones cada una → cuatro juicios → reporte con código de salida 0. Es un control negativo en miniatura: al ser el mismo agente, no debe declararse regresión. Los datos del hito se guardan en `evidence/f1-hito/` y no en `corpus/`, porque el corpus de la §5.2 debe tener exactamente 20 conversaciones elicitadas. El costo real se anota en el ROADMAP.

**Fuera de F1:** mutaciones D1–D6 y condiciones del experimento (F3), tarjetas de situación y matriz de cobertura (F2), prueba de Fisher con Benjamini-Hochberg (F3), análisis de costo y latencia (F3), otros frameworks (F4).

## 2. Idioma

Todo el contenido que ven los modelos y las personas está en español: la conversación con el agente, la base de conocimiento, el texto de la política, los prompts del inductor, del usuario simulado y del juez, y los criterios inducidos. El motivo es metodológico: la §5.5 exige que los anotadores humanos usen una rúbrica idéntica a la del evaluador automático. El código y sus identificadores siguen en inglés.

## 3. Dominio del caso de estudio (`casestudy/domain`)

**La tienda.** Andina Tech, tienda en línea de electrónica. La fecha del dominio es fija: **1 de octubre de 2026**, y el agente la conoce por su prompt. Así las decisiones correctas no cambian según el día en que se ejecute un experimento.

**Los pedidos.** Entre 12 y 16 pedidos ficticios y fijos. Cada pedido tiene un solo producto y estos campos: identificador (`AT-1001`, …), cliente, producto, categoría, monto en dólares, estado (`en_preparacion`, `en_camino` o `entregado`), fecha de compra y fecha de entrega (solo si está entregado). No existe el estado "cancelado". Para que ningún caso quede en el borde de una regla, ningún pedido entregado tiene entre 27 y 33 días desde la entrega ni un monto entre $450 y $550.

**La política de reembolsos.** Se define por cuatro parámetros: ventana de reembolso de 30 días, umbral de supervisión de $500, garantía de 365 días y las categorías excluidas (tarjetas de regalo y software descargable). El motivo del cliente pertenece a un vocabulario cerrado: `defecto` (dañado o no funciona) o `arrepentimiento` (ya no lo quiere). La decisión pertenece al vocabulario cerrado de la §5.4 (`procede`, `no procede`, `escalamiento`) y se obtiene aplicando las reglas en este orden:

1. Pedido no entregado → **no procede**. No se cancela por este canal; el cliente puede solicitar el reembolso una vez entregado.
2. Categoría excluida → **no procede**, por cualquier motivo.
3. Entregado hace 30 días o menos: monto mayor a $500 → **escalamiento** (aprobación de un supervisor); en otro caso → **procede**, por cualquier motivo.
4. Entregado hace más de 30 días: motivo `defecto` y 365 días o menos → **escalamiento** (reclamo de garantía); en otro caso → **no procede**.

No hay reembolsos parciales ni crédito en tienda. Para cualquier combinación de pedido y motivo, la decisión es única.

**Una sola fuente de verdad.** Los cuatro parámetros generan a la vez el **texto de la política**, que el agente lee con su herramienta, y la **función de decisión** que usará el oráculo (§5.4). Ambos no pueden divergir, y D4 (F3) consistirá en alterar esos parámetros solo en la salida de la herramienta.

**Las herramientas del agente**, como funciones Python puras sin framework:

| Herramienta | Qué hace |
|---|---|
| `lookup_order(order_id)` | Devuelve los datos del pedido, incluidos los días transcurridos desde la entrega calculados con la fecha del dominio, o un error si no existe |
| `get_refund_policy()` | Devuelve el texto de la política |
| `create_ticket(summary, order_id)` | Registra un caso escalado. Solo se usa para escalar; un reembolso aprobado no genera ticket |

**El prompt del agente** indica la fecha del dominio y que debe consultar los datos del pedido y la política con sus herramientas antes de decidir. **No incluye el texto de la política**: si lo incluyera, corromper la herramienta en D4 no tendría efecto.

La base de conocimiento debe cubrir las seis ramas de la política (1, 2, 3a, 3b, 4a y 4b) con al menos un pedido cada una. Una prueba lo verifica.

## 4. Esquema de datos (`agentproof/schema`)

- **Evento de traza:** número de paso, tipo (`user_message`, `agent_message`, `tool_call`, `error`), nombre (de la herramienta, si aplica), entrada, salida y marca de tiempo.
- **Traza:** identificador; tipo (`seed` o `run`); adaptador, agente y variante; condición, id de corrida, escenario y número de repetición (solo en trazas de corrida); motivo de terminación; eventos; configuración de modelos vigente; consumo del agente; inicio y fin.
- **Escenario:** identificador `sc-<id de la semilla>`, semilla de origen, objetivo del usuario, mensaje inicial, entre 2 y 5 criterios de éxito, modelo inductor y fecha.
- **Juicio:** traza, escenario y corrida; por cada criterio, si se cumple y una justificación breve; aprobado (todos los criterios cumplidos); modelo evaluador y fecha.
- **Manifiesto de corrida:** id de corrida, condición, variante, adaptador, agente, repeticiones, presupuesto de turnos, configuración de modelos y fecha.

## 5. Componentes (`agentproof`)

| Módulo | Responsabilidad |
|---|---|
| `models` | Identificadores de modelo de la §5.6 y su configuración de llamada (esfuerzo de razonamiento), con una función que devuelve la configuración completa para registrarla |
| `session` | Contrato entre el núcleo y los adaptadores |
| `conversation` | `converse()` y los dos tipos de usuario |
| `transcript` | Transcripción ciega de una traza |
| `induction` | Inductor de escenarios |
| `simulator` | Usuario simulado |
| `judge` | Evaluador ciego |
| `store` | Lectura y escritura de corpus, corridas y evidencia en archivos JSON |
| `runner` | Ejecución de escenarios × repeticiones |
| `report` | Comparación de dos corridas |
| `cli` | Comandos `record`, `induce`, `run`, `judge` y `report` |
| `adapters/claude_sdk` | Traducción de los mensajes del SDK al contrato |

**Contrato con los adaptadores.** Una sesión es un contexto asíncrono con una sola operación, `send(message) -> AgentTurn`. Un `AgentTurn` contiene la respuesta visible para el usuario, los eventos del agente en ese turno (mensajes y llamadas a herramientas con su salida), un motivo de parada del turno (`completed`, `step_limit` o `error`) y, opcionalmente, el consumo de tokens y costo. El adaptador solo traduce: no numera pasos, no arma trazas ni guarda nada.

**`converse()`: el único lugar donde se arma una traza.** Grabar con una persona y reejecutar con el usuario simulado son el mismo bucle; solo cambia quién escribe. Ambos usuarios implementan `first_message()` y `next_message(historial)`, y este último devuelve `None` para terminar. `converse()` agrega los mensajes del usuario, numera los pasos, registra la configuración de modelos y determina el motivo de terminación de la conversación:

| Motivo | Cuándo |
|---|---|
| `user_ended` | El usuario terminó: la persona dejó una línea vacía o el usuario simulado dio el objetivo por resuelto |
| `turn_budget` | Se agotó el presupuesto de turnos del usuario simulado (10 por defecto) |
| `step_limit` | Un turno del agente agotó su límite de pasos. **Termina la conversación**, como supone el predicado de D6 (§5.4) |
| `agent_error` | El agente o su adaptador fallaron |
| `simulator_error` | Falló la llamada al usuario simulado |

Pase lo que pase, `converse()` devuelve **exactamente una traza** (invariante 4 del plan maestro). La **respuesta final** de una conversación, a la que se refieren los predicados de la §5.4, es la respuesta del último turno del agente.

**Transcripción ciega.** Es lo único que leen el inductor y el juez. Contiene los mensajes del usuario, los mensajes del agente, las llamadas a herramientas con su salida y los errores. **No contiene** nombres de modelo, condición, variante, id de corrida, agente ni marcas de tiempo. Sin esto, en D3 la transcripción revelaría el modelo degradado.

**Inductor** (Opus 5). Recibe la transcripción de una semilla y produce, con salida estructurada, el objetivo del usuario, un mensaje inicial (con la misma intención y solo lo que el cliente reveló al abrir la conversación, sin copiarlo literalmente; lo que dio después vive en el objetivo, de donde el usuario simulado lo toma cuando el agente pregunta) y entre 2 y 5 criterios de éxito. Los criterios describen **el desenlace comunicado al usuario** y deben poder verificarse desde una transcripción. No imponen qué herramienta usar ni en qué orden, porque la tesis distingue el escenario conversacional de un contrato sobre la trayectoria. Si la salida no es válida, se reintenta una vez; si vuelve a fallar, se informa el error. El inductor no induce dos veces la misma semilla.

**Usuario simulado** (Haiku 4.5). Conoce el objetivo del escenario y ve solo lo que ve un cliente: sus mensajes y las respuestas del agente, nunca las llamadas a herramientas. Escribe un mensaje breve por turno y responde exactamente `[FIN]` cuando el objetivo está resuelto o ya no puede resolverse. El primer mensaje es el mensaje inicial del escenario.

**Juez** (Opus 5). Recibe los criterios del escenario y la transcripción ciega, y devuelve por cada criterio si se cumple y una justificación breve. La rúbrica está en español y es el texto que recibirán los anotadores en E2 (§5.5). Una ejecución aprueba si cumple todos sus criterios. Si la respuesta no cubre exactamente todos los criterios, se reintenta una vez y, si vuelve a fallar, se registra un error de juicio: nunca se rellenan resultados. El juez no juzga dos veces la misma traza.

**Configuración de los modelos.** Los identificadores y el esfuerzo de razonamiento se fijan en `models` y se registran con cada traza y cada manifiesto. Opus 5 y Sonnet 5 no admiten fijar la temperatura; la variabilidad resultante es la que el diseño de la §5.5 absorbe con R = 5. No se activa el mecanismo de la API que reemplaza automáticamente un modelo por otro ante un rechazo: el instrumento de medición debe ser siempre el mismo modelo, y un rechazo se registra como error visible.

**Adaptador y edición Claude Agent SDK.** La edición expone `build_options(variant)`, que en F1 solo acepta `baseline` y rechaza cualquier otra variante. El agente usa el modelo de línea base de la §5.6, un límite de 10 pasos por turno y únicamente sus tres herramientas. Se ejecuta **sin cargar configuraciones ni archivos de instrucciones del sistema de archivos** y desde un directorio de trabajo neutro, para que nada ajeno al experimento llegue a su contexto. El adaptador traduce los mensajes del SDK en eventos, distingue un turno que agotó el límite de pasos (`step_limit`) de uno que falló (`error`) y reporta el consumo y el costo que informa el SDK.

## 6. Datos en disco

```
corpus/
├── seeds/<trace_id>.json          # conversaciones semilla
└── scenarios/sc-<seed_id>.json    # un escenario por semilla
results/runs/<run_id>/
├── manifest.json
├── traces/<trace_id>.json         # una traza por repetición
└── verdicts/<trace_id>.json       # un juicio por traza
evidence/f1-hito/                  # misma estructura, para el hito de F1
```

Todo es JSON legible, para que el corpus y los resultados publicados puedan revisarse en el repositorio. El id de corrida combina la condición y la fecha (por ejemplo, `baseline-a-20261002-153000`). Todos los comandos son idempotentes: repetirlos no duplica escenarios ni juicios.

## 7. Comandos

```bash
agentproof record --adapter claude_sdk --agent casestudy.editions.claude_sdk:build_options
agentproof induce
agentproof run --adapter claude_sdk --agent casestudy.editions.claude_sdk:build_options \
               --condition baseline-a --variant baseline --repetitions 2
agentproof judge --run <run_id>
agentproof report --baseline <run_a> --candidate <run_b>
```

Todos aceptan `--data <carpeta>` como raíz de los datos. El CLI importa el adaptador **por nombre** (`agentproof.adapters.<nombre>`) y la función del agente por su ruta, de modo que incorporar un framework no exige modificar el núcleo (§5.7).

## 8. Reporte

Por cada escenario presente en ambas corridas: repeticiones válidas, tasa de aprobación de cada corrida y diferencia. Un escenario es **regresión** si su tasa de aprobación cae **0.4 o más**, el mismo tamaño mínimo de efecto de la §5.5; F3 agrega la prueba de Fisher con Benjamini-Hochberg. Las tasas se calculan con fracciones exactas, para que una caída de 1.0 a 0.6 cuente como regresión sin errores de redondeo. Las repeticiones con `simulator_error` o con error de juicio se cuentan como inválidas y se informan. Código de salida: **0** sin regresiones, **2** con al menos una, **1** ante un error de uso o de datos.

## 9. Errores

| Situación | Resultado |
|---|---|
| El agente falla o agota su límite de pasos | Traza con `agent_error` o `step_limit`; **se juzga**, porque es un fallo del agente |
| Falla el usuario simulado | Traza con `simulator_error`; no se juzga y el reporte la cuenta como inválida |
| El inductor o el juez rechazan la petición o responden mal | Un reintento; si vuelve a fallar, error registrado e informado |
| Errores temporales de la API (429, 5xx) | Reintentos del propio SDK de Anthropic |
| Un escenario falla | La suite continúa |

## 10. Pruebas

**Sin conexión**, en la integración continua, con usuarios, sesiones y cliente de API falsos:

- Dominio: cada regla de la política; la cobertura de sus seis ramas; que ningún pedido esté cerca de un límite; que el texto y la función provengan de los mismos parámetros.
- `converse()`: cada motivo de terminación y exactamente una traza en todos los casos.
- Transcripción: sin modelo, condición, variante, corrida, agente ni marcas de tiempo, verificado con una traza de tipo D3.
- Inductor, usuario simulado y juez: contenido de los prompts, validación de la salida y reintento.
- Almacenamiento: idempotencia de escenarios y juicios.
- Reporte: 1.0 → 0.6 es regresión; 1.0 → 0.8 no lo es; repeticiones inválidas; códigos de salida.
- Adaptador: traducción de los mensajes del SDK, incluidos `step_limit` y `error`.
- Arquitectura: la guarda del núcleo se amplía para que `casestudy` solo pueda importar `agentproof.models`.

**En vivo**, marcadas `live`, excluidas por defecto y ejecutadas a mano con la API key (`uv run --env-file .env pytest -m live`):

- Un turno real con el agente: usa sus herramientas, conoce la fecha del dominio y no carga archivos de instrucciones.
- Una inducción real y un juicio real.
- El hito completo por el CLI.

## 11. Dependencias y empaquetado

- Núcleo: `anthropic`, `pydantic` y `typer`.
- `claude-agent-sdk` como dependencia opcional `agentproof[claude-sdk]`, incluida en el grupo de desarrollo.
- Los paquetes `agentproof`, `casestudy` y `experiments` se construyen desde `src/` con el mismo backend (`uv_build`).
- Cada dependencia se agrega en su propio commit `build:`.

## 12. Orden de construcción

Commits de 50 a 150 líneas, cada uno con sus pruebas:

1. Dependencias del núcleo y empaquetado de los tres paquetes.
2. Dominio: pedidos y fecha fija; política calculable; texto de la política; herramientas y prompt; guarda de arquitectura de `casestudy`.
3. Núcleo: esquema de trazas; escenarios, juicios y manifiestos; modelos y su configuración; contrato de sesión; `converse()`; transcripción ciega; almacenamiento.
4. Cognición: inductor; usuario simulado; juez.
5. Ejecución: runner; reporte.
6. Framework: dependencia opcional del SDK; adaptador; edición Claude Agent SDK.
7. Interfaz: comandos `record` e `induce`; comandos `run`, `judge` y `report`.
8. Verificación: pruebas en vivo; hito con su evidencia.

## 13. Ajuste al ROADMAP

Dos ítems de F2 pasan a F1 porque este diseño ya los incluye: la separación entre trazas semilla y trazas de corrida, y el motivo de terminación normalizado. F2 conserva las tarjetas de situación, la matriz de cobertura, la grabación asociada a su tarjeta y el protocolo de elicitación.
