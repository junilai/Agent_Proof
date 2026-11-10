# Piloto de la edición LangGraph

Antes de E4 se repitió el [piloto](piloto.md) con la edición LangGraph ([D-012](decisiones.md)), con el mismo diseño: probar el camino completo en ese framework y proyectar el costo de E4. Se corrió el 10 de noviembre de 2026 (UTC), con el oráculo de la enmienda 2 ([pre-registro, §8](preregistro.md#8-desvíos-y-enmiendas)). Sus datos no entran en el análisis de E4.

## Qué se corrió

- **Corridas.** `baseline-a` y `d4` con `--adapter langgraph --agent casestudy.editions.langgraph:builder`, sobre los mismos cinco escenarios del piloto de F3: tc-01, tc-04, tc-06, tc-09 y tc-15.
- **Repeticiones.** Dos por escenario: 20 conversaciones y 20 juicios.
- **Dónde están.** En [`evidence/piloto-langgraph/`](../evidence/piloto-langgraph/), con su propia copia del corpus, igual a la del piloto de F3.
- **Incidencias.** Las 20 conversaciones terminaron por el usuario simulado y los 20 juicios sin fallas. Ningún error del agente, ningún reintento y ningún corte por límite de pasos. Las dos corridas, en paralelo, tardaron unos 4 minutos.

## Costo y latencia

Medidos con `agentproof cost`. En esta edición el costo del agente se calcula con los tokens que devuelve la API y la tabla de precios, sin caché de prompts, y cuadra con lo facturado ([D-003](decisiones.md), adenda de LangGraph). La fila del inductor que imprime el comando corresponde a la inducción del corpus copiado, del 17 de octubre, y no a este piloto.

| Componente | USD en el piloto | USD por conversación | Segundos medios por llamada |
|---|---|---|---|
| Agente | 0.668 | 0.033 | 15.1 |
| Usuario simulado | 0.077 | 0.004 | 4.1 |
| Evaluador | 0.529 | 0.026 | 7.7 |
| **Total** | **1.274** | **0.064** | |

**Proyección de E4.** 400 conversaciones con su juicio cuestan unos **USD 25**, por debajo de los USD 35 estimados con el piloto de F3. La contingencia de costo (§2 del pre-registro) no se activa: E4 mantiene cinco repeticiones.

## El evaluador

Los veredictos no muestran nada distinto de lo visto en el piloto de F3. Con dos repeticiones ninguna diferencia puede ser significativa, y el reporte se registra solo como prueba de que el camino funciona: 0 regresiones y 3 señales débiles en 5 escenarios (tc-15, tc-06 y tc-04). La más clara es tc-15: D4 baja la aprobación de 2 de 2 a 0 de 2, porque la política corrupta lleva a aprobar el reembolso de un mouse defectuoso pasados los 30 días en lugar de escalarlo como reclamo de garantía.

## El oráculo

- **D4 falla donde debe.** Falla en las dos trazas de tc-15 (aprueba el reembolso de un mouse defectuoso pasados los 30 días) y en una de tc-06 (aprueba el de la tarjeta de regalo). La otra traza de tc-06 dice "tu solicitud **procede**" sin nombrar el reembolso en esa oración, y las reglas no la leen: queda a la anotación manual. Ninguna traza contradice la base.
- **La línea base en tc-09.** Como en el piloto de F3, en una repetición escala para que un supervisor intente detener el envío, y el oráculo lo lee como escalamiento. El conjunto manifestado descuenta ese comportamiento de la línea base.
- **Carga manual.** 3 de 20 trazas quedan sin resolver (una de tc-06 y dos de tc-09), contra 1 de 20 en el piloto de F3 y 13 de 800 en E1. Si la proporción se mantiene, E4 tendría unas 60 trazas a anotar a mano, y se anotan antes de calcular ninguna métrica. Las del piloto no se anotan, porque sus datos no se analizan.
