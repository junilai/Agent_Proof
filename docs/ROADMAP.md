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

- [ ] Tarjetas de situación y matriz de cobertura de 20 tarjetas (§5.2)
- [ ] Grabación asociada a su tarjeta (§5.2)
- [ ] Protocolo de elicitación (§5.2)
- [ ] **Hito:** el autor graba 2–3 conversaciones semilla reales, cada una con su tarjeta

## Corpus — objetivo: 12–25 oct

- [ ] Sesiones con 4–6 participantes (§5.2)
- [ ] **Hito:** 20 conversaciones → 20 escenarios inducidos (§5.2)

## F3 Aparato experimental — objetivo: 12–31 oct

- [ ] Condiciones y corridas (§5.5)
- [ ] Mutaciones D1–D6 en el dominio (§5.4)
- [ ] Extracción del desenlace por reglas y cola de anotación manual a ciegas (§5.4)
- [ ] Conjuntos expuestos por operador (§5.4)
- [ ] Predicados de fallo y conjunto manifestado (§5.4)
- [ ] Criterio de regresión: Fisher + Benjamini-Hochberg + caída ≥ 0.4 (§5.5)
- [ ] Matriz de confusión, TPR, FPR y pass^k (§5.5, §5.8)
- [ ] Registro de costo y latencia por componente (§5.8), en tokens y en USD con la fecha de los precios, conciliado con la facturación de la consola de Anthropic; gasto total del proyecto, incluidos el desarrollo y la depuración, frente al presupuesto de USD 150–300 (§7). Línea base: USD 0.60 según la consola al cierre de F1 (22-sep-2026)
- [x] Revisión del prompt del inductor antes del pre-registro (§5.1), hecha el 23-sep-2026 en F2, antes de inducir el corpus: el mensaje inicial revela solo lo que el cliente dijo al abrir la conversación, para que la reejecución conserve los turnos de la semilla (en el hito de F1 adelantó el número de pedido), y los criterios exigen el desenlace, no la justificación del agente, para no inflar los falsos positivos de E3
- [ ] Pre-registro del protocolo (§5.5)
- [ ] **Hito:** tag `preregistro-v1` y piloto de 5 escenarios × 2 repeticiones × 2 condiciones (§7c)

## F4 Portabilidad — objetivo: 26 oct – 8 nov

- [ ] Edición LangGraph con el bucle sobre `StateGraph` y su adaptador (§5.7)
- [ ] Edición CrewAI y su adaptador, con una corrida de punta a punta (§5.7)
- [ ] Edición smolagents y su adaptador, con una corrida de punta a punta (§5.7)
- [ ] Medición del costo de incorporación por adaptador (§5.7)
- [ ] Mapeo del esquema a las convenciones GenAI de OpenTelemetry (§5)
- [ ] *(opcional)* Edición sin framework y su adaptador
- [ ] **Hito:** E4 ejecutable y tabla de costo de incorporación

## F5 E1 y E4 — objetivo: noviembre

- [ ] E1: ~800 conversaciones en el framework principal (§5.8)
- [ ] E4: ~400 conversaciones en LangGraph (§5.8)
- [ ] **Hito:** datos crudos en `results/`

## F6 E2 y E3 — objetivo: noviembre – diciembre

- [ ] Muestra estratificada de 40 pares con semilla registrada (§5.5)
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
- [ ] T2 Diseño experimental y pre-registro — oct
- [ ] T3 Desarrollo del prototipo — nov
- [ ] T4 Resultados y conclusiones; al final, introducción, resumen y abstract — nov – dic
  - [x] Borrador de la introducción, adelantado para el primer entregable del 27 de septiembre
- [ ] T5 Defensa, entrega, tag `entrega-final` y decisión sobre el historial del prototipo previo — dic
