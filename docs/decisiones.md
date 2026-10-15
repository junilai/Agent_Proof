# Decisiones

Decisiones de diseño que no se deducen del código ni de la [planificación](planificacion.pdf), con su motivo y su estado. Cada una se registra cuando se toma, no cuando se implementa.

## D-001 · Repeticiones inválidas: cuándo se reintenta y cuándo no

- **Fecha:** 23 de septiembre de 2026
- **Estado:** decidida; se implementa en F3, cuando exista el aparato experimental
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
