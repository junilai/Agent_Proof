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
