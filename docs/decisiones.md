# Decisiones

Decisiones de diseño que no se deducen del código ni de la [planificación](planificacion.pdf), con su motivo y su estado. Cada una se registra cuando se toma, no cuando se implementa.

## D-001 · Repeticiones inválidas: cuándo se reintenta y cuándo no

- **Fecha:** 23 de septiembre de 2026
- **Estado:** decidida; se implementa en la parte D de F3
- **Origen:** retroalimentación del tutor sobre el primer entregable

### El problema

El diseño estadístico fija R = 5 repeticiones por par (escenario, condición). Una repetición puede terminar sin juicio por causas ajenas al agente evaluado: el usuario simulado falla, o el evaluador no devuelve un juicio válido. Hoy esa repetición se cuenta como inválida y el denominador baja. La planificación no dice qué hacer en ese caso.

Perder repeticiones degrada la detección de forma medible. En el caso extremo (todas aprueban en la línea base y ninguna en la candidata), con la prueba exacta de Fisher y el umbral de Benjamini-Hochberg sobre veinte escenarios:

| Repeticiones válidas | p | Consecuencia |
|---|---|---|
| 5 contra 5 | 0.0079 | detectable si está entre los cuatro escenarios más significativos |
| 5 contra 4 | 0.0079 | sin cambio |
| 4 contra 4 | 0.0286 | necesita estar entre los doce más significativos |
| 3 contra 3 | 0.1000 | nunca detectable |

### La regla

1. **Se reintenta** una repetición cuya traza termine en `simulator_error`, y una cuyo juicio falle después del reintento interno del evaluador. Son fallos de la instrumentación, no del sistema bajo prueba.
2. **No se reintenta** una repetición que termine en `user_ended`, `turn_budget`, `step_limit` o `agent_error`. Son comportamiento del agente evaluado y se juzgan como cualquier otra.
3. **Tope:** dos reintentos por repetición y cinco reintentos adicionales por par (escenario, condición).
4. **Si aun así faltan repeticiones válidas**, el par se analiza con las que tenga y el reporte lo marca. No se descarta el escenario ni se completa con repeticiones de otra condición.
5. **Se reporta cuántos reintentos necesitó cada condición.** Si una condición necesita bastantes más que las demás, eso es un hallazgo y no ruido: puede indicar que la degradación está provocando fallos del usuario simulado, es decir, un defecto del agente disfrazado de fallo de instrumentación.

La regla se pre-registra junto con el resto del protocolo, antes de ejecutar cualquier experimento.

### Cómo se reintenta cada fallo (16 de octubre de 2026)

La regla no decía si reintentar tras un juicio fallido significa repetir la conversación o volver a juzgar la misma traza. Se decide así:

- **Un fallo del usuario simulado repite la conversación.** Esa conversación es inválida: no muestra lo que el agente habría hecho con un cliente que siguiera hablando. El intento fallido se conserva, con su número de intento.
- **Un juicio fallido se resuelve volviendo a juzgar la misma traza, sin repetir la conversación.** Repetirla descartaría evidencia del comportamiento del agente. Si además el evaluador fallara más con las respuestas inusuales de una versión degradada, se descartarían justo esas conversaciones y la medición quedaría sesgada a favor de la versión degradada.
- **Los topes de la regla 3 se comparten entre las dos etapas:** dos reintentos por repetición y cinco por par, sumando los del usuario simulado y los del evaluador.
- **El oráculo cuenta la traza cuyo juicio falló definitivamente.** La verdad de referencia no puede depender de que el detector haya logrado juzgarla. Solo las conversaciones que invalidó el usuario simulado se excluyen de ambos lados, y el reporte marca el par con menos repeticiones juzgadas (regla 4).

### Por qué así

Reintentar mantiene el denominador en cinco y con ello la resolución de la prueba, que es la razón por la que se eligió R = 5. El tope evita que un fallo persistente deje una corrida sin terminar. Y la asimetría entre los dos tipos de fallo es lo que protege la validez: si se reintentara también un fallo atribuible al agente, se estaría borrando evidencia en contra de la versión evaluada.

## D-002 · Qué mensaje comunica el desenlace

- **Fecha:** 13 de octubre de 2026
- **Estado:** decidida; se implementa en el oráculo de F3 y se pre-registra
- **Origen:** diseño del oráculo de F3

### El problema

La §5.4 manda extraer el desenlace de la respuesta final y define el predicado de fallo sobre la decisión comunicada al usuario. En una conversación de varios turnos las dos cosas pueden no coincidir: el agente decide en un turno y el último mensaje es una despedida, o la respuesta a una pregunta de seguimiento que no repite la decisión. Tomar solo el último mensaje mandaría esos casos a anotación manual, o peor, los leería como si el agente no hubiera decidido nada.

Medido sobre las trazas disponibles al diseñar F3: la respuesta final contiene la decisión en las cuatro corridas con usuario simulado, que cierra la conversación sin mensaje de cortesía, y solo en dos de las cuatro conversaciones con personas.

### La regla

1. **La decisión comunicada** es la del mensaje más reciente del agente que enuncia una decisión. Los mensajes posteriores sin vocabulario de decisión, como una despedida, no la sustituyen; si el agente cambia de decisión, cuenta la última.
2. Si el mensaje más reciente con vocabulario de decisión es ambiguo o contradictorio, el caso pasa a **anotación manual**; no se adivina ni se retrocede a un mensaje anterior.
3. **Los atributos de pedido** (estado, fecha, importe) se revisan en todos los mensajes del agente: un dato que discrepa de la base de conocimiento es un resultado incorrecto comunicado al usuario aunque aparezca antes del último turno.

### Por qué no cambia lo que se mide

La regla precisa cómo se localiza el desenlace comunicado; no cambia qué cuenta como fallo, que sigue siendo un desenlace incorrecto respecto de una verdad fijada con independencia del sistema. Se pre-registra junto con el resto del protocolo, antes de ejecutar cualquier experimento.

## D-003 · Límite de pasos de D6 en Claude Agent SDK

- **Fecha:** 13 de octubre de 2026
- **Estado:** decidida e implementada
- **Origen:** calibración de las mutaciones de F3

La §5.4 define D6 como "el límite de pasos se reduce a dos" y su conjunto expuesto como los escenarios cuya traza semilla tiene tres o más llamadas a herramientas. "Paso" no significa lo mismo en cada framework, así que el valor se calibró midiendo qué alcanza a hacer el agente con cada límite, en un solo turno y con tres casos que necesitan una, dos y tres llamadas:

| Límite | Una llamada | Dos llamadas | Tres llamadas |
|---|---|---|---|
| 2 | completa | completa | se trunca |
| 3 | completa | completa | completa |
| 4 | completa | completa | completa |

Con 2, el agente consulta el pedido y la política en paralelo en el primer paso y responde en el segundo; cuando además debe crear un ticket, se queda sin pasos para responder. Eso es exactamente el conjunto expuesto de la §5.4, así que en esta edición D6 usa un límite de 2. La sonda costó USD 0.095. En F4 se repite la calibración en cada framework y se registra su valor.

## D-004 · Política corrupta de D4

- **Fecha:** 13 de octubre de 2026
- **Estado:** decidida e implementada
- **Origen:** calibración de las mutaciones de F3

D4 hace que la herramienta de política devuelva datos corruptos. Para que la mutación sea medible, la corrupción tiene que cambiar la decisión correcta en una parte de los escenarios, no en todos ni en ninguno. Calculado contra el catálogo para las quince tarjetas con decisión:

| Corrupción | Decisiones que cambia |
|---|---|
| Solo el umbral (500 → 100) | 1 |
| Solo las categorías excluidas (ninguna) | 2 |
| Solo la ventana (30 → 90 días) | 3 |
| Ventana de 90 días, umbral de USD 5000 y sin categorías excluidas | **7** |

Se adopta la última: cambia la decisión en tc-06, tc-07, tc-08, tc-11, tc-12, tc-13 y tc-15, y deja intactas las otras ocho, de modo que la mutación tiene dónde manifestarse y dónde no. Todas las corrupciones van en la misma dirección, hacia aprobar más, lo que la hace una política coherente y no ruido. Una prueba fija ese conjunto de siete tarjetas.

## D-005 · Calibración del oráculo con respuestas de agentes degradados

- **Fecha:** 16 de octubre de 2026
- **Estado:** decidida e implementada
- **Origen:** construcción del oráculo de F3

Hasta F3 las únicas respuestas grabadas eran del agente sano: 37 mensajes, todos escalamientos, aprobaciones o mensajes sin decisión. No había ningún ejemplo de cómo se expresa un agente degradado cuando se equivoca, y las reglas del oráculo se congelan en el pre-registro. Por eso se calibran antes, contra respuestas generadas para eso y no contra corridas del experimento.

**Procedimiento.** Un turno real de cada agente degradado con predicado (D1, D2, D4, D5 y D6) sobre situaciones de las tarjetas, en dos lotes:

| Lote | Respuestas | Situaciones | Uso |
|---|---|---|---|
| Ajuste | 17 | 10 | Se etiquetaron a mano y las reglas se corrigieron mirándolas |
| Reserva | 11 | 8 | Se etiquetaron a ciegas antes de correr las reglas |

Costo: USD 0.335 según el SDK. Las 28 respuestas y sus etiquetas quedan en `tests/fixtures/oracle_replies.json`, y una prueba exige que ninguna quede clasificada al revés.

**Resultados.**

- *Ajuste, primera pasada:* una inversión (una oferta condicionada, "con esa confirmación, escalo tu caso", leída como escalamiento) y dos fallas de extracción: las fechas en formato `27/08/2025` y el umbral de la política corrupta de D4 ("no supera los $5000") leído como importe del pedido. Se corrigieron con reglas generales: las ofertas sujetas a una condición pendiente son condicionales, se leen las fechas con barras y un importe que se compara es un umbral, no un atributo.
- *Reserva:* 11 de 11 decisiones y 11 de 11 predicados correctos, ninguno sin resolver. Hubo un falso positivo de estado ("mientras el pedido esté en preparación o en camino" leído como afirmación de que está en camino) que no cambió el predicado de su operador, D5, pero sí lo habría cambiado en D1. Se corrigió: una enumeración de estados o un supuesto con "mientras" no es una afirmación sobre el pedido.
- *Estado final:* 28 de 28 decisiones y predicados correctos, ninguno a la cola manual. Sobre los 37 mensajes del agente sano: 35 exactos, 2 omitidos y ninguno al revés.

**Limitaciones que se declaran.**

1. Ninguna respuesta degradada enunció un atributo falso: sin la herramienta de pedidos, D1 pidió los datos en lugar de inventarlos. Los casos positivos de discrepancia de atributos están probados solo con texto escrito para la prueba, y la regla de estados no tiene una medición independiente limpia, porque se corrigió con la reserva.
2. En los dos cortes de D6 que terminaron con texto, el agente ya había anunciado el escalamiento ("voy a escalar tu caso") antes de que el límite impidiera crear el ticket. Según la §5.4 cuenta la decisión comunicada, así que ahí el predicado no falla: D6 se manifiesta solo cuando el corte llega antes de que el agente enuncie el desenlace.

**Observación para el análisis.** En siete respuestas de D5 el agente no aprobó ningún reembolso que la política negara, y D2 siguió consultando la política. Son mutaciones de propensión: es esperable que su conjunto manifestado sea chico, y eso es un resultado, no un defecto del oráculo.

## D-006 · Lo que el criterio de regresión y las métricas dejan abierto

- **Fecha:** 16 de octubre de 2026
- **Estado:** decidida; se implementa en la parte C de F3 y se pre-registra
- **Origen:** construcción del criterio de regresión y de las métricas de F3

La §5.5 fija el criterio y las métricas, pero deja sin precisar seis detalles que cambian las cifras. Se fijan antes de escribir el código, porque se pre-registran con el resto del protocolo.

1. **Qué cuenta como detección.** Solo el estado *regresión*, que cumple las dos condiciones del criterio. La *señal débil* (caída de al menos 0.4 sin significancia) no es detección en la matriz de confusión: se reporta aparte, para que se vea cuántas regresiones quedan por debajo de la resolución que da R = 5.
2. **Prueba de Fisher de dos colas.** Con los márgenes de la tabla fijos, el valor p es la suma de las probabilidades de todas las tablas tan probables o menos que la observada. Es la definición estándar y reproduce los valores de la §5.5: 0.100, 0.029, 0.0079 y 0.0022 para R = 3, 4, 5 y 6. Se calcula con aritmética exacta, porque los límites de la corrección están muy cerca entre sí: 0.0079 queda entre 0.0075 y 0.01, que son los umbrales de tres y de cuatro escenarios.
3. **Familia de la corrección.** Benjamini-Hochberg se aplica, en cada comparación, sobre los escenarios comparados, que en el experimento son los veinte. Un escenario sin repeticiones válidas en alguna de las dos corridas no tiene valor p y no entra en la familia.
4. **pass^k.** Se usa el estimador insesgado por escenario, C(c, k) / C(n, k), con c repeticiones aprobadas de n válidas, promediado sobre los escenarios, para k de 1 a R.
5. **Tamaño de efecto.** Es la diferencia entre la tasa media de aprobación de la referencia y la del candidato. Para D3 se calcula sobre la suite completa, porque no tiene conjunto expuesto. Para la familia B se calcula sobre la suite y también sobre su conjunto expuesto. Siempre se acompaña de la distribución por escenario, para que una media no esconda de dónde viene el efecto.
6. **Escenarios incompletos.** La §5.5 pide que las cuatro celdas de la matriz particionen los veinte escenarios sin exclusiones. Un escenario sin repeticiones válidas en una de las corridas no puede etiquetarse. Si aparece uno, aun con los reintentos de D-001, no se le asigna celda ni se descarta en silencio: se lista como desvío del protocolo junto a la matriz.

## D-007 · Cómo se mide el costo y la latencia de cada componente

- **Fecha:** 16 de octubre de 2026
- **Estado:** decidida; se implementa en la parte D de F3 y se concilia en el piloto
- **Origen:** registro de costo y latencia por componente (§5.8, §7)

Hasta F2 solo el agente registraba su consumo: el inductor, el usuario simulado y el evaluador lo descartaban. Desde la parte D de F3:

1. **Qué se registra.** Cada componente guarda los tokens de entrada y de salida que informa la API y los segundos de cada llamada, incluidas las llamadas fallidas, que también se pagan. El inductor lo guarda en el escenario, el usuario simulado y el agente en la traza, y el evaluador en el veredicto.
2. **Cómo se pasa a dólares.** Con una tabla de precios por millón de tokens copiada de la página oficial de precios, con la fecha en que se verificó. Un modelo que no está en la tabla se reporta como tal, sin estimar su precio. Verificada el 16 de octubre de 2026, en USD por millón de tokens de entrada y de salida: Opus 5, 5 y 25; Sonnet 5, 2 y 10; Haiku 4.5, 1 y 5.
3. **El agente es un caso aparte.** Usa caché de prompts, que tiene tarifas propias, así que multiplicar sus tokens por la tabla no da su costo. Se reporta además la estimación que entrega su SDK.
4. **Las cifras de la herramienta son cálculos propios.** Al cerrar el piloto se concilian con la facturación de la consola de Anthropic, y la diferencia se informa. Así se registró en F1 y F2, cuando la consola marcó menos que la suma de las estimaciones del SDK.
5. **Los artefactos anteriores a este registro** se cuentan como "sin registro", nunca como costo cero.

**Verificación en vivo (16 de octubre de 2026).** Corrida de dos repeticiones sobre el escenario del hito de F1, interrumpida después de la primera traza.

- Con el proceso original todavía vivo, `resume` se negó a continuar. Tras matarlo de forma abrupta, tomó el control y completó la repetición que faltaba sin duplicar ninguna.
- Un primer intento, hecho antes de existir el candado de ejecución, dejó una repetición duplicada. La señal de interrupción no había detenido la corrida original. Eso motivó el candado.
- Costo de la corrida verificada, según la herramienta: USD 0.16 en total. El agente gastó 0.056 por conversación según su SDK, con 14 s medios; el usuario simulado, 0.003, con 3 s; el evaluador, 0.023 por juicio, con 6.5 s.
- Con ambos intentos, la verificación costó unos USD 0.32.
- Extrapolado a 0.08 por repetición, E1 (~800 conversaciones) costaría unos USD 65 y E4 (~400), unos 33. Es una cifra orientativa: sale de un solo escenario. El piloto dará la estimación que se use.
