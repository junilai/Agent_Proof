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
