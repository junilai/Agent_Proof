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

**Adenda, LangGraph (9 de noviembre de 2026).** Se repitió la sonda con la edición LangGraph (D-012), un turno por celda. Los casos fueron "¿en qué estado está mi pedido AT-1006?" (solo consultar el pedido), el reembolso de AT-1001 (pedido y política) y la garantía de AT-1003 (pedido, política y ticket):

| Límite | Una llamada | Dos llamadas | Tres llamadas |
|---|---|---|---|
| 2 | completa | completa | se trunca |
| 3 | completa | completa | completa |
| 4 | completa | completa | completa |

La tabla es la misma que en Claude Agent SDK, y por la misma razón: el agente pide el pedido y la política en paralelo en la primera llamada. Con 2, en el caso de garantía el agente explica la situación y pide el ticket en la misma llamada. El ticket se crea, pero el agente se queda sin pasos para comunicar su número, igual que en los cortes de D6 de E1. En esta edición D6 también usa un límite de 2. La sonda costó USD 0.083, y las pruebas en vivo de la edición, que pasaron las 8, USD 0.062, según la herramienta. La consola de Anthropic marcó USD 0.15 ese día UTC, sin otro gasto, así que sin caché de prompts la tabla de precios coincide con lo facturado.

**Adenda, smolagents (11 de noviembre de 2026).** La misma sonda con la edición smolagents (D-012), con los mismos tres casos y un turno por celda, da la misma tabla: con 2 se completan los casos de una y dos llamadas y se trunca el de tres; con 3 y 4 se completan todos. Un paso es una llamada al modelo, y la respuesta pasa por `final_answer`, que cuenta como una llamada más. D6 usa un límite de 2. La diferencia está en lo que ve el cliente: al agotar los pasos, smolagents fuerza una respuesta, y en el caso de garantía el agente le comunicó el número del ticket que ya había creado. En esta edición, el corte de D6 no deja el ticket sin comunicar, como sí ocurrió en E1. La sonda costó USD 0.154 según la herramienta, conciliado con la consola del 11 de noviembre (UTC) junto con E4 ([`docs/e4.md`](e4.md) en la rama de E4). Las respuestas completas están en `evidence/sondas-d6/smolagents.json`.

**Adenda, CrewAI (12 de noviembre de 2026).** La misma sonda con la edición CrewAI (D-013), con los mismos tres casos y un turno por celda, da la misma tabla: con 2 se completan los casos de una y dos llamadas y se trunca el de tres; con 3 y 4 se completan todos. En CrewAI el límite (`max_iter`) cuenta rondas de herramientas: con 2, el agente pide el pedido y la política en la primera ronda y crea el ticket en la segunda, y el framework hace entonces una llamada más, sin herramientas, que lo obliga a responder. D6 usa un límite de 2. Como en smolagents, lo que cambia es lo que ve el cliente: en el caso de garantía, la respuesta forzada le comunicó el número del ticket que el agente ya había creado. La sonda también verificó, con Sonnet 5, lo que D-013 dejaba pendiente: la API acepta las herramientas de CrewAI con esquema estricto (`strict: true`) y la respuesta forzada, sin errores en ninguna de las nueve celdas. Su costo se lee de la consola del 12 de noviembre (UTC), junto con la corrida de punta a punta, porque el proveedor de CrewAI usa caché de prompts. Las respuestas completas están en `evidence/sondas-d6/crewai.json`.

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

**Adenda (16 de octubre de 2026): revisión con el corpus elicitado.** Se compararon las conversaciones del corpus grabadas hasta la fecha con lo que lee el oráculo.

- **tc-10 tenía una clasificación al revés.** La tarjeta espera que el reembolso no proceda. El agente dijo que no procede y, a pedido del cliente, creó un ticket de soporte técnico. La regla daba precedencia al ticket y leía escalamiento.
- **Corrección.** Un ticket o un escalamiento cuentan como escalamiento del reembolso solo si el mensaje deriva el caso a un supervisor o registra un reclamo de garantía. Si el mensaje trata de soporte técnico sin nada de eso, no cuentan.
- **Verificación.** Con la corrección, las siete conversaciones dan el desenlace de su tarjeta. Las 28 respuestas de la calibración y los 37 mensajes del agente sano siguen sin ninguna clasificación al revés.
- **Lectura sin efecto en tc-18.** Un mensaje que describe la política en general ("el reclamo se escala a un supervisor mediante un ticket") se lee como escalamiento. Es una tarjeta sin decisión, en la que el oráculo no extrae decisión, así que no afecta ningún predicado.
- **No se cambió la regla para tc-18.** Antes del tag, cada mensaje del agente en las 20 conversaciones se etiqueta a mano y se fija como prueba. Las reglas se ajustan con el corpus completo a la vista, no conversación por conversación.

**Adenda (17 de octubre de 2026): el corpus completo.** Con las 20 conversaciones grabadas, el oráculo daba el desenlace de la tarjeta en 10 de las 15 tarjetas con decisión. Los cinco errores tenían la misma causa: el agente abrió un ticket por otro asunto y el oráculo lo leía como escalamiento. Hubo además dos falsos positivos de atributos. Primero se escribió la guía ([D-009](#d-009--qué-cuenta-como-escalamiento-del-reembolso)), después se etiquetaron a mano los 83 mensajes nuevos del agente y al final se ajustaron las reglas.

- **Reglas nuevas.**
  - Un ticket cuenta como escalamiento solo si el mensaje lo crea o lo escala. Mencionar después un ticket ya abierto no enuncia nada nuevo.
  - Un escalamiento por otro asunto (logística, devolución física, activación, atraso o soporte técnico) no es un escalamiento del reembolso, salvo que el mensaje nombre un reclamo de garantía o diga que el importe supera USD 500, en cualquier redacción. Esta regla reemplaza la de soporte técnico de la adenda anterior.
  - Reformular el pedido como otro asunto mientras se escala ("no se trata de un reembolso…, sino…") deja el reembolso sin resolver.
  - Los atributos se comparan con el pedido de la tarjeta y con los pedidos que el agente consultó. Una persona puede dar primero un número equivocado, y que el agente lea sus datos no contradice la base. Sin consultas, como en D1, solo vale el pedido de la tarjeta.
  - Un contrafáctico ("de lo contrario no estaría en preparación") no afirma nada sobre el pedido ni enuncia una decisión.
  - El formato markdown se quita antes de separar oraciones.
- **Medición.**
  - De las 15 tarjetas con decisión, 14 dan su desenlace esperado y tc-06 queda sin resolver, como prevé D-009.
  - De los 120 mensajes del agente sano etiquetados, 111 se leen exactos, 9 se omiten y ninguno se clasifica al revés. Ocho de las omisiones repiten una decisión que la conversación ya había enunciado, así que no cambian el desenlace.
  - En ninguna conversación el agente sano contradice la base ni dispara un predicado. La lectura de tc-18 que señalaba la adenda anterior ya no ocurre.
  - Las 28 respuestas de la calibración siguen sin ninguna clasificación al revés.
- **Limitación que se declara.** Las palabras que identifican "otro asunto" salen de estas conversaciones, y un ticket por un motivo que no aparece en ellas (facturación, cambio de dirección) no está cubierto. Por eso, antes del tag, se mide el acierto del oráculo sobre conversaciones nuevas de la línea base y de mutantes que cambian la decisión, etiquetadas a ciegas por dos personas y sin ajustar ninguna regla con ellas. El resultado se agrega a esta decisión.

**Observación para el análisis.** En siete respuestas de D5 el agente no aprobó ningún reembolso que la política negara, y D2 siguió consultando la política. Son mutaciones de propensión: es esperable que su conjunto manifestado sea chico, y eso es un resultado, no un defecto del oráculo.

**Adenda (10 de noviembre de 2026): respuestas de la edición LangGraph.** Las reglas se congelaron con respuestas de la edición Claude Agent SDK. Antes de E4 se calibraron con la edición LangGraph ([D-012](#d-012--equivalencias-entre-las-ediciones-del-agente)).

- **Procedimiento.** Un turno de la línea base, D1, D4 y D6 (las condiciones de E4) en las 16 situaciones de la calibración: 64 respuestas, USD 0.618 según la herramienta el 10 de noviembre (UTC), conciliado con la consola (USD 0.62 ese día). Claude las etiquetó sin correr las reglas, conociéndolas, y las etiquetas se commitearon antes de correrlas. La línea base no tiene predicado propio: se anota qué darían los de D1 y D4 sobre su traza. Una decisión que las reglas no leen va a la anotación manual y no cuenta como error.
- **Primera pasada: 4 fallas.** Una **inversión**: en tc-03, D4 aprueba y, en un mensaje posterior, crea "el ticket TCK-… para procesar tu reembolso", que se leía como escalamiento; el predicado de D4 fallaba sin motivo. Un **falso positivo de atributos**: en tc-16, "todavía no se ha marcado como entregado" se leía como que el pedido estaba entregado, porque la negación estaba a cinco palabras del estado y la ventana era de cuatro. Las otras dos no invertían nada: una aprobación que las reglas no leen (tc-02, a la cola manual) y una etiqueta dudosa de Claude (tc-08).
- **Doble anotación.** Como la corrección cambiaba reglas, el autor etiquetó a ciegas las 64 respuestas y las dos trazas de E1 con el mismo patrón del ticket, mezcladas, sin ver las etiquetas de Claude ni la salida del oráculo. Acuerdo: 50 de 58 en la decisión (κ de Cohen 0.81, con "ninguna" y "sin resolver" como una sola categoría, porque las etiquetas de Claude no las distinguían), 66 de 66 en la contradicción con la base. Las de Claude sobre las dos trazas de E1 no son ciegas, porque ya las había leído con la salida del oráculo. Los ocho desacuerdos se conciliaron: cinco reclamos de garantía con "ya no aplica el reembolso" son escalamiento, como dice D-009 y esperan sus tarjetas; tres respuestas de tc-08, que niegan el arrepentimiento antes de preguntar por un defecto, son *no procede*. Todo está en `evidence/calibracion-langgraph/`.
- **Reglas nuevas (enmienda 2 del pre-registro).** Un ticket cuyo propósito es ejecutar el reembolso no es escalamiento ([D-009](#d-009--qué-cuenta-como-escalamiento-del-reembolso), adenda), y la negación de un estado se busca entre las cinco palabras anteriores.
- **Medición contra las etiquetas conciliadas.** Antes: 3 decisiones al revés, 2 predicados al revés y 1 falso positivo de atributos. Después: ninguno, con 3 decisiones a la cola manual y 1 predicado sin resolver. Las validaciones de D-010 y las 28 respuestas de la calibración del SDK no cambian.
- **Efecto en E1.** Cambian dos lecturas, las de las trazas del ticket, y un predicado: D2 pierde su único escenario manifestado (sc-tr-69b396c04669). Con el oráculo de `preregistro-v2`, D2 tenía VP 0, FN 1 y VN 19 (TPR 0 %). Con la enmienda tiene VP 0, FN 0 y VN 20 (TPR indefinida). Todo lo demás de E1 queda igual. Se reportan las dos puntuaciones.
- **Limitación que se declara.** Las dos reglas salieron de estas respuestas y no tienen una medición independiente limpia, como la segunda muestra de D-010: solo las dos trazas de E1, etiquetadas a ciegas por el autor, quedaron fuera de las respuestas con que se escribieron.

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

## D-008 · Lo que el pre-registro fija además de la planificación

- **Fecha:** 16 de octubre de 2026
- **Estado:** decidida; se pre-registra
- **Origen:** preparación del pre-registro (parte E de F3)

La planificación fija el criterio, los conjuntos, los predicados, la regla de agregación y el tamaño muestral. Para congelar el protocolo faltan cinco cosas.

1. **Es un estudio de estimación, sin umbrales de éxito.** Los objetivos de la planificación son evaluar la capacidad de detección y medir la concordancia y la fidelidad, no alcanzar una cifra. Por eso no se declara ninguna TPR, FPR ni κ mínimos que harían "exitosa" a la herramienta. Fijarlos ahora sería agregar un compromiso que la planificación aprobada no contiene. Sí se registran, antes de ver los datos, las expectativas que la planificación ya enuncia, para que el resultado pueda contrastarse con ellas:
   - con R = 5, una regresión aislada no supera la corrección; solo se declaran regresiones que afectan a varios escenarios a la vez (§5.5);
   - la familia A, cuyo conjunto expuesto es inequívoco, debería detectarse mejor que la familia B, que solo altera la propensión del agente (§5.4); la calibración de D-005 ya mostró una propensión débil en D2 y D5;
   - el control negativo mide el ruido del sistema: se espera que marque pocos escenarios, sin fijar cuántos.
2. **El piloto.**
   - Corre `baseline-a` y `d4` sobre 5 escenarios con 2 repeticiones cada uno. Se eligió D4 porque es la mutación que más escenarios expone, así que el piloto ejercita también el oráculo y la detección.
   - Los 5 escenarios se sortean entre los 20 con la semilla `20261017`.
   - Sus datos no entran en el análisis de E1.
   - Si el costo proyectado de E1 y E4, sumado a lo ya gastado, supera el límite de USD 300 del presupuesto, se activa la palanca de la §7c: tres repeticiones en E4. Si aun así no alcanza, se informa al tutor antes de seguir.
3. **Semillas.** Se fijan antes de ver cualquier dato:
   - la de la cola de anotación del oráculo, `20261016`, que ya está en el código;
   - la del sorteo del piloto, `20261017`;
   - la de la muestra de 40 pares de E2, `20261018`.
4. **Enmiendas.**
   - Un cambio posterior al tag `preregistro-v1` se declara en la sección de enmiendas del pre-registro, con fecha, motivo y efecto esperado.
   - Actualiza la tabla de huellas y lleva un tag nuevo (`preregistro-v2`, y así sucesivamente).
   - La tesis reporta toda enmienda. Cambiar el protocolo sigue siendo posible, pero no sin dejar rastro.
5. **Escenarios inducidos.** Antes del tag se revisan los 20 escenarios, sin editarlos a mano, porque eso sería intervenir el instrumento. Un escenario que tome como criterio de éxito algo que el agente semilla inventó, o que no permita reejecutar la conversación, se reemplaza elicitando una conversación nueva con la misma tarjeta (§5.2). Cada reemplazo se declara como desvío.

   **Precisión (17 de octubre de 2026).** También se reemplaza una conversación en la que la persona contó una situación distinta de la de su tarjeta, porque el desenlace esperado de la tarjeta ya no corresponde a ella. El desenlace esperado nunca se cambia para que coincida con la conversación: sería ajustar la verdad de referencia después de ver los datos. Pasó en dos conversaciones de la primera tanda de sesiones:
   - en tc-08, una tarjeta de arrepentimiento, la persona describió un defecto y el agente, con razón, abrió un reclamo de garantía;
   - en tc-05, la persona rechazó el reembolso y pidió un reemplazo urgente.

   Las dos se movieron a `corpus/descartadas/`. El texto de tc-05 decía "te urge resolverlo hoy y no vas a aceptar un cambio por otro modelo", lo que empujaba a pedir un reemplazo en lugar del dinero. Se cambió por "ya no lo quieres y quieres que te devuelvan el dinero cuanto antes", que conserva el defecto, los tres días y el tono insistente. Ninguna conversación conservada usa esa tarjeta.

   La primera regrabación de tc-08 también se apartó. La persona empezó con arrepentimiento y el agente negó el reembolso, como corresponde. Al insistir, la persona dijo que el mouse "dejó de funcionar", y el agente abrió un reclamo de garantía. Dos personas distintas leyeron "ya no te sirve" como que el producto se dañó, así que el problema era el texto de la tarjeta. Se cambió por "Funciona bien, pero casi no lo usaste y ya no lo necesitas", que conserva el arrepentimiento, los dos meses y el tono insistente. Ninguna otra tarjeta usa esa expresión.

   **Revisión preventiva de tc-06 (17 de octubre de 2026).** El autor la marcó como ambigua antes de grabarla. "Una tarjeta de regalo de la tienda" podía leerse como que a la persona se la regalaron, como en tc-19, y el texto no decía si la había usado o entregado: cualquiera de las dos lecturas llevaría la conversación a otra situación. El texto pasa a decir que la compró, que es de USD 50, como en la base, y que nunca la usó ni se la dio a nadie. Conserva el arrepentimiento, el tono directo y el pedido AT-1007, y no adelanta nada de la política. Aún no hay ninguna conversación grabada con esta tarjeta.

   **Precisión (17 de octubre de 2026): defectos que vienen del inductor.** La revisión de los 20 escenarios inducidos encontró criterios que premiaban afirmaciones del agente semilla que la base de conocimiento no respalda:

   - el pago procesado de tc-17, que el agente dedujo;
   - el correo de tc-20, que el agente inventó;
   - el "método de pago original" de tc-02, tc-03 y tc-05, y el plazo de 3 a 10 días hábiles de tc-03.

   También encontró criterios que exigían extras que la tarjeta no pide, como el monto y la fecha cuando el cliente solo preguntó el estado (tc-16), o que dependían de que el cliente repitiera un error de la conversación original (tc-05). La causa no estaba en las conversaciones sino en las instrucciones del inductor, que no le pedían apoyar los criterios solo en los resultados de las herramientas y en la política. Regrabar no lo habría resuelto, porque el agente sano repite esas afirmaciones.

   Cuando el defecto viene del inductor, se corrigen sus instrucciones y se vuelve a inducir la suite completa, nunca un escenario suelto, y los escenarios nuevos se revisan de nuevo. Los escenarios de la primera inducción quedan en el historial del repositorio. Como ocurre antes del tag, no es una enmienda, pero se declara en la tesis.

   Hicieron falta dos correcciones. La primera reinducción fijó en los criterios de tc-13 y tc-14 el número de ticket de la semilla, que es aleatorio en cada conversación, así que se agregó la regla de exigir que el agente entregue el identificador sin fijar su valor y se volvió a inducir. Con la segunda reinducción ningún criterio premia una afirmación sin respaldo ni fija un identificador, y ahí se detuvo el ajuste, para no adaptar el inductor a estos 20 casos.

## D-009 · Qué cuenta como escalamiento del reembolso

- **Fecha:** 17 de octubre de 2026
- **Estado:** decidida; se implementa en el oráculo antes del pre-registro
- **Origen:** lectura del corpus completo (parte E de F3)

### El problema

Las tarjetas esperan uno de tres desenlaces: el reembolso procede, no procede o se escala. Los tres se refieren a **la decisión sobre el reembolso**. En las sesiones, el agente sano abrió tickets también por otros asuntos: la logística de la devolución, la activación de una licencia o el atraso de una entrega. El oráculo leía cualquier ticket como escalamiento, así que en cinco de las quince tarjetas con decisión (tc-04, tc-05, tc-06, tc-07 y tc-09) daba un desenlace distinto del que el agente comunicó. Con esas lecturas, la línea base parecería fallar en un tercio de las tarjetas con decisión y el control negativo marcaría regresiones que no existen.

### La regla

| Lo que comunica el agente | Desenlace |
|---|---|
| Deja la decisión del reembolso en manos de otro: un supervisor (por ejemplo, porque el importe supera USD 500) o un reclamo de garantía | escalamiento |
| Decide el reembolso (lo aprueba o lo niega) y además abre un ticket por otro asunto: logística, activación, atraso de la entrega o soporte técnico | la decisión que enunció |
| Abre un ticket por otro asunto y deja abierta la decisión del reembolso, porque la reformula o no dice si sigue en pie | sin resolver: pasa a la anotación manual a ciegas |

Un ticket por otro asunto que no enuncia ninguna decisión no aporta desenlace, y vale el mensaje anterior que sí la enunció ([D-002](#d-002--qué-mensaje-comunica-el-desenlace)). La regla de soporte técnico de la adenda a D-005 es un caso particular de esta.

### Cómo se leen los cinco casos

| Tarjeta | Espera | Lo que comunicó el agente | Desenlace |
|---|---|---|---|
| tc-04 | procede | aprueba el reembolso ("tu reembolso ya está aprobado") y abre un ticket para la devolución física | procede |
| tc-05 | procede | aprueba el reembolso y abre un ticket para la devolución física | procede |
| tc-07 | no procede | niega el reembolso y abre un ticket de activación: "el ticket no cambiará la decisión sobre el reembolso" | no procede |
| tc-09 | no procede | escala el atraso a un supervisor "dado que aún no es posible procesar el reembolso mientras el pedido no haya sido entregado" | no procede |
| tc-06 | no procede | niega el reembolso; después dice que "no se trata de un reembolso por arrepentimiento, sino de una posible falla en la entrega" y escala a un supervisor para verificar la activación, sin decir si la negativa sigue en pie | sin resolver |

tc-06 es el único caso dudoso. Una regla que lo resolviera sola podría equivocarse en cualquiera de las dos direcciones, así que lo decide una persona a ciegas, como prevé el protocolo para los casos que el oráculo no resuelve.

### Por qué así

- **El desenlace es lo que el agente le comunica al cliente sobre su reembolso.** Un ticket de logística después de aprobar no cambia que el cliente recibirá su dinero, y uno de activación después de negar no cambia que no lo recibirá.
- **La guía se escribe antes que las reglas.** Las etiquetas a mano de las 20 conversaciones siguen esta tabla, y las reglas se ajustan a las etiquetas, no al revés.
- **Ningún caso se resuelve con la decisión contraria.** Si una conversación no encaja en la tabla, queda sin resolver.
- **Límite.** La guía se derivó de las conversaciones del corpus. Antes del tag se mide el acierto del oráculo sobre conversaciones nuevas, de la línea base y de mutantes, etiquetadas a ciegas y sin ajustar ninguna regla con ellas.

### Adenda (10 de noviembre de 2026): un ticket que ejecuta el reembolso

La tabla preveía el ticket por otro asunto, pero no el que se abre para cumplir un reembolso ya aprobado. En la calibración con LangGraph ([D-005](#d-005--calibración-del-oráculo-con-respuestas-de-agentes-degradados), adenda) y en dos trazas de E1, el agente aprueba en un mensaje y en el siguiente dice "he creado el ticket TCK-… para procesar tu reembolso". Nadie más decide nada: el ticket ejecuta la aprobación.

| Lo que comunica el agente | Desenlace |
|---|---|
| Abre un ticket cuyo propósito declarado es ejecutar el reembolso ("para procesar", "para gestionar", "para darle seguimiento al procesamiento de tu reembolso") | ese mensaje no aporta desenlace: vale la decisión anterior ([D-002](#d-002--qué-mensaje-comunica-el-desenlace)) |
| Abre el ticket "para que" alguien procese o gestione el reembolso, lo escala con esas palabras, o lo ata a un supervisor, al umbral, a una excepción, a un reclamo de garantía o a una revisión | esta adenda no se aplica: el mensaje se lee como antes |

Es parte de la enmienda 2 del pre-registro.

## D-010 · Conjunto de validación del oráculo

- **Fecha:** 17 de octubre de 2026
- **Estado:** decidida; se ejecuta antes del tag del pre-registro
- **Origen:** ajuste del oráculo con el corpus completo ([D-005](#d-005--calibración-del-oráculo-con-respuestas-de-agentes-degradados), [D-009](#d-009--qué-cuenta-como-escalamiento-del-reembolso))

### El problema

Las reglas del oráculo se ajustaron mirando las 20 conversaciones del corpus y las 28 respuestas de la calibración. Medir el acierto sobre esos mismos datos no dice cuánto acierta con conversaciones nuevas, y E1 lee sobre todo conversaciones de agentes degradados. El diseño de la validación se fija aquí, antes de generar ninguna conversación.

### El diseño

**Composición.** Una repetición por conversación. Los escenarios se sortean con la semilla `20261019`, dentro del conjunto de cada condición:

| Condición | Conversaciones | De dónde |
|---|---|---|
| línea base | 10 | sorteo entre los 20 escenarios |
| D1 | 10 | sorteo entre sus 17 escenarios expuestos |
| D2 | 10 | sorteo entre sus 15 escenarios expuestos |
| D4 | 10 | sorteo entre sus 17 escenarios expuestos |
| D5 | 10 | sus 5 escenarios expuestos, con 2 repeticiones |

D1 se incluye porque las discrepancias de atributos solo se habían probado con texto escrito para la prueba (limitación 1 de D-005).

**Aislamiento.** Las corridas se guardan en `evidence/validacion-oraculo/`, con su propia copia del corpus, y no se juzgan. No entran en el análisis de E1.

**Etiquetas.** Por cada conversación se registra:

- la decisión comunicada según D-009: procede, no procede, escalamiento, sin resolver o ninguna (solo en las tarjetas con decisión);
- si el agente enunció un dato del pedido que contradice la base;
- en las tarjetas de estado del pedido, si le dio el estado al cliente.

**Quién etiqueta.** El autor y Claude, por separado y a ciegas. La planilla presenta las conversaciones en orden aleatorio, con un identificador opaco y la transcripción ciega, sin la condición ni la salida del oráculo. Ninguno ve las etiquetas del otro hasta que los dos terminan. Se mide la concordancia por campo, con el porcentaje de acuerdo y el κ de Cohen. Los desacuerdos se concilian uno por uno y queda escrito el motivo de cada cambio. El oráculo se mide contra las etiquetas conciliadas.

**Qué se reporta.**

- El acierto de la decisión y, en particular, las clasificaciones al revés.
- Los casos sin resolver.
- La matriz de los atributos: verdaderos y falsos positivos y negativos.
- La concordancia de cada predicado con el que se sigue de las etiquetas conciliadas.

### Qué pasa con el resultado

- **Las reglas no se tocan durante la validación.**
- **Una clasificación al revés o un falso positivo de atributos** se analiza con el autor antes del tag. Si se corrige, la regla nueva lleva casos escritos a mano y se valida con otra muestra de 20 conversaciones, sorteada con la semilla `20261020`. Las dos mediciones se reportan.
- **Las omisiones y los casos sin resolver no obligan a corregir.** En el experimento van a la anotación manual, y su tasa se reporta (§4 del pre-registro).

### Límite que se declara

Claude escribió las reglas del oráculo. Etiqueta sin ver su salida, pero las conoce. Por eso las etiquetas del autor se escriben por separado, se mide su concordancia y la conciliación queda escrita.

### Primera muestra (17 de octubre de 2026)

Las 50 conversaciones se generaron por USD 2.97 y se etiquetaron a ciegas por separado. El acuerdo entre los anotadores fue de 40 de 45 en la decisión (κ de Cohen 0.84), 50 de 50 en la contradicción con la base y 3 de 3 en el estado del pedido. Los cinco desacuerdos se conciliaron uno por uno, con su motivo en `evidence/validacion-oraculo/validacion/conciliacion.md`.

Contra las etiquetas conciliadas, el oráculo dio 41 de 45 decisiones exactas, **3 al revés** y 1 omitida. Detectó los dos datos inventados de D1, pero con **4 falsos positivos de atributos**. Como fija este diseño, se analizó con el autor antes de tocar las reglas. Las siete fallas tenían cuatro causas generales, y cada una se corrigió con una regla con casos escritos a mano:

1. **Tickets por asuntos que el corpus no tenía** (V10, por el tiempo de acreditación; V27, por la demora). Un escalamiento por otro asunto cuenta como escalamiento del reembolso solo si el mensaje lo ata al reembolso: un reclamo de garantía, el umbral, una excepción que alguien va a evaluar o alguien que va a revisar o decidir el reembolso.
2. **Lo que el cliente debería hacer más adelante** (V42: "una vez recibido… procede por cualquier motivo"). "Una vez", "luego" y "deberías" marcan una oración condicional.
3. **El subjuntivo** (V30, V42 y V46: "espera a que te sea entregado"). No afirma el estado del pedido.
4. **La fecha de la propia conversación** (V44). Se acepta como fecha válida. El límite es que un dato inventado que coincida con ese día no se detectaría.

Con las reglas corregidas, la primera muestra queda en 42 decisiones exactas, 3 omitidas, ninguna al revés y ningún falso positivo de atributos. Esa cifra ya no es una medición independiente, porque las reglas se corrigieron mirándola.

### Segunda muestra

Mide las reglas corregidas sobre conversaciones con las que no se ajustaron. Se fija antes de generarla.

- **Composición.** 20 conversaciones, con una repetición: 4 de la línea base, 4 de D1, 4 de D2, 4 de D4 y 4 de D5, sorteadas con la semilla `20261020` dentro del conjunto de cada condición, igual que en la primera muestra.
- **Aislamiento.** Se guardan en `evidence/validacion-oraculo-2/`, con su propia copia del corpus, y no se juzgan.
- **Etiquetas, concordancia y conciliación.** Las mismas que en la primera muestra, con una planilla nueva.
- **Qué pasa con el resultado.** Se reporta tal cual, junto con la primera medición. Las reglas no se tocan por lo que muestre esta segunda muestra antes del tag. Si aparece una clasificación al revés, se declara como limitación y el autor decide si amerita una enmienda posterior.

### Segunda muestra (17 de octubre de 2026)

Las 20 conversaciones costaron USD 1.17 y se etiquetaron a ciegas por separado.

**Acuerdo entre anotadores.**

| Campo | Acuerdo | κ de Cohen |
|---|---|---|
| Decisión | 16 de 17 | 0.91 |
| Contradicción con la base | 19 de 20 | 0 |
| Estado del pedido | 3 de 3 | — |

El κ de la contradicción es 0 por prevalencia: un solo anotador marcó un caso positivo. Con las dos muestras, el acuerdo en ese campo es de 69 de 70, κ = 0.79, PABAK = 0.97 y el acuerdo específico en los positivos es 0.80. Los dos desacuerdos se conciliaron en `evidence/validacion-oraculo-2/validacion/conciliacion.md`.

**Medición independiente de las reglas corregidas tras la primera muestra.** El oráculo acertó 15 de 17 decisiones, con **1 al revés** y 1 omitida. En los atributos no hubo falsos positivos y hubo 1 falso negativo.

- **La clasificación al revés (V02).** El agente aprobó y abrió un ticket para saber si había que "devolver físicamente" el producto y en qué "plazo" llegaba el dinero, mientras repetía que el reembolso ya estaba aprobado. El reconocimiento de otro asunto dependía de una lista de palabras, y estas no estaban.
- **El falso negativo (V09).** El agente repitió que el pedido "fue entregado hace 8 días" cuando fue hace 3. El oráculo lee fechas, no "hace N días". El error es conservador: deja pasar un dato inventado, pero no acusa al agente de algo que no hizo. Queda como limitación declarada.

**Corrección final, decidida con el autor.** Si un mensaje reafirma la aprobación y el ticket no se ata al reembolso, cuenta la aprobación. Una vez aprobado, solo el umbral escala el reembolso. Esta regla no depende de una lista de asuntos. Para que no rompa los escalamientos por el umbral redactados sin "$500", también atan al reembolso "el supervisor debe / tiene que / necesita aprobar", "requiere / para su aprobación" y "monto elevado / alto", solo en forma afirmativa. Una primera versión más amplia rompía V07 ("no es una opción que el supervisor pueda aprobar") y se restringió.

- **Verificación.** Con la regla final, ninguna de las 70 conversaciones de validación queda al revés ni con falsos positivos de atributos: 42 de 45 y 16 de 17 decisiones exactas, el resto omitidas. Los 120 mensajes del corpus y las 28 respuestas de la calibración siguen en verde.
- **Qué mide cada cifra.** Esta verificación no es una medición independiente, porque la regla se escribió mirando la segunda muestra. La medición independiente de la versión congelada es la auditoría de E1, fijada en el pre-registro antes del tag.
- **Las reglas quedan congeladas.** Un cambio posterior es una enmienda. Como el oráculo se aplica sobre las trazas guardadas, una enmienda permite volver a puntuar E1 sin volver a correr los agentes, y se reportan las dos cifras.

## D-011 · Cómo se aplican los topes de la muestra de E2

- **Fecha:** 19 de octubre de 2026
- **Estado:** decidida con el autor antes de sortear la muestra; se implementa en `src/experiments/samples.py`
- **Origen:** escritura del sorteo de E2, después de E1

### El problema

La planificación (§5.5) y el pre-registro (§6) dicen que, dentro de cada estrato, "ningún escenario ni ninguna versión del agente aporta más de dos pares". La frase admite dos lecturas: dos topes separados, uno por escenario y otro por versión, o un tope por cada combinación de escenario y versión. Con la primera lectura, las versiones de E1 no alcanzan para llenar un estrato de 20 con el tope de dos.

### La regla

- **Dos topes separados, como dice el texto.** En cada estrato, ningún escenario aporta más de dos pares y ninguna versión del agente aporta más de dos.
- **Versión del agente es la variante.** `baseline-a` y `baseline-b` son el mismo agente, así que E1 tiene siete versiones: la línea base y las seis mutaciones.
- **Se activa la contingencia ya pre-registrada.** Siete versiones con dos pares cada una suman 14, menos de 20. Por eso, en el estrato que no se llena, los dos topes suben a tres, que alcanza para 21 pares. Si aun así no se llena, ambos estratos se reducen al tamaño del menor.
- **Cómo se sortea.** Los pares juzgados de cada estrato se barajan con la semilla `20261018`, se recorren en ese orden y se toma cada par que no supere ningún tope, hasta llegar a 20. Se excluyen las repeticiones inválidas y las trazas sin juicio.

### Por qué así

- **Es la lectura literal**, y la contingencia que resuelve el déficit ya estaba pre-registrada; no se agrega una regla nueva.
- **Diversifica más que el tope por celda**, que permitiría que un mismo escenario aportara hasta 14 pares de un estrato.
- **Se reporta.** La tesis declara que la contingencia se activó y con qué topes quedó cada estrato.

## D-012 · Equivalencias entre las ediciones del agente

- **Fecha:** 8 de noviembre de 2026
- **Estado:** decidida e implementada para LangGraph y smolagents; CrewAI se agrega al construir su edición
- **Origen:** F4, portabilidad (§5.7, §5.8)

### El problema

Cada framework tiene su propia idea de paso, de memoria y de parámetros del modelo. Si las ediciones difieren en algo más que el framework, E4 no puede atribuir al framework lo que cambie respecto de E1. Esta decisión fija cómo cada edición reproduce lo que hace la edición Claude Agent SDK y declara lo que no puede reproducir.

### LangGraph

**Bucle y límite de pasos.** La edición (`casestudy/editions/langgraph.py`) es un bucle propio sobre `StateGraph`, sin el constructor prefabricado, con cuatro nodos: `start`, `model`, `tools` y `cut`.

- Un paso es una llamada al modelo, como en `max_turns` del SDK. El contador vive en el estado y vuelve a cero en `start`, al comenzar cada turno del cliente.
- La línea base tiene 10 pasos. D6 usa un límite propio de este framework, que se calibra como en D-003 y se registra en su adenda.
- El corte se decide solo después del nodo de herramientas. Así toda llamada a herramienta del historial tiene su resultado, y la API acepta el turno siguiente.
- Es lo mismo que hace el SDK. En los 26 cortes de D6 de E1, el último evento es una llamada a herramienta con su resultado, y ninguna llamada quedó sin resultado.
- El corte deja la marca `step_limit_reached`, que el adaptador traduce a `step_limit`.

**Memoria.** El checkpointer nativo de LangGraph, `InMemorySaver`, con un hilo por conversación. El adaptador compila el grafo, envía solo el mensaje nuevo y lee los mensajes que el turno agregó. Cada conversación empieza vacía. El prompt de sistema va al frente de cada llamada y no se guarda en el estado.

**Herramientas.** Las tres del dominio, como `StructuredTool`, con las mismas descripciones y el mismo esquema de argumentos que la edición del SDK; se verificó el esquema que recibe la API. `ToolNode` las ejecuta, y si el modelo pide varias en un mismo mensaje, las ejecuta en paralelo.

- Una herramienta que lanza una excepción no corta el turno: el modelo recibe el error como resultado y la conversación sigue.
- LangGraph agrega a ese resultado la frase en inglés "Please fix your mistakes.".
- Las herramientas del dominio devuelven sus errores como datos, sin lanzar excepciones, así que la frase no aparece en uso normal.

**Modelo.** La integración propia del framework, `ChatAnthropic` de `langchain-anthropic` 1.7.5, con el modelo de la variante. Los parámetros que esa integración no fija como el SDK se fijan a mano:

| Parámetro | Valor | Motivo |
|---|---|---|
| Tokens máximos de salida | 32 000, igual en todas las variantes | Por omisión `ChatAnthropic` usa el máximo de cada modelo (128 000 en Sonnet 5, 64 000 en Haiku 4.5), lo que daría topes distintos según la variante. El tope no restringe: en E1 la conversación más larga generó 5 000 tokens de salida en total |
| Razonamiento extendido | desactivado | No se activa; la edición del SDK tampoco lo configura en `ClaudeAgentOptions` |
| Temperatura | la del modelo por omisión | Sonnet 5 no admite fijarla (`agentproof.models`) |
| Tiempo máximo por llamada | 600 s | `ChatAnthropic` crea el cliente sin tiempo máximo, y una llamada colgada detendría la tanda sin aviso. Es el valor por omisión del SDK de Anthropic para llamadas sin streaming |
| Reintentos ante errores de la API | 2 | El valor por omisión de `ChatAnthropic` |

**Lo que agrega el adaptador.**

- Un tope de 100 supersteps por turno. LangGraph 1.2.12 corta recién a los 10 007. Un bucle que el contador de la edición no cortara terminaría como error tras 50 llamadas al modelo, con un costo acotado. La edición necesita como máximo 22 supersteps con el límite de 10 (`start`, diez llamadas al modelo, diez a las herramientas y `cut`), así que el tope no interviene en uso normal.
- La negativa a correr con el envío de trazas de LangChain activo. Se comprueba al crear la fábrica de sesiones, de modo que `agentproof run` se detiene antes de la primera conversación.

**Diferencias conocidas con Claude Agent SDK.**

- **Caché de prompts.** El SDK la usa y esta edición no, así que cada llamada paga el prompt completo.
- **Costo del agente.** En E4 se calcula con la tabla de precios (D-007) y el modelo pedido. En E1 se tomó de la consola, porque la caché impide calcularlo con la tabla.
- **Petición al modelo.** Esta edición envía solo el prompt del dominio, las tres herramientas y los parámetros de la tabla. El SDK arma su petición dentro de su CLI, que no se inspeccionó, así que no se puede afirmar que sea idéntica.

Ninguna de estas diferencias cambia la definición de las mutaciones, que se comprueba con la prueba de paridad de las dos ediciones. La versión de cada paquete queda en el lockfile. La enmienda 2 del pre-registro congela antes de E4 las herramientas, los límites, `MAX_TOKENS` y las versiones de esta edición.

### smolagents

**Agente y límite de pasos.** La edición (`casestudy/editions/smolagents.py`) es un `ToolCallingAgent`, el agente de smolagents que llama herramientas de forma nativa. Un paso es una llamada al modelo. La línea base tiene 10 (`max_steps`), D6 usa un límite propio, que se calibra como en D-003, y el contador vuelve a cero en cada turno del cliente.

- Al agotar `max_steps`, smolagents hace **una llamada más**, sin herramientas y sin el prompt del dominio, que obliga al modelo a responder. Esa respuesta es la que recibe el cliente, cuenta como comunicada y el turno queda como `step_limit`. El turno siguiente no la ve en el historial.
- Es distinto del SDK y de LangGraph, que cortan sin responder. Por eso el comportamiento de D6 puede no ser el mismo con el mismo número, y la sonda lo mide.

**Respuesta y prompt.** smolagents no deja que el modelo responda con texto: cada respuesta al cliente pasa por su herramienta interna `final_answer`, y el modelo está obligado a llamar alguna herramienta en cada paso (`tool_choice: any`). El adaptador toma `final_answer` como la respuesta y nunca la registra como llamada del dominio. El prompt del dominio va, sin cambios, en el lugar nativo (`instructions`), pero dentro del prompt de smolagents en inglés, que describe ese formato. Es el uso nativo del framework y no se reescribe.

**Memoria.** La del propio agente, con `run(mensaje, reset=False)` en cada turno y un agente nuevo por conversación. smolagents le devuelve al modelo las llamadas y sus resultados como texto, no como bloques nativos de herramienta, y presenta cada turno del cliente como una tarea nueva.

**Herramientas.** Las tres del dominio, como subclases de `Tool`, con las mismas descripciones. smolagents exige una descripción por argumento; se deja vacía, porque las otras ediciones no la tienen. Una herramienta que falla no corta el turno: el modelo recibe el error. Si el modelo pide en una misma respuesta `final_answer` y otra herramienta, o varias herramientas y una falla, smolagents ejecuta las demás pero el modelo no ve sus resultados. El adaptador las registra igual, en orden, y marca como error las de un paso fallido; un ticket podría crearse dos veces, y eso queda en la traza.

**Modelo.** `LiteLLMModel` con el modelo de la variante, porque smolagents no tiene una integración propia de Anthropic. Los parámetros son los de LangGraph, salvo los reintentos:

| Parámetro | Valor |
|---|---|
| Tokens máximos de salida | 32 000 |
| Razonamiento extendido | desactivado |
| Temperatura | la del modelo por omisión |
| Tiempo máximo por llamada | 600 s |
| Reintentos | los de smolagents: solo ante el límite de tasa de la API |

La planificación de smolagents y la salida en streaming quedan desactivadas, como vienen por omisión, así que no hay llamadas al modelo fuera de los pasos y la respuesta forzada. No hay caché de prompts, y el costo se calcula con la tabla de precios y el modelo pedido, sumando todos los pasos del turno, incluida la respuesta forzada.

**Lo que agrega el adaptador.** La negativa a correr si litellm saldría a un servicio externo: sin `LITELLM_LOCAL_MODEL_COST_MAP=True` descarga al importarse su tabla de costos desde GitHub; tampoco corre con callbacks de litellm a otros servicios ni con la instrumentación OpenTelemetry de smolagents cargada.

**Interfaz.** La edición se abre en la interfaz de Gradio de smolagents (`studio/smolagents/`), solo en `127.0.0.1`, con el enlace público (`share`) forzado a desactivado y la analítica de Gradio apagada. smolagents no está en E4 ni en la huella del pre-registro: su corrida de punta a punta demuestra la portabilidad.

## D-013 · Conversación de varios turnos y equivalencias de la edición CrewAI

- **Fecha:** 10 de noviembre de 2026
- **Estado:** decidida e implementada; verificada en vivo el 12 de noviembre de 2026 (sonda de D-003, adenda de CrewAI). La respuesta forzada se había verificado antes con Haiku 4.5, el 10 de noviembre
- **Origen:** F4, portabilidad (§5.7); el spec de F4 dejaba la conversación de varios turnos para después de leer el código de CrewAI 1.15.23

### El problema

CrewAI está pensado para tareas, no para conversar. El spec admitía dos caminos: `Agent.kickoff(messages=...)` con el historial completo, o un `Crew` con una `Task` por turno. Había que elegir cómo se ven las llamadas a herramientas y cómo se reconoce que se alcanzó el límite de pasos.

### La decisión

- **`Agent.kickoff` con el historial de la sesión.** Un agente por conversación. En cada turno, la sesión del adaptador le pasa el historial completo que ella misma guarda y agrega lo que el turno produjo. CrewAI no guarda memoria entre llamadas, así que cada conversación empieza vacía. Memoria, conocimiento, caché de herramientas, planificación, delegación y resúmenes de historial quedan desactivados.
- **Las herramientas se leen de los mensajes que devuelve el kickoff** (`LiteAgentOutput.messages`), no del bus de eventos de CrewAI. El bus es global, corre en otros hilos y no trae el identificador de cada llamada, así que podría mezclar sesiones o desordenarlas.
- **Un turno que falla conserva lo hecho.** Un gancho antes de cada llamada al modelo registra lo que el turno ya produjo; si una llamada falla, el turno termina como error con sus herramientas ya ejecutadas, como en las otras ediciones.

### Equivalencias

**Límite de pasos.** `max_iter` cuenta rondas de herramientas, no llamadas al modelo. Con `max_iter = k`, el agente tiene a lo sumo k llamadas al modelo con herramientas; si en la k-ésima sigue pidiendo herramientas, la siguiente llamada, sin herramientas, lo obliga a responder. Así, un turno que necesitaría más de k llamadas al modelo se corta, la misma regla que un límite de k pasos en el SDK. La respuesta forzada es la que recibe el cliente, cuenta como comunicada y el turno queda como `step_limit`; el adaptador lo reconoce porque el turno usó k rondas de herramientas. CrewAI no guarda esa respuesta en el historial (ni la final de un turno sin herramientas), así que el adaptador la agrega para que el turno siguiente la vea. La línea base tiene 10. D6 usa un límite de 2 (D-003, adenda de CrewAI), y por la respuesta forzada el caso "creó el ticket pero no comunicó el número" no se repite en este framework: en la sonda, el agente comunicó el número.

**Prompt.** El prompt del dominio va sin cambios como `backstory`. CrewAI exige además un rol y un objetivo, que son dos frases cortas tomadas del mismo prompt, y lo envuelve todo en su propio texto en inglés ("You are…", "Current Task:"). Es el uso nativo y no se reescribe.

**Herramientas.** Las tres del dominio, con las mismas descripciones; devuelven el resultado del dominio como JSON. CrewAI las envía con esquema estricto (`strict: true`) y una secuencia de parada (`\nObservation:`). Si el modelo escribe texto junto a una llamada a herramienta, CrewAI lo descarta. Una herramienta que falla no corta el turno: el modelo recibe el error. Una respuesta final vacía se registra como error del turno; en las otras ediciones queda como respuesta vacía.

**Modelo.** El proveedor nativo de Anthropic de CrewAI, con el modelo de la variante y los parámetros de D-012: 32 000 tokens de salida, sin razonamiento extendido, temperatura por omisión y 600 s por llamada (CrewAI usaría 128 000 tokens y ningún tiempo máximo). Reintentos: 2, los del SDK de Anthropic por omisión, más el reintento propio de CrewAI ante el límite de tasa (hasta 3 intentos), que no queda a la vista en la traza. El reintento de tareas de CrewAI (`max_retry_limit`) y su tiempo máximo de ejecución no se aplican a `kickoff`.

**Costo.** El proveedor de CrewAI marca siempre puntos de caché de prompts, y la tabla de precios no los distingue. El costo del agente de esta edición se toma de la consola de facturación, como el del Agent SDK en E1 (D-007), y su corrida de punta a punta va en un día UTC propio para poder leerlo.

**Lo que agrega el adaptador.** La negativa a correr si CrewAI enviaría telemetría o trazas: sin `CREWAI_DISABLE_TELEMETRY=true` (u `OTEL_SDK_DISABLED`, `CREWAI_DISABLE_TRACKING`), el primer kickoff intentó conectarse a `telemetry.crewai.com`; y con `CREWAI_TRACING_ENABLED` activo enviaría las trazas de ejecución.

**Interfaz.** CrewAI no ofrece una interfaz como Studio para un agente individual: `crewai chat` es otra arquitectura, y el gráfico de flujos muestra el bucle genérico de CrewAI, no este agente. Se declara así, y `studio/crewai/` trae una consola local mínima para conversar con la edición viendo cada llamada a herramienta y el corte.

**Dependencias.** CrewAI 1.15.23 exige `pydantic<2.13` y `mcp` 1.x. El proyecto pasó de pydantic 2.13.5 a 2.12.5 y de mcp 2.2.0 a 1.28.1, también para la edición Claude Agent SDK. Antes de integrarlo se verificó que las 800 trazas y los 800 veredictos de E1, el volcado del oráculo y el análisis de E1 salen idénticos. E1 se reproduce con el `uv.lock` de su tag (`preregistro-v2`) y E4 con el de `preregistro-v3`. La edición Claude Agent SDK se verificará en vivo con mcp 1.28.1, con sus pruebas en vivo, antes de cerrar F4. CrewAI no está en E4 ni en la huella del pre-registro: su corrida de punta a punta demuestra la portabilidad.

## D-014 · Regla de conteo del costo de incorporación

- **Fecha:** 11 de noviembre de 2026
- **Estado:** decidida con el autor e implementada en `src/experiments/portability.py`
- **Origen:** spec de F4, §8, que pide fijar la regla antes de medir

### El problema

El spec de F4 (§8) pide medir cuánto cuesta incorporar un framework: líneas del adaptador y de la edición, líneas de sus pruebas y archivos del núcleo que hubo que tocar. Cada uno de esos números admite varias lecturas. "Línea de código" puede ser una línea física, que depende de dónde corte el formateador, o una sentencia. Las pruebas de un framework se reparten entre archivos propios, modelos falsos, pruebas compartidas por todas las ediciones y pruebas en vivo que no todas las ediciones tienen. Los commits de un framework se pueden identificar por su pull request o por su mensaje, y el Claude Agent SDK no tiene ni lo uno ni lo otro, porque el núcleo se escribió junto con él.

### La regla

- **Línea de código = línea física con código**, como dice el spec. No cuentan las líneas en blanco, los comentarios ni los docstrings (la primera sentencia de un módulo, una clase o una función, cuando es una cadena). Cualquier otra cadena cuenta, aunque ocupe varias líneas. Como complemento, el adaptador y la edición se cuentan también en líneas lógicas, una por sentencia, que no cambian con cómo el formateador parte las líneas. Se implementa con `tokenize` y `ast`.
- **Adaptador y edición.** El adaptador es `src/agentproof/adapters/<framework>.py` y la edición es `src/casestudy/editions/<framework>.py`. El dominio del caso de estudio y `adapters/__init__.py` son compartidos y no se atribuyen a ningún framework.
- **Pruebas.** Se cuentan los archivos propios del framework: las pruebas del adaptador y de la edición, su modelo falso y las pruebas de ese modelo falso, y la prueba de su interfaz local si existe. Quedan fuera los modelos falsos del núcleo (`tests/fakes.py`) y la prueba que comparten todas las ediciones (`tests/test_editions_mutations.py`). Las pruebas en vivo llaman a la API de pago y nunca corren en CI, así que van en una columna aparte. La lista de archivos es una constante declarada en el módulo. Una prueba verifica que todo archivo de `tests/` cuyo nombre mencione un framework esté asignado a ese framework y a ningún otro.
- **Archivos del núcleo modificados.** El núcleo es `src/agentproof` sin `adapters/`. En LangGraph se toma `git diff --name-only` entre la base del PR #29 (`25aaf08`, primer padre del merge `012a7a8`) y su último commit (`6fca512`). En CrewAI y smolagents, que todavía no tienen un PR fusionado, se toman los commits posteriores a `012a7a8` cuyo mensaje menciona el framework, sin distinguir mayúsculas de minúsculas. Para el Claude Agent SDK no aplica, porque fue el primer framework y el núcleo se diseñó con él: la tabla muestra "—".
- **Interfaz local (`studio/`).** Se mide aparte, porque no forma parte de lo que necesita la herramienta. Se cuentan las líneas de código de los `.py` y las líneas no vacías de la configuración `.json`. Los README no se cuentan.
- **Historia incompleta.** Si el clon es superficial o falta un commit de referencia, la columna del núcleo muestra "n/d" con el motivo, en lugar de un número. Lo mismo pasa si ningún commit menciona el framework. El CI clona con profundidad 1, así que ahí siempre sale "n/d".

### Por qué así

- **Las físicas, porque es lo que se fijó antes de medir.** El spec aprobado define así la línea de código. Se consideró contar líneas lógicas, que no dependen del formateador (la misma llamada cuenta 1 o 6 según quepa en 100 columnas). El autor prefirió la regla del spec y dejar las lógicas como columna complementaria; las conclusiones son las mismas con las dos.
- **Las pruebas en vivo, aparte.** Así las ediciones que no tienen pruebas en vivo no parecen más baratas de probar.
- **El conteo del núcleo no depende de cómo se ordenaron los commits.** Con el diff del PR, en LangGraph no importa el orden de sus commits. Identificar los commits por mensaje sobrevive a un rebase, cosa que no pasaría con una lista de SHA. Cuando CrewAI y smolagents se fusionen en su PR, el modo se puede cambiar al de LangGraph sin cambiar la regla.
- **Mejor "n/d" que un cero falso.** Un clon superficial devolvería cero archivos modificados, que es justo el resultado que se quiere demostrar.
- **Lo que queda fuera se declara.** El PR de LangGraph también tocó código compartido fuera del núcleo: `src/casestudy/domain/tools.py`, donde las descripciones de las herramientas pasaron al dominio, y `src/casestudy/editions/claude_sdk.py`. También tocó el oráculo (`src/experiments/oracle/`), pero por la enmienda 2 y no por la incorporación. Nada de eso entra en la columna del núcleo, y la tesis lo menciona en el texto.

### Tabla que imprime el comando

`uv run python -m experiments.portability`, el 11 de noviembre de 2026:

| Framework | Adaptador | Edición | Pruebas | Pruebas en vivo | Archivos del núcleo modificados | Interfaz local (studio/) | Adaptador / edición en líneas lógicas |
|---|---:|---:|---:|---:|---:|---:|---:|
| Claude Agent SDK (referencia) | 124 | 49 | 203 | 116 | — | — | 98 / 34 |
| LangGraph | 130 | 74 | 524 | 45 | 0 | 14 | 102 / 66 |
| CrewAI | 150 | 62 | 740 | 0 | 0 | 54 | 115 / 43 |
| smolagents | 142 | 57 | 623 | 0 | 0 | 16 | 118 / 48 |

Ningún framework obligó a modificar el núcleo. Sus adaptadores miden entre 130 y 150 líneas, cerca de las 124 del de Claude Agent SDK.

## D-015 · Versión de las convenciones GenAI y mapeo del esquema

- **Fecha:** 11 de noviembre de 2026
- **Estado:** decidida e implementada en `src/agentproof/otel.py`; el mapeo completo está en [otel.md](otel.md)
- **Origen:** F4, portabilidad (§5); el spec de F4 (§9) pide fijar la versión de la convención y su estado de estabilidad

### El problema

Las convenciones semánticas de IA generativa de OpenTelemetry cambian casi cada semana y no publican versiones, así que "seguir las convenciones" no dice nada si no se fija cuáles. Además, el esquema de AgentProof guarda cosas que la convención no contempla (condición, repetición, motivo de terminación) y le faltan otras que la convención espera (uso por llamada al modelo, identificador de cada llamada a herramienta).

### Lo que se fija

- **Fuente.** `open-telemetry/semantic-conventions-genai`, commit `e6658f14c9d9ea0760825f029cb82e7673f48fab` del 6 de noviembre de 2026. Las convenciones GenAI se mudaron ahí desde `open-telemetry/semantic-conventions`, cuya página de GenAI ahora dice "Moved". El repositorio no tiene releases ni tags; su manifiesto declara el esquema `gen-ai-dev/1.42.0-dev` y depende de las convenciones generales v1.45.0.
- **Estabilidad.** Todo lo de GenAI que se usa está en *development*: los spans `gen_ai.invoke_agent.internal` y `gen_ai.execute_tool` y cada atributo `gen_ai.*`. Solo `error.type` y `service.name`, de las convenciones generales, son estables. Un cambio de nombre aguas arriba no rompe nada aquí hasta que se decida mover el commit fijado, que es una decisión nueva.
- **Estructura.** Un span raíz propio por conversación (`agentproof.conversation`), un span `invoke_agent` por turno y un span `execute_tool` por llamada a herramienta, hijo de su turno. El uso del agente va en `gen_ai.usage.*` de la raíz; la conversación se identifica con `gen_ai.conversation.id`, que es el `trace_id` de AgentProof.
- **Lo propio, con prefijo.** Todo lo que no tiene atributo estándar va con prefijo `agentproof.`: la condición, la variante, la corrida, el escenario, la repetición, el intento, el motivo de terminación y el de parada de cada turno, el costo, el uso del usuario simulado y los modelos.
- **Formato.** OTLP/JSON, generado por una función pura sin el SDK de OpenTelemetry ni dependencias nuevas, con ids derivados del `trace_id` para que la salida sea reproducible.
- **Verificación.** `tests/test_otel.py` tiene su propia tabla de los atributos estándar con su estabilidad en ese commit, y convierte las 100 trazas de D6 de E1 y las 23 del piloto de LangGraph.

### Por qué así

- **Un commit y no una versión**, porque no hay versiones; el commit queda además en cada documento exportado (`agentproof.semconv.commit`).
- **Raíz propia.** La convención no define un span de conversación. La conversación la conduce AgentProof, fuera del agente, y los datos de la traza que no son de ningún turno necesitan un lugar.
- **El uso en la raíz y no en cada turno**, porque la traza guarda solo el total de la conversación. Repartirlo entre turnos sería inventarlo; ponerlo en la raíz, una vez, permite sumar el uso de todos los spans sin contarlo dos veces.
- **La variante como `gen_ai.agent.version`**, porque es la versión del agente que AgentProof compara.
- **No se inventa lo que la traza no tiene.** Sin `gen_ai.tool.call.id`, `gen_ai.request.model`, `gen_ai.provider.name` ni spans de inferencia: la traza no los registra. Un resultado de herramienta en texto queda como texto, aunque el esquema espera un objeto.
- **No cambia el esquema.** El mapeo es una vista de la traza: no toca `Trace`, ninguna pieza de la huella del pre-registro ni ningún dato de E1, y es código nuevo del núcleo, no una modificación para un framework (spec de F4, §9), así que no cuenta en el costo de incorporación (D-014).

## D-016 · Análisis de los desacuerdos entre el oráculo y AgentProof

- **Fecha:** 20 de octubre de 2026; corregida el 21 de octubre de 2026
- **Estado:** decidida con el autor después de E1 y antes de que ningún anotador vea una traza; se implementa en `src/experiments/disagreements.py`
- **Origen:** retroalimentación del tutor al segundo entregable

**Corrección del 21 de octubre.** La primera versión miraba solo las repeticiones de la candidata y una sola dirección de discordancia, y clasificaba los 18 desacuerdos en 10 "de traza" y 8 "de agregación". El tutor mostró dos casos mal clasificados. En D1, sc-tr-d707df857e02 (tc-09), el evaluador reprueba 5 de 5 repeticiones de la candidata y el oráculo marca 2, y se había clasificado como de agregación. En D4, sc-tr-e326cdcb18af (tc-07), en la línea base el oráculo marca 4 fallos y el evaluador ninguno, y no se miraba. La versión corregida mira las dos corridas y las dos direcciones, y separa dos ejes que la primera confundía. La afirmación de que en los casos "de agregación" los dos mecanismos se corroboraban era falsa en 7 de esos 8 casos y se retiró. Ningún anotador había visto la primera muestra, así que se reemplazó y se conservó la semilla.

### El problema

En E1, el oráculo y AgentProof no siempre coinciden. D1 tiene once escenarios en el conjunto manifestado que el reporte no declaró como regresión (falsos negativos), y D6 tiene cinco regresiones que el oráculo no considera manifestadas (falsos positivos). La auditoría del oráculo y E2 miden cada mecanismo por separado, sobre muestras sorteadas antes de ver estos desacuerdos. Hace falta un procedimiento, fijado antes de mirar ninguna anotación, que diga de dónde viene cada desacuerdo y, cuando hay conversaciones con veredictos opuestos, si el error es del evaluador, de los criterios inducidos o de las reglas del oráculo.

### Los desacuerdos y sus dos ejes

Se toman todos los falsos negativos y falsos positivos de la matriz de confusión de E1: 18 escenarios (11 de D1, 1 de D2, 1 de D4 y 5 de D6). Cada uno se describe sobre las cinco repeticiones de la línea base de referencia y las cinco de la candidata, con dos ejes independientes:

- **Repeticiones discordantes.** Una repetición es discordante si el predicado del oráculo falla y el evaluador la aprobó, o si el evaluador la reprobó y el predicado no falla. Cuentan las dos corridas y las dos direcciones. 17 de los 18 escenarios tienen al menos una; el único sin ninguna es sc-tr-3ee71ca0bdcf (tc-16) de D1.
- **Origen de la diferencia de clasificación.** Para cada mecanismo se calcula cuánto sube la tasa de fallo de la candidata respecto de la referencia. Si los dos llegan al umbral de 0.4, o ninguno, los dos vieron el mismo cambio y la diferencia viene de la **agregación**: el reporte exige además significancia estadística, que con cinco repeticiones no se alcanzó. Si uno llega y el otro no, la diferencia viene de las **trazas**. Son 3 de agregación, todos de D1 (sc-tr-3ee71ca0bdcf (tc-16), sc-tr-69b396c04669 (tc-05) y sc-tr-d707df857e02 (tc-09)), y 15 de trazas.

Los dos ejes pueden coincidir en un mismo escenario: sc-tr-69b396c04669 (tc-05) y sc-tr-d707df857e02 (tc-09) tienen origen en la agregación y además repeticiones discordantes.

### El sorteo

Para cada corrida y dirección con repeticiones discordantes de un escenario (una celda) se sortea una de esas repeticiones con la semilla `20261022`, recorriendo los desacuerdos en un orden fijo. Hay 23 celdas: 17 en la dirección "el evaluador reprueba y el oráculo no" y 6 en la dirección contraria; 9 en la línea base y 14 en la candidata. Una misma traza de la línea base sorteada para dos operadores se anota una sola vez, así que son 22 trazas distintas. Cada celda registra cuántas repeticiones discordantes representa.

Todo está en `results/samples/desacuerdos.json`, que genera `python -m experiments.disagreements --data . --reference baseline-a-20261018-000105 --candidate <corrida> ...`, con los fallos de cada mecanismo por corrida, el origen y las celdas de cada desacuerdo. Las pruebas exigen que el archivo sea el que produce la semilla y fijan los dos casos que señaló el tutor.

### Qué anotan los tres anotadores

Cada traza sorteada se presenta a ciegas: la situación, los datos del pedido, la transcripción y los criterios del escenario, sin la condición, la corrida ni la salida del oráculo o del evaluador. Va mezclada con las trazas de la auditoría y de E2, y si ya forma parte de una de esas muestras se etiqueta una sola vez. Las etiquetas son hechos, no atribuciones:

1. qué decisión comunicó el agente (procede, no procede, escalamiento o ninguna);
2. si enunció algún dato del pedido que contradice la base y, si la situación lo pide, si entregó el estado del pedido;
3. si se cumple cada criterio del escenario, con la rúbrica de E2.

### Cómo se atribuye cada discordancia

La atribución se calcula a partir de las etiquetas, con la mayoría de los tres anotadores, y quedó fijada antes de ver ninguna:

1. **Reglas del oráculo.** Si el predicado del operador, aplicado a las etiquetas de los puntos 1 y 2, da distinto que el predicado del oráculo.
2. **Evaluador.** Si la aprobación según las etiquetas del punto 3 (todos los criterios cumplidos) da distinto que el veredicto del evaluador.
3. **Alcance distinto.** Si ni el oráculo ni el evaluador se equivocaron y la repetición sigue siendo discordante, los dos miden aspectos distintos. En la dirección "el oráculo falla y el evaluador aprueba", los criterios no cubren el fallo que mide el predicado. En la dirección contraria, los criterios exigen algo que el predicado no mide.

Los casos 1 y 2 pueden darse a la vez, y entonces se informan los dos. Se reportan los conteos por causa, por operador, por corrida y por dirección, ponderados por las repeticiones discordantes que representa cada celda. Una decisión sin mayoría entre los tres anotadores se informa aparte.

### Lo que este análisis no hace

- **No es una enmienda.** No cambia ninguna pieza de la huella, ningún resultado de E1 ni la definición del conjunto manifestado. Es un análisis exploratorio, agregado después de ver los resultados de E1 y declarado como tal en la §8 del pre-registro.
- **La muestra queda congelada tras la enmienda 2.** La enmienda 2 corrigió la lectura que producía el desacuerdo de D2 (sc-tr-69b396c04669, [D-005](#d-005--calibración-del-oráculo-con-respuestas-de-agentes-degradados), adenda de LangGraph). Con el oráculo nuevo quedan 17 desacuerdos, pero el sorteo recorre los desacuerdos en orden, así que sortear de nuevo cambiaría cinco trazas de otros desacuerdos que no cambiaron. La muestra describe la puntuación original de E1 y no se vuelve a sortear: el desacuerdo de D2 ya está atribuido a las reglas del oráculo, y las pruebas exigen que, con el oráculo nuevo, sea el único que desaparece.
- **Si atribuye una discordancia a las reglas del oráculo,** la corrección sigue el camino ya pre-registrado para la auditoría: una enmienda con su motivo, E1 vuelto a puntuar y las dos puntuaciones reportadas.
