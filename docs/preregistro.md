# Pre-registro del protocolo experimental

- **Autor:** Jarod Tierra Medina
- **Estado:** borrador. Se congela con el tag `preregistro-v1`, después de completar el corpus y antes de ejecutar cualquier experimento.
- **Fuentes:** la [planificación](planificacion.pdf) ("§"), la [especificación de F3](specs/2026-10-13-f3-aparato-experimental.md) y las [decisiones](decisiones.md) D-001 a D-008.

Este documento fija qué se mide en los experimentos E1 a E4, cómo se mide y con qué criterio se decide, antes de observar ningún resultado. Resume y remite a sus fuentes, sin repetir sus argumentos. La [sección 10](#10-huella-del-protocolo) contiene la huella de cada pieza congelada, y una prueba automática falla si el código deja de coincidir con ella.

## 1. Instrumentos

AgentProof tiene cuatro componentes basados en modelos de lenguaje. Sus modelos y su configuración quedan fijados en `src/agentproof/models.py` (§5.6) y se registran con cada traza y cada corrida.

| Componente | Modelo | Configuración |
|---|---|---|
| Inductor de escenarios | `claude-opus-5` | esfuerzo alto, hasta 16000 tokens de salida |
| Evaluador | `claude-opus-5` | esfuerzo alto, hasta 16000 tokens de salida |
| Usuario simulado | `claude-haiku-4-5-20251001` | hasta 1024 tokens de salida |
| Agente del caso de estudio (línea base) | `claude-sonnet-5` | límite de 10 pasos por turno |
| Agente degradado de D3 | `claude-haiku-4-5-20251001` | igual que la línea base |

Ningún componente tiene habilitado un cambio automático a otro modelo: el instrumento de medida es siempre el mismo.

**Prompts congelados.** Son las instrucciones del inductor (`INDUCTION_SYSTEM`), las del usuario simulado (`SIM_USER_SYSTEM`), la rúbrica del evaluador (`JUDGE_RUBRIC`) y el prompt de sistema del agente base (`casestudy.domain.prompt.SYSTEM_PROMPT`), con el que se grabó el corpus. La rúbrica del evaluador es el mismo texto que reciben los anotadores humanos de E2 (§5.5).

**Costo.** Cada componente registra sus tokens y sus segundos. Se valoran con los precios de la página oficial verificados el 16 de octubre de 2026 y se concilian con la consola de facturación ([D-007](decisiones.md)).

## 2. Diseño

**Unidad de análisis: el escenario** (§5.5). El corpus tiene 20 conversaciones de interacción elicitada, una por cada tarjeta de situación (§5.2, [protocolo de elicitación](protocolo-elicitacion.md)). De cada conversación se induce exactamente un escenario. Los 20 escenarios son las 20 hipótesis que se contrastan por operador, así que la corrección por comparaciones múltiples se aplica sobre 20. Si una conversación no permite inducir un escenario utilizable, se elicita otra con la misma tarjeta, sin reducir el conjunto ([D-008](decisiones.md), punto 5).

**Condiciones** (§5.4, §5.5). Hay ocho por framework:

- `baseline-a`, la referencia de todas las comparaciones;
- `baseline-b`, una segunda ejecución independiente del mismo agente, reservada al control negativo;
- las seis mutaciones, de `d1` a `d6` ([sección 3](#3-mutaciones)).

**Repeticiones y turnos.** R = 5 repeticiones por par (escenario, condición). Es un compromiso entre sensibilidad y costo, no el resultado de un análisis de potencia (§5.5). El presupuesto es de 10 turnos del usuario simulado por conversación.

**Volumen.**

- E1: 8 condiciones × 20 escenarios × 5 repeticiones = 800 conversaciones en Claude Agent SDK.
- E4: la línea base y las tres mutaciones de la familia A en LangGraph = 400 conversaciones.

Cada conversación recibe un juicio del evaluador.

**Repeticiones inválidas** ([D-001](decisiones.md)).

- Si el usuario simulado falla, se repite la conversación.
- Si falla un juicio, se vuelve a juzgar la misma traza.
- Los topes son dos reintentos por repetición y cinco por escenario, compartidos entre ambas etapas.
- Nunca se reintenta un fallo atribuible al agente.
- Si aun así faltan repeticiones, el par se analiza con las que tenga y el reporte lo marca.
- Se informa cuántos reintentos necesitó cada condición.

**Contingencia de costo** (§7c, [D-008](decisiones.md)). Antes de E1 se corre un piloto: `baseline-a` y `d4`, con 5 escenarios sorteados con la semilla `20261017` y 2 repeticiones. Sus datos no entran en el análisis. Si el costo proyectado de E1 y E4, más lo ya gastado, supera USD 300, E4 pasa a tres repeticiones; si aun así no alcanza, se informa al tutor antes de seguir.

## 3. Mutaciones

Cada operador es un dato que declara qué cambia (`src/casestudy/domain/mutations.py`), y cada edición del agente aplica la misma definición, de modo que entre frameworks la única variable sea el framework (§5.4, §5.8). Cada mutación cambia un solo aspecto de la línea base.

| Op. | Familia | Qué cambia | Valor |
|---|---|---|---|
| D1 | A | herramientas disponibles | sin `lookup_order`; el prompt la sigue nombrando |
| D4 | A | política que devuelve `get_refund_policy` | ventana de 90 días (verdadera: 30), umbral de supervisor de USD 5000 (verdadero: 500) y sin categorías excluidas |
| D6 | A | límite de pasos por turno | 2 (línea base: 10) |
| D2 | B | prompt de sistema | sin la instrucción de consultar la política antes de decidir |
| D5 | B | prompt de sistema | con una instrucción añadida: aprobar todo reembolso, sin excepciones |
| D3 | B | modelo del agente | `claude-haiku-4-5-20251001` en lugar de `claude-sonnet-5` |

**Calibraciones hechas antes del pre-registro.**

- **D6** ([D-003](decisiones.md)): con un límite de 2, el agente completa las conversaciones de una y dos llamadas a herramientas y trunca las de tres o más, que es como la §5.4 define su conjunto expuesto.
- **D4** ([D-004](decisiones.md)): la política corrupta cambia la decisión correcta en 7 de las 15 tarjetas con decisión (tc-06, 07, 08, 11, 12, 13 y 15) y deja intactas las otras ocho.
- **Cambio de framework:** el sentido de "paso" difiere entre frameworks, así que el límite de D6 se recalibra en cada uno y se registra.

## 4. Verdad de referencia

La verdad de referencia la establece un oráculo (`src/experiments/oracle/`). Usa solo tres fuentes fijadas antes de la ejecución y ajenas a AgentProof: la base de conocimiento del caso de estudio, la tarjeta de situación y los eventos de la traza (§5.4).

- **No usa el sistema evaluado.** Nunca usa el evaluador automático ni los escenarios inducidos, y no lee los veredictos ni el reporte. Dos pruebas de arquitectura lo verifican.
- **Cómo llega a la tarjeta.** De cada corrida llega a su traza semilla por el identificador del escenario, y de la semilla a su tarjeta.

**Conjunto expuesto.** Se calcula con una regla sobre información fijada antes de la inducción (§5.4):

| Op. | Expuesto cuando |
|---|---|
| D1 | la traza semilla llama a `lookup_order` |
| D4 | la traza semilla llama a `get_refund_policy` |
| D6 | la traza semilla tiene tres o más llamadas a herramientas |
| D2 | la tarjeta plantea una decisión de reembolso |
| D5 | la tarjeta espera que el reembolso no proceda |
| D3 | no define conjunto expuesto |

**Desenlace comunicado** ([D-002](decisiones.md)). Las reglas extraen la decisión dentro del vocabulario cerrado (procede, no procede o escalamiento) y los atributos del pedido que el agente enuncia (importe, fecha y estado).

- **Cuál decisión cuenta.** Es la del mensaje más reciente del agente que enuncia una decisión. Los mensajes posteriores sin vocabulario de decisión no la sustituyen.
- **Dónde se buscan los atributos.** Se revisan en todos los mensajes del agente y se contrastan con la base de conocimiento.
- **Lo que las reglas no resuelven no se adivina:** pasa a anotación manual.

**Predicados de fallo** (§5.4):

| Op. | Falla cuando |
|---|---|
| D1 | el agente enuncia un atributo del pedido que contradice la base, o, en una tarjeta de estado del pedido, no entrega el estado |
| D2, D4, D5 | la decisión comunicada difiere de la que la tarjeta declara de antemano según la política verdadera; en las tarjetas sin decisión el predicado es falso |
| D6 | la conversación terminó por el límite de pasos y no comunicó el desenlace que la tarjeta pedía |

**Calibración de las reglas** ([D-005](decisiones.md)). Antes del pre-registro se probaron con 28 respuestas de agentes degradados, generadas para eso y no tomadas del experimento. Un lote se usó para ajustar las reglas y otro, reservado, se etiquetó a ciegas. Al final, ninguna respuesta queda clasificada al revés. Se declaran dos limitaciones:

1. Las discrepancias de atributos solo se probaron con texto escrito para la prueba.
2. En D6, un corte que llega después de que el agente anunció el escalamiento cuenta como desenlace comunicado.

**Anotación manual a ciegas.**

- **Cómo se presentan los casos.** En orden aleatorio con la semilla `20261016`, junto con la situación, los datos del pedido en la base y la transcripción ciega. No se indica la condición ni el desenlace esperado.
- **Dónde se guardan.** En `results/oracle/annotations.json`, marcados como manuales, y se reportan en el recuento.
- **Ninguna métrica se calcula** mientras quede un caso pendiente.

**Qué trazas cuentan** ([D-001](decisiones.md)). Se excluyen las conversaciones que invalidó el usuario simulado. Se cuentan las trazas cuyo juicio falló definitivamente, porque la verdad no depende de que el detector haya podido juzgarlas.

**Conjunto manifestado** (§5.4). Se evalúa el predicado en las 5 repeticiones del candidato y en las 5 de `baseline-a`. Un escenario expuesto pertenece al conjunto manifestado cuando la tasa de fallo del candidato supera a la de la referencia en al menos 0.4. Es la única condición. El análisis de sensibilidad repite el cálculo con 0.2 y 0.6.

## 5. Criterio de regresión y métricas

**Criterio** (§5.5). Un escenario regresó si se cumplen dos condiciones:

- la prueba exacta de Fisher de dos colas entre la referencia y la candidata es significativa tras la corrección de Benjamini-Hochberg con α = 0.05 sobre los escenarios comparados;
- la tasa de aprobación cae al menos 0.4.

Los valores p se calculan con aritmética exacta ([D-006](decisiones.md)).

El reporte da a cada escenario uno de tres estados:

| Estado | Condición | Salida |
|---|---|---|
| regresión | las dos condiciones | 2 |
| señal débil | caída ≥ 0.4 sin significancia | 0 |
| ok | el resto | 0 |

**Resolución que impone R = 5.** Con veinte comparaciones, cuando k escenarios regresan juntos se declaran si su valor p es a lo sumo k × 0.0025. En el caso extremo, de 5/5 a 0/5, p = 0.0079. Por eso hacen falta al menos cuatro escenarios regresando juntos (umbral 0.01), porque con tres el umbral es 0.0075. Una regresión de un solo escenario nunca supera la corrección y se reporta como señal débil (§5.5).

**Matriz de confusión** (§5.5). Se calcula por operador sobre los veinte escenarios.

- **Positivo:** el escenario está en el conjunto manifestado del oráculo.
- **Negativo:** el resto, esté o no expuesto.
- **Detección:** solo el estado *regresión* cuenta como detección; la señal débil se lista aparte ([D-006](decisiones.md)).
- **Tasas:** TPR = VP / (VP + FN) y FPR = FP / (FP + VN).
- **Falsos positivos:** se desglosan entre no expuestos y expuestos sin regresión manifestada.
- **Desvíos:** un escenario sin repeticiones válidas en una de las corridas no recibe celda y se lista como desvío.

**Control negativo.** Se compara `baseline-a` con `baseline-b` con el mismo criterio. Todo escenario marcado es un falso positivo atribuible a la variabilidad del sistema.

**Otras medidas.**

- **Sensibilidad:** TPR y FPR con umbrales de manifestación de 0.2, 0.4 y 0.6.
- **Distribución conjunta** de las tasas de fallo de referencia y candidata por escenario y operador. Permite reconstruir cualquier otra clasificación.
- **Frecuencias de fallo** del candidato, de 0/5 a 5/5.
- **pass^k**, para k de 1 a 5, con el estimador insesgado por escenario, C(c, k) / C(n, k), promediado.

**Familias** (§5.4).

- **Familia A** (D1, D4 y D6): las métricas principales.
- **Familia B** (D2 y D5): se reporta aparte, con el tamaño de efecto sobre su conjunto expuesto y sobre la suite.
- **D3:** solo como tamaño de efecto sobre la suite completa, es decir, la diferencia entre las tasas medias de aprobación de la referencia y del candidato, acompañada de la distribución por escenario.

**Costo y latencia.** Se reportan por escenario evaluado y por componente en todos los experimentos (§5.8).

El comando `python -m experiments.analysis` calcula todo lo anterior y no calcula nada mientras haya casos pendientes de anotación.
