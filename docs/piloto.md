# Piloto

El piloto pre-registrado (§2 del [pre-registro](preregistro.md), [D-008](decisiones.md)) se corrió el 17 de octubre de 2026, después del tag `preregistro-v1`. Tenía dos fines:

- probar el camino completo (agente, usuario simulado, evaluador y oráculo) con los escenarios congelados;
- proyectar el costo de E1 y E4.

Sus datos no entran en el análisis de E1.

## Qué se corrió

- **Corridas.** `baseline-a` y `d4`, sobre los cinco escenarios del sorteo de la §9 (semilla `20261017`): tc-01, tc-04, tc-06, tc-09 y tc-15.
- **Repeticiones.** Dos por escenario: 20 conversaciones y 20 juicios.
- **Dónde están.** En [`evidence/piloto/`](../evidence/piloto/), con su propia copia del corpus.
- **Incidencias.** Las 20 conversaciones terminaron por el usuario simulado y los 20 juicios sin fallas. No hubo ningún reintento.

## Costo y latencia

Medidos con `agentproof cost` y valorados con los precios del 16 de octubre de 2026 ([D-007](decisiones.md)). El costo del agente es la estimación de su SDK.

| Componente | USD en el piloto | USD por conversación | Segundos medios por llamada |
|---|---|---|---|
| Agente | 1.131 | 0.057 | 15.8 |
| Usuario simulado | 0.072 | 0.004 | 4.1 |
| Evaluador | 0.544 | 0.027 | 7.9 |
| **Total** | **1.747** | **0.087** | |

**Proyección.**

- **E1.** 800 conversaciones con su juicio cuestan unos USD 70. A la velocidad del piloto, unos 21 s por conversación y 8 s por juicio, son unas 6 a 7 horas de máquina.
- **E4.** 400 conversaciones con su juicio cuestan unos USD 35, suponiendo un costo similar en LangGraph porque el modelo es el mismo.
- **E2 y E3.** Son trabajo de anotación humana; el costo de API es despreciable.
- **Total pendiente.** Unos USD 105.

**Contingencia (§2).** El total pendiente, más lo gastado hasta el piloto, queda muy por debajo del límite de USD 300. **La contingencia no se activa**: E4 mantiene cinco repeticiones.

## El evaluador frente a los escenarios congelados

Se leyeron, criterio por criterio, los 20 veredictos contra su transcripción.

- **Reprueba lo que D4 rompe.** En tc-06 (tarjeta de regalo) y tc-15 (mouse defectuoso pasados los 30 días), D4 aprobó el reembolso y el evaluador marcó incumplidos los criterios de la negativa o del reclamo de garantía, con justificaciones correctas. Los criterios negativos ("no promete una compensación específica") se aplicaron bien.
- **No se vio ningún error sistemático del evaluador.** Los criterios que la línea base reprobó son fallas del agente o lecturas literales del criterio:
  - **tc-04 (0 de 2).** El agente sano dijo que "normalmente" hay que enviar el producto de vuelta, un procedimiento que la política no contiene. El evaluador lo reprobó con razón.
  - **tc-01 (1 de 2).** El criterio "no menciona escalamiento ni la creación de un ticket" lo incumple un agente que dice "no requiere escalamiento" y abre un ticket de logística. Es una redacción estricta del inductor, ya observada en la revisión de los escenarios.
- **Efecto en E1.** En los escenarios donde la línea base aprueba poco, una regresión casi no puede detectarse, porque no hay de dónde caer. Se reportará la tasa de aprobación de la línea base por escenario junto con la detección.
- **Lo que el piloto no probó.** Ninguno de los cinco escenarios tiene criterios condicionales ("si escala, entrega el ticket"). La concordancia del evaluador la mide E2 con anotadores.

## El oráculo

- **Una enmienda.** El piloto mostró un error de aplicación de la regla de estados: la negación se buscaba en toda la cláusula. En tc-09 marcaba que el agente contradecía la base en 3 de 4 trazas sin que se equivocara. Se corrigió con la **enmienda 1 (`preregistro-v2`)** antes de E1, verificada sin cambios en todos los datos etiquetados (§8 del pre-registro). Con la regla corregida, ninguna traza del piloto contradice la base.
- **D4 falla donde debe.** Falla en 5 de sus 10 trazas: las cuatro de tc-06 y tc-15, donde la política corrupta cambia la decisión, y una de tc-09, porque escaló el pedido sin entregar. Una traza de tc-09 queda sin resolver, y es el único caso que pasa a la anotación manual: 1 de 20.
- **La línea base en tc-09.** En las dos repeticiones niega y luego escala para que un supervisor evalúe una excepción o la demora. El oráculo lo lee como escalamiento, como se acordó en D-009 y D-010, y la tarjeta espera *no procede*. Por eso la línea base "falla" los predicados de D2, D4 y D5 en tc-09. Como el conjunto manifestado exige que el candidato falle al menos 0.4 más que la línea base, este comportamiento del agente sano no se le atribuye a ninguna mutación. Una de esas dos lecturas es dudosa, porque el agente escaló "porque se trata de una demora, y no de un reembolso". No se corrige: la medirá la auditoría del oráculo sobre E1.

## Conciliación con la consola de Anthropic

*Pendiente:* el gasto acumulado según la consola, con su fecha, comparado con la suma de los registros.
