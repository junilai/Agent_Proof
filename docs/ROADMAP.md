# ROADMAP de la tesis

Estado vivo del [plan maestro](specs/2026-09-21-plan-maestro.md). Cada ítem cita la sección de la [planificación](planificacion.pdf) que cumple y se marca como hecho en el mismo commit que lo completa. Las fechas son objetivos en el mejor caso; lo que no se mueve es el orden de dependencias descrito en el plan maestro.

**Leyenda:** `[x]` hecho · `[ ]` pendiente · *(opcional)* se recorta primero si falta tiempo · **Evidencia:** cómo se verificó un hito o una prueba en vivo (fecha, corrida de integración continua, costo).

## F0 Cimientos — objetivo: 21–23 sep

- [x] Planificación aprobada en `docs/planificacion.pdf` (§9)
- [x] ROADMAP de la tesis (este archivo)
- [x] Convenciones de trabajo en `docs/convenciones.md` (§5)
- [x] Licencia MIT (§9)
- [x] README del repositorio (§9)
- [x] Proyecto Python con uv, pytest y ruff (§5)
- [x] Prueba de invariantes de arquitectura del núcleo (§5.7)
- [x] Integración continua en GitHub Actions (§5)
- [x] **Hito:** integración continua en verde en GitHub. Evidencia: [corrida 35604536772](https://github.com/junilai/Agent_Proof/actions/runs/35604536772), 21-sep-2026

## F1 Esqueleto de punta a punta — objetivo: 23 sep – 4 oct

- [x] Especificación de la fase en `docs/specs/2026-09-21-f1-esqueleto.md`
- [x] Esquema de trazas neutral (§5.7)
- [x] Identificadores de modelo fijados en un único módulo (§5.6)
- [x] Protocolo de sesión (§5.7)
- [x] Persistencia de trazas, escenarios y veredictos
- [x] Separación entre trazas semilla y trazas de corrida
- [x] Motivo de terminación normalizado en la traza (§5.4)
- [x] Dominio del caso de estudio con política calculable (§5.4)
- [x] Edición Claude Agent SDK y su adaptador (§5.7)
- [x] Grabación interactiva de conversaciones
- [x] Inductor de escenarios con criterios sobre el desenlace (§5.1)
- [x] Usuario simulado con presupuesto de turnos y condición de parada (§5.1)
- [x] Runner con exactamente una traza por repetición (§5.1)
- [x] Evaluador ciego (§5.1)
- [x] Reporte con código de salida para integración continua (§3)
- [x] Verificación en vivo del inductor, el usuario simulado y el evaluador (§5.6). Evidencia: 4 pruebas `live` en verde contra la API, 21-sep-2026, costo USD 0.034
- [x] Verificación en vivo del agente aislado (§5.7). Evidencia: 4 pruebas `live` en verde en 3 corridas seguidas, 22-sep-2026, USD 0.025 por corrida; la prueba canario con control positivo confirma que el agente no lee un archivo de instrucciones de su carpeta de trabajo
- [x] **Hito:** corrida real de punta a punta (1 conversación → 1 escenario → 2 reejecuciones → juicios → reporte). Evidencia: [`evidence/f1-hito/`](../evidence/f1-hito/), 22-sep-2026. El autor grabó una conversación de 4 turnos sobre un monitor defectuoso entregado hace 90 días (reclamo de garantía, regla 4); el escenario inducido tiene 4 criterios; baseline-a y baseline-b con 2 repeticiones cada una, las 4 terminadas por el usuario simulado y con 4 de 4 criterios cumplidos; `report` salió con 0 (100 % → 100 %, sin regresiones). Tiempo automático ≈ 2 min (inducción 8 s, corridas 38 s y 40 s, juicios 14 s y 17 s). Costo del agente medido: USD 0.212 (semilla 0.068 + reejecuciones 0.144); el inductor, el usuario simulado y el juez aún no registran su consumo. El escenario de esta evidencia se indujo con el prompt anterior al ajuste del 23-sep-2026 y se conserva tal cual, porque documenta por qué se hizo ese ajuste

## F2 Listo para el corpus — objetivo: 5–11 oct

- [x] Tarjetas de situación y matriz de cobertura de 20 tarjetas (§5.2), con informe de cobertura para las sesiones
- [x] Grabación asociada a su tarjeta (§5.2)
- [x] [Protocolo de elicitación](protocolo-elicitacion.md) (§5.2), con consentimiento y sin datos personales
- [x] **Hito:** el autor graba 2–3 conversaciones semilla, cada una con su tarjeta. Evidencia: `corpus/seeds/`, 24-sep-2026. Tres conversaciones de 4, 5 y 6 turnos del cliente con las tarjetas tc-01 (procede), tc-13 (escalamiento por garantía) y tc-20 (sin decisión); en las tres el desenlace coincide con el resultado esperado de su tarjeta y ninguna terminó por error. Costo USD 0.199. Con solo tres conversaciones, los conjuntos expuesto y de control de D1, D4 y D6 ya son no vacíos

## Corpus — objetivo: 12–25 oct

- [x] Sesiones con 4–6 participantes (§5.2). Evidencia: `corpus/seeds/`, 17-oct-2026. Cinco participantes, contando al autor, grabaron 20 conversaciones, una por tarjeta, con la matriz de cobertura completa (D1 17 expuestas y 3 de control, D4 17 y 3, D6 11 y 9). Cuatro grabaciones quedaron apartadas en [`corpus/descartadas/`](../corpus/descartadas/) según [D-008](decisiones.md): tres en que la persona contó una situación distinta de la tarjeta y una que se cortó sin contenido. Para las regrabaciones se aclaró el texto de tc-05, tc-06 y tc-08, sin cambiar su resultado esperado
- [x] **Hito:** 20 conversaciones → 20 escenarios inducidos (§5.2). Evidencia: `corpus/scenarios/`, 17-oct-2026. Los 20 escenarios se revisaron contra su semilla, su tarjeta y la base de conocimiento antes del tag. La primera inducción tenía criterios que premiaban afirmaciones del agente sin respaldo, como un pago, un correo o un medio de pago, y la siguiente fijaba números de ticket. Se corrigieron las instrucciones del inductor y se volvió a inducir la suite completa ([D-008](decisiones.md)); la última inducción costó USD 0.52

## F3 Aparato experimental — objetivo: 12–31 oct

- [x] Condiciones y corridas (§5.5), con la regla de repeticiones inválidas de [D-001](decisiones.md):
  - Si el usuario simulado falla, la conversación se repite y el intento fallido se conserva con su número.
  - Si falla un juicio, se vuelve a juzgar la misma traza.
  - Los topes son compartidos entre las dos etapas.
  - El reporte informa los reintentos por corrida.
  - `agentproof resume --run <corrida>` retoma una corrida interrumpida sin repetir lo hecho.
- [x] Mutaciones D1–D6 en el dominio (§5.4), aplicadas por la edición Claude Agent SDK, con D6 y D4 calibrados ([D-003, D-004](decisiones.md)). Evidencia: 8 pruebas `live` en verde, 14-oct-2026, USD 0.078: D1 no consulta el pedido, D4 enuncia la ventana corrupta de 90 días, D6 trunca solo la conversación de tres llamadas y la línea base resuelve el reembolso como antes
- [x] Extracción del desenlace por reglas y cola de anotación manual a ciegas (§5.4), con la regla de [D-002](decisiones.md) y calibrada con respuestas reales de agentes degradados ([D-005](decisiones.md)): 28 de 28 respuestas bien clasificadas, ninguna al revés. Cola: `python -m experiments.oracle.annotation --data .`
- [x] Conjuntos expuestos por operador (§5.4), con una sola regla que comparte el informe de cobertura
- [x] Predicados de fallo y conjunto manifestado (§5.4), con el análisis de sensibilidad a 0.2, 0.4 y 0.6. El agente sano no dispara ningún predicado en las corridas del hito de F1 ni en el corpus
- [x] Criterio de regresión: Fisher + Benjamini-Hochberg + caída ≥ 0.4 (§5.5). El reporte tiene tres estados: regresión (sale con 2), señal débil y ok. Las pruebas fijan los valores p de la §5.5 y que, con R = 5, la corrección exige al menos cuatro escenarios regresando juntos. Decisiones abiertas fijadas en [D-006](decisiones.md)
- [x] Matriz de confusión, TPR, FPR y pass^k (§5.5, §5.8), con desglose de falsos positivos, sensibilidad, control negativo, distribución conjunta de fallos y tamaño de efecto. Se calculan solo sin casos pendientes de anotación. Los escenarios sin repeticiones válidas se listan como desvío, y los pares con menos repeticiones válidas que las previstas se marcan (D-001, regla 4). Comando: `python -m experiments.analysis --data . --reference <corrida> --control <corrida> --candidate <corrida> ...`
- [x] Registro de costo y latencia por componente (§5.8), en tokens y en USD con la fecha de los precios, conciliado con la facturación de la consola de Anthropic; gasto total del proyecto, incluidos el desarrollo y la depuración, frente al presupuesto de USD 150–300 (§7). Línea base: USD 0.60 según la consola al cierre de F1 (22-sep-2026) *Hecho en la parte D:* el inductor, el usuario simulado, el agente y el evaluador registran tokens y segundos, y `agentproof cost` los reporta con precios verificados el 16-oct-2026. *Conciliado* el 18-oct-2026 ([`docs/piloto.md`](piloto.md)): Opus coincide con el registro. El costo del agente que estima su SDK es unas 2.1 a 2.5 veces el facturado, probablemente por la caché de prompts, así que la tesis toma el costo del agente de la consola; y el Agent SDK gasta además ~USD 0.001 de Haiku por conversación que no se registra (corregido el 18-oct: la primera lectura de la consola estaba incompleta). Gasto total del proyecto según la consola hasta el 17-oct: USD 6.45.
- [x] Revisión del prompt del inductor antes del pre-registro (§5.1), hecha el 23-sep-2026 en F2, antes de inducir el corpus: el mensaje inicial revela solo lo que el cliente dijo al abrir la conversación, para que la reejecución conserve los turnos de la semilla (en el hito de F1 adelantó el número de pedido), y los criterios exigen el desenlace, no la justificación del agente, para no inflar los falsos positivos de E3
- [x] Pre-registro del protocolo (§5.5). Evidencia: tag `preregistro-v1` sobre `bc8d2b1`, 17-oct-2026. [`docs/preregistro.md`](preregistro.md) fija el diseño, la verdad de referencia, el criterio y las métricas. La huella de 14 piezas incluye las reglas del oráculo, el corpus semilla y los escenarios inducidos, y la comprueba `tests/test_preregistration.py`. La §9 la genera un comando. El oráculo se validó en dos muestras ciegas ([D-010](decisiones.md)), y su medición independiente final es una auditoría de 40 trazas de E1, fijada antes del tag
- [x] **Hito:** tag `preregistro-v1` y piloto de 5 escenarios × 2 repeticiones × 2 condiciones (§7c). Evidencia: [`docs/piloto.md`](piloto.md) y `evidence/piloto/`, 17-oct-2026. Las 20 conversaciones y los 20 juicios se completaron sin reintentos. El evaluador reprueba lo que D4 rompe, sin errores sistemáticos. Se encontró un error de aplicación en la regla de estados del oráculo, corregido con la enmienda 1 (`preregistro-v2`) antes de E1. Proyección de E1: USD 37–70 (corregida el 18-oct con la primera tanda), 6–7 h de máquina en serie. La contingencia de costo no se activa

## F4 Portabilidad — objetivo: 26 oct – 8 nov

- [ ] Edición LangGraph con el bucle sobre `StateGraph` y su adaptador (§5.7)
- [ ] Edición CrewAI y su adaptador, con una corrida de punta a punta (§5.7)
- [ ] Edición smolagents y su adaptador, con una corrida de punta a punta (§5.7)
- [ ] En cada framework, el adaptador traduce el corte por límite de pasos a `step_limit`; si no, D6 nunca se manifiesta. Se recalibran D6 ([D-003](decisiones.md)) y las reglas del oráculo, con respuestas de los agentes degradados de ese framework, como en [D-005](decisiones.md)
- [ ] Medición del costo de incorporación por adaptador (§5.7)
- [ ] Mapeo del esquema a las convenciones GenAI de OpenTelemetry (§5)
- [ ] *(opcional)* Edición sin framework y su adaptador
- [ ] **Hito:** E4 ejecutable y tabla de costo de incorporación

## F5 E1 y E4 — objetivo: noviembre

- [x] E1: ~800 conversaciones en el framework principal (§5.8). Evidencia: [`docs/e1.md`](e1.md) y `results/`, 18-oct-2026. Las 800 conversaciones y sus juicios, sin un solo reintento ni error del agente; 13 casos anotados a mano. USD 37.89 según la consola
- [ ] E4: ~400 conversaciones en LangGraph (§5.8)
- [ ] **Hito:** datos crudos en `results/`

## F6 E2 y E3 — objetivo: noviembre – diciembre

- [x] Muestra estratificada de 40 pares con semilla registrada (§5.5). Evidencia: `results/samples/e2.json`, 19-oct-2026, semilla `20261018`; 20 aprobados y 20 reprobados, con la contingencia activada (topes de tres por escenario y por versión, [D-011](decisiones.md)). Con el mismo comando, `python -m experiments.samples --data .`, se sortearon las 40 trazas de la auditoría del oráculo (`results/samples/auditoria.json`, semilla `20261021`, 3 con ticket y 2 sin ticket por condición)
- [x] Sorteo de los desacuerdos entre el oráculo y AgentProof en E1 ([D-016](decisiones.md)), agregado a pedido del tutor como análisis exploratorio. Evidencia: `results/samples/desacuerdos.json`, 21-oct-2026, semilla `20261022`: 18 desacuerdos, 17 con repeticiones discordantes en la línea base o la candidata y en cualquier dirección; 3 de origen en la agregación y 15 en las trazas; 23 celdas y 22 trazas para los anotadores
- [ ] Paquetes ciegos para los anotadores (§5.5)
- [ ] Fichas Likert de fidelidad (§5.8)
- [ ] Función opcional de revisión de escenarios y suite curada (§5.3)
- [ ] **Hito:** calificaciones de los tres anotadores recogidas

## F7 Análisis — objetivo: diciembre

- [ ] Métricas de detección, análisis de sensibilidad y efecto de D3 (§5.4, §5.5)
- [ ] κ de Fleiss, κ de Cohen y α de Krippendorff (§5.5, §5.8)
- [ ] Reporte de costo y latencia por componente (§5.8)
- [ ] **Hito:** todas las cifras, tablas y figuras de la tesis se regeneran con un solo comando

## Redacción

- [x] T0 Esqueleto con la plantilla USFQ y citas IEEE, compilado en la integración continua — sep. Evidencia: [corrida 35613059520](https://github.com/junilai/Agent_Proof/actions/runs/35613059520), 21-sep-2026
- [x] T1 Estado del arte (con réplica de la búsqueda en bases académicas) y descripción de la propuesta — sep – oct
  - [x] Capítulo de estado del arte, con sus referencias verificadas en la fuente (§4)
  - [x] Capítulo de descripción de la propuesta (§5.1, §5.6, §5.7)
  - [x] Réplica de la búsqueda en Scopus, IEEE Xplore y ACM Digital Library (§5, A2). Evidencia: 18 consultas el 22-sep-2026, 709 resultados, 256 revisados por título y resumen; ningún trabajo cubre la combinación completa y tres cubren eslabones aislados, ahora citados en la brecha
- [x] T2 Diseño experimental y pre-registro — oct. Capítulo 5 completo, con el corpus y la validación del oráculo (Tabla 4); 43 páginas al 17-oct-2026
  - [x] Borrador del capítulo, con sus seis secciones y las referencias de Benjamini-Hochberg, Fleiss y Hayes-Krippendorff verificadas en Crossref
  - [x] Cifras del corpus y conjuntos expuestos, al cerrar el corpus
- [ ] T3 Desarrollo del prototipo — nov
  - [x] Borrador del capítulo, adelantado para el segundo entregable del 25 de octubre: organización del código, núcleo, agente del caso de estudio, operadores de mutación, oráculo y pruebas. Falta la portabilidad, al cerrar F4
- [ ] T4 Resultados y conclusiones; al final, introducción, resumen y abstract — nov – dic
  - [x] Borrador de la introducción, adelantado para el primer entregable del 27 de septiembre
  - [x] Resultados preliminares de E1, para el segundo entregable: ejecución, detección por operador y lectura, sujetos a la auditoría del oráculo y a E2
- [ ] T5 Defensa, entrega, tag `entrega-final` y decisión sobre el historial del prototipo previo — dic
