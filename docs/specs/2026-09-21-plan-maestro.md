# Plan maestro de AgentProof

- **Autor:** Jarod Tierra Medina
- **Fecha:** 21 de septiembre de 2026
- **Estado:** aprobado
- **Fuente de verdad:** *Planificación para el Desarrollo del Proyecto Integrador* (aprobada por el tutor el 6 de septiembre de 2026). En este documento, "§" remite a sus secciones.

## 0. Propósito

La planificación define **qué** se construye y se demuestra. Este documento define **cómo** se lleva la tesis de 0 a 100 % dentro de este repositorio: la arquitectura del código, cómo se construyen los agentes del caso de estudio, las fases de trabajo, las reglas de verificación y de commits, y dónde viven la tesis escrita y la documentación. Si algo aquí contradice la planificación, prevalece la planificación, y cambiar un compromiso de la planificación requiere acordarlo con el tutor.

Existe un prototipo previo, construido entre julio y septiembre de 2026, que se usa como **base de conocimiento**: de él se toman las ideas que funcionaron y se evitan los defectos detectados al revisarlo (Sección 6). Su código no se copia en bloque; cada pieza se reconstruye aquí con pruebas y en commits pequeños.

## 1. Arquitectura del repositorio

```
Agent_Proof/
├── src/agentproof/        # 1. LA HERRAMIENTA: no conoce frameworks ni el caso de estudio
│   ├── schema, models, session, store
│   ├── induction, simulator, judge, runner
│   ├── report, stats      # criterio de regresión, pass^k, código de salida para CI
│   └── adapters/          # único lugar con imports de frameworks de agentes
├── src/casestudy/         # 2. EL AGENTE EVALUADO (tienda Andina Tech)
│   ├── domain/            # base de conocimiento, política calculable, herramientas,
│   │                      # prompt y mutaciones D1–D6, sin frameworks
│   └── editions/          # una aplicación nativa por framework
├── src/experiments/       # 3. EL APARATO EXPERIMENTAL
│   ├── oracle/            # conjuntos expuestos, extracción del desenlace, predicados de fallo
│   └── analysis/          # matriz de confusión, TPR/FPR, κ de Fleiss y de Cohen, α de Krippendorff
├── corpus/                # tarjetas de situación, matriz de cobertura, trazas semilla
├── results/               # datos crudos de los experimentos
├── thesis/                # documento escrito (plantilla USFQ)
└── docs/                  # plan maestro, ROADMAP, especificaciones, decisiones, convenciones
```

Las tres partes se mantienen separadas porque la planificación exige que sean independientes:

- **La herramienta** (`agentproof`) es lo que se publica como software de código abierto. Solo conoce el esquema de trazas neutral y el protocolo de sesión (§5.7).
- **El agente evaluado** (`casestudy`) es el objeto de estudio. Su dominio se escribe una sola vez y cada framework lo envuelve (Sección 2).
- **El aparato experimental** (`experiments`) establece la verdad de referencia. La §5.4 exige que esa verdad no dependa del sistema evaluado; tenerla en un paquete aparte lo hace visible en el propio código: el oráculo consulta la base de conocimiento del caso de estudio y nunca invoca al evaluador ni lee los criterios inducidos.

**Dirección de las dependencias.** `agentproof` no importa `casestudy` ni `experiments`. `casestudy` no importa nada de `agentproof`, con una única excepción: lee los identificadores de modelo del agente (línea base y D3) desde `agentproof.models`, porque la §5.6 exige que todos los identificadores estén centralizados en un único módulo. Leer esas constantes no introduce código de evaluación en el agente. `experiments` puede importar a los otros dos.

**Invariantes**, cada uno verificado por una prueba automática:

1. Ningún módulo del núcleo (`agentproof` fuera de `adapters/`) importa un framework de agentes (§5.7).
2. El evaluador nunca recibe la condición ni la versión del agente que califica (§5.1).
3. El oráculo nunca usa el evaluador automático ni los criterios inducidos (§5.4).
4. Cada repetición produce exactamente una traza, incluso cuando la conversación falla, y un fallo nunca detiene la suite.
5. Una ejecución se identifica por **condición** (`baseline-a`, `baseline-b`, `d1` … `d6`) y por **id de corrida**, no por una etiqueta de versión libre. Así el control negativo de línea base contra sí misma (§5.5) queda representado en los datos.
6. Los identificadores de modelo están fijados en `agentproof/models.py` y se registran con cada corrida (§5.6).
7. Los frameworks se instalan como dependencias opcionales (por ejemplo, `agentproof[langgraph]`); la herramienta base no los arrastra.

## 2. Agentes del caso de estudio

**Dominio compartido** (`casestudy/domain`, sin frameworks):

- La base de conocimiento controlada: pedidos con estado, fecha e importe, y el texto de la política de reembolsos.
- La **política calculable**: una función que, dado un pedido y su situación, devuelve uno de los tres desenlaces del vocabulario cerrado de la §5.4 (procede, no procede, escalamiento). El predicado de fallo de D2, D4 y D5 depende de ella.
- La lógica de cada herramienta como función Python pura (consulta de pedidos, política de reembolsos, creación de ticket).
- El prompt de sistema.
- Las **mutaciones D1–D6 como datos**: qué herramienta se elimina, qué salida se corrompe, qué límite de pasos se impone, cómo se recorta el prompt, qué instrucción se inyecta y qué modelo se usa. Cada edición aplica la misma definición, de modo que en el experimento E4 la única variable sea el framework (§5.8).

**Ediciones**: cada una es una aplicación normal de su framework, construida con sus piezas nativas:

| Edición | Paradigma (§5.7) | Qué se construye en ella | Prioridad |
|---|---|---|---|
| Claude Agent SDK | SDK nativo: bucle completo ya provisto | Herramientas MCP, prompt, límites, aplicación de las mutaciones | Crítica |
| LangGraph | Grafos | **El bucle completo sobre `StateGraph`**: estado, nodo del modelo, nodo de herramientas, transiciones, contador de pasos y motivo de terminación | Crítica |
| CrewAI | Roles | Rol, objetivo y tarea; conversión del modelo de tareas en una conversación de varios turnos | Crítica |
| smolagents | Tool-calling ligero | Herramientas, instrucciones, memoria entre turnos, límite de pasos | Crítica |
| Sin framework | Bucle propio | **Todo**, directamente sobre la API de mensajes de Anthropic | Opcional |

Principios:

- **El agente no sabe que lo evalúan.** Una edición puede ejecutarse sola, como cualquier aplicación de su framework. El adaptador de AgentProof la observa desde afuera (mensajes, callbacks o memoria del agente); la edición no incluye código de captura de trazas.
- Todas las ediciones usan el mismo modelo interno (§5.6) a través de la integración propia de cada framework.
- Las equivalencias que no son directas se documentan como decisiones explícitas en `docs/decisiones.md`: cómo una conversación de varios turnos se traduce al modelo de tareas de CrewAI, y cómo el límite de "dos pasos" de D6 se calibra en cada framework (`max_turns`, contador propio en LangGraph, `max_iter`, `max_steps`). En todas las ediciones, alcanzar el límite queda registrado como **motivo de terminación** en la traza y no como un error del programa, porque el predicado de fallo de D6 lo necesita (§5.4).

El conjunto cubre un espectro que va desde el bucle totalmente provisto por el SDK hasta el bucle escrito a mano, lo que refuerza el argumento de portabilidad de la §5.7.

## 3. Fases

Las fechas son **fechas objetivo en el mejor caso**; el cronograma real puede moverse. Lo que no se mueve es el **orden de dependencias** (más abajo).

| Fase | Contenido | Hito verificable | Fecha objetivo | Plan |
|---|---|---|---|---|
| **F0 Cimientos** | Estructura del repositorio, uv, ruff, pytest, integración continua, licencia MIT, ROADMAP, convenciones, planificación en `docs/` | Integración continua en verde en GitHub | 21–23 sep | §5, A3 |
| **F1 Esqueleto de punta a punta** | Esquema de trazas, protocolo de sesión, persistencia, dominio con política calculable, edición y adaptador de Claude Agent SDK, grabación interactiva, inductor (criterios sobre el desenlace), usuario simulado, runner, evaluador ciego y reporte con código de salida | Corrida real: 1 conversación grabada → 1 escenario inducido → reejecución × 2 → juicios → reporte | 23 sep – 4 oct | §5.1, §5.6, A3 |
| **F2 Listo para el corpus** | Tarjetas de situación y matriz de cobertura (20 tarjetas), grabación asociada a su tarjeta, separación entre trazas semilla y trazas de corrida, motivo de terminación normalizado, protocolo de elicitación | El autor graba 2–3 conversaciones semilla reales, cada una con su tarjeta | 5–11 oct | §5.2, A4 |
| **Corpus** | Sesiones con 4–6 participantes (actividad humana) | 20 conversaciones → 20 escenarios, con reemplazo de las que no sirvan | 12–25 oct | §5.2, A4 |
| **F3 Aparato experimental** (en paralelo con el corpus) | Condiciones y corridas; mutaciones D1–D6; extracción del desenlace por reglas y cola de anotación manual a ciegas; conjuntos expuestos; predicados de fallo; conjunto manifestado; prueba exacta de Fisher con Benjamini-Hochberg y caída ≥ 0.4; matriz de confusión; pass^k; costo y latencia por componente | **Pre-registro congelado con el tag `preregistro-v1`**, seguido del piloto (5 escenarios × 2 repeticiones × 2 condiciones) con costo y latencia reales | 12–31 oct | §5.3–5.5, §7c, A5 |
| **F4 Portabilidad** | Edición LangGraph con el bucle construido sobre `StateGraph` y su adaptador; después CrewAI y smolagents con una corrida de punta a punta cada uno; medición de líneas por adaptador y de archivos del núcleo modificados; mapeo del esquema a las convenciones GenAI de OpenTelemetry; edición sin framework (opcional) | E4 ejecutable; tabla de costo de incorporación por adaptador | 26 oct – 8 nov | §5.7, A3 |
| **F5 E1 y E4** | ~800 conversaciones en el framework principal y ~400 en LangGraph, con sus juicios | Datos crudos en `results/` | nov | §5.5, §5.8, A6 |
| **F6 E2 y E3** | Muestra estratificada de 40 pares con semilla registrada; paquetes ciegos para los anotadores; fichas Likert; función opcional de revisión de escenarios y suite curada | Calificaciones recogidas de los tres anotadores | nov – dic | §5.3, §5.5, §5.8, A7 |
| **F7 Análisis** | Matrices de confusión, TPR/FPR por familia, desglose de falsos positivos, sensibilidad con 0.2/0.4/0.6, distribución conjunta de tasas de fallo, efecto de D3, κ, α, costo y latencia | Todas las cifras, tablas y figuras de la tesis se regeneran con un solo comando | dic | §5.4, §5.5, §5.8, A8 |

**Redacción, en paralelo** (A9, A10):

| Tramo | Contenido | Fecha objetivo |
|---|---|---|
| **T0** | Esqueleto del documento con la plantilla USFQ y citas IEEE, compilado en la integración continua | sep |
| **T1** | Estado del arte (incluida la réplica de la búsqueda en bases académicas, A2) y descripción de la propuesta | sep – oct |
| **T2** | Diseño experimental y pre-registro | oct |
| **T3** | Desarrollo del prototipo | nov |
| **T4** | Resultados y conclusiones; al final, introducción, resumen y abstract | nov – dic |
| **T5** | Presentación para la defensa, entrega, tag `entrega-final` y decisión sobre publicar el historial del prototipo previo como evidencia de la §5.7 | dic |

**Dependencias rígidas:**

- F1 → F2: la grabación necesita el agente y el pipeline.
- F2 → Corpus: las sesiones necesitan la herramienta de grabación y las tarjetas.
- Corpus + F3 → tag `preregistro-v1` → piloto → F5: nada se ejecuta antes de que el protocolo esté congelado (§5.5).
- F4 (LangGraph) → E4 en F5.
- F5 → F6: la muestra de E2 se toma de ejecuciones ya evaluadas.
- F6 → F7 → T4.

**Qué se recorta primero si el tiempo se acorta:** (1) la edición sin framework, que es opcional; (2) las repeticiones de E4 bajan a tres, contingencia ya prevista en la §7c. E1, E2, E3 y el documento escrito no se recortan.

**Nivel de detalle.** Cada fase recibe su propia especificación en `docs/specs/` justo antes de empezarla, y a partir de ella se define su secuencia de commits. No se detallan ahora las fases tardías porque dependen de lo que muestren el corpus y el piloto.

## 4. Verificación y commits

**Un paso está hecho cuando:**

1. El comportamiento nuevo tiene su prueba, escrita antes que el código (§5: desarrollo guiado por pruebas), y `uv run pytest` pasa.
2. `ruff check` y `ruff format --check` no reportan problemas.
3. La integración continua está en verde en GitHub.
4. Si el paso invoca un modelo de lenguaje, además pasa su prueba en vivo (`@pytest.mark.live`). Esas pruebas se ejecutan de forma manual con la API key y no en la integración continua; la fecha y el costo de la verificación se anotan en el ROADMAP.
5. El ítem del ROADMAP que cumple cita la sección de la planificación y se marca como hecho en el mismo commit que lo completa.

**Commits:**

- Una idea por commit, con su código y sus pruebas juntos. Como guía, menos de ~300 líneas modificadas sin contar el lockfile; si algo crece más, se divide.
- Cada commit deja el repositorio funcionando. No hay commits "WIP" ni commits que arreglan el anterior.
- Las dependencias se agregan en commits `build:` separados.
- Formato `tipo(alcance): resumen`, con los tipos `feat`, `fix`, `test`, `refactor`, `docs`, `build`, `ci` y `thesis`. El cuerpo explica qué cambia y por qué, y cita la planificación (por ejemplo, `Plan: §5.4`).
- Idioma: código, identificadores y docstrings en inglés; commits, ROADMAP, documentación y tesis en español.

**Ramas, fases y tags:**

- Una rama por fase (`f0-cimientos`, `f1-esqueleto`, …). Al cerrar la fase se abre un pull request con el resumen y la lista de secciones de la planificación que cubre.
- Antes de integrar, el código de la fase se revisa y se contrasta con esas secciones.
- La integración se hace con merge commit, nunca con squash, para conservar cada commit pequeño y que la fase se vea como una unidad en el historial.
- Tags obligatorios: `preregistro-v1` (sello público del protocolo antes del piloto) y `entrega-final`.

## 5. Tesis y documentación

```
thesis/
├── main.tex            # preámbulo de la plantilla USFQ + \input de cada parte
├── preliminares/       # portada, hoja de calificación, derechos de autor, resumen, abstract
├── capitulos/          # 01-introduccion … 07-conclusiones
├── anexos/             # pre-registro, protocolo de elicitación y tarjetas, rúbricas, mapeo OpenTelemetry
├── figuras/  tablas/   # generadas por experiments/analysis, nunca a mano
└── bib/referencias.bib
```

- Se usa la plantilla oficial de la USFQ en LaTeX (XeLaTeX, biber y latexmk). Se eliminan sus cuatro páginas de instrucciones y se conserva su preámbulo, con un único cambio: el estilo bibliográfico pasa de APA a **IEEE** (`biblatex-ieee`), el mismo que usa la planificación.
- Un capítulo por archivo, para que cada uno avance en sus propios commits. Los capítulos siguen el sumario de contenidos de la planificación (§6).
- **Las cifras de los resultados no se escriben a mano.** El análisis genera `tablas/cifras.tex` con macros (por ejemplo, `\TPRfamiliaA`) que el texto utiliza, además de las tablas y figuras. Reejecutar el análisis actualiza el documento completo.
- La guía de la USFQ recomienda no superar las 30 páginas de cuerpo. Presupuesto inicial: introducción 3, estado del arte 5, propuesta 5, prototipo 4, diseño experimental 5, resultados 6, conclusiones 2. El detalle (pre-registro, protocolo de elicitación, rúbricas, tablas completas) va a los anexos.
- La integración continua compila el PDF cuando cambia `thesis/` y lo deja disponible como artefacto descargable.

**Documentación en `docs/`:**

| Archivo | Rol |
|---|---|
| `planificacion.pdf` | El documento de planificación aprobado, primer entregable (§9) |
| `specs/` | Este plan maestro y la especificación de cada fase |
| `ROADMAP.md` | Estado vivo del plan: ítems por fase, sección de la planificación, prioridad, fecha objetivo y evidencia de verificación |
| `decisiones.md` | Registro breve de decisiones de diseño con su justificación, útil como material para la tesis |
| `convenciones.md` | Las reglas de la Sección 4 |

## 6. Lecciones del prototipo previo

| Defecto detectado en el prototipo | Cómo lo evita este diseño |
|---|---|
| El inductor pedía criterios sobre la trayectoria (qué herramienta llamar), justo el tipo de contrato del que la planificación distingue a AgentProof | El inductor pide criterios sobre el desenlace comunicado al usuario; una prueba verifica el prompt |
| Cuatro copias del agente con prompt, herramientas y mutaciones duplicadas, que ya divergían (prompt de CrewAI, D6 en LangGraph) | Dominio único y mutaciones como datos (Sección 2) |
| D4 (política corrupta) no existía en ninguna edición | Una prueba verifica que cada edición aplica las seis mutaciones |
| La política de reembolsos era texto libre, sin un desenlace verdadero calculable | Política calculable con tres desenlaces |
| El inductor también tomaba como semillas las trazas de las corridas de regresión | Trazas semilla separadas de las trazas de corrida |
| Una conversación fallida producía dos trazas en la misma repetición | Invariante 4 con su prueba |
| Dos corridas de la misma versión no se distinguían | Condición + id de corrida (invariante 5) |
| El criterio de regresión era una caída > 0.5 | Fisher + Benjamini-Hochberg + caída ≥ 0.4 (§5.5) |
| No se registraba el motivo de terminación; en LangGraph el límite de pasos era una excepción | Motivo de terminación normalizado en la traza |
| Solo se medía el costo del agente de la edición Claude | Consumo y latencia por componente |
| La independencia del núcleo se comprobaba por inspección | Invariante 1 con su prueba en la integración continua |
| Nunca se ejecutó de punta a punta contra la API real y no tenía integración continua | Pruebas en vivo desde F1 e integración continua desde F0 |

## 7. Decisiones registradas

| Decisión | Resultado |
|---|---|
| Orden de construcción | Esqueleto de punta a punta primero y luego profundización por etapas |
| Idioma | Código en inglés; commits, documentación y tesis en español |
| Estilo de citas | IEEE |
| Licencia | MIT |
| Datos de participantes y anotadores | Se publican en el repositorio |
| Edición LangGraph | Bucle construido sobre `StateGraph`, sin el constructor prefabricado |
| Edición sin framework | Opcional; primera en recortarse |
| Historial del prototipo previo como evidencia de la §5.7 | Se decide en T5, antes de redactar los resultados |
