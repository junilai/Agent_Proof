# F6: anotación humana de E2, E3, la auditoría del oráculo y los desacuerdos

- **Fecha:** 10 de noviembre de 2026
- **Estado:** aprobado por el autor
- **Fuentes:** pre-registro §4 (auditoría del oráculo) y §6 (E2 y E3); [D-010](../decisiones.md), [D-011](../decisiones.md) y [D-016](../decisiones.md)

## Qué se anota

Tres anotadores independientes, identificados como X1, X2 y X3, etiquetan a ciegas las muestras ya sorteadas sobre E1, en dos sesiones separadas.

**Sesión 1: 94 trazas de E1.** Son las de las tres muestras, cada una etiquetada una sola vez:

| Muestra | Archivo | Trazas | Qué se pide |
|---|---|---|---|
| E2 | `results/samples/e2.json` | 40 | los criterios del escenario |
| Auditoría del oráculo | `results/samples/auditoria.json` | 36 de 40 | los hechos |
| Desacuerdos (D-016) | `results/samples/desacuerdos.json` | 22 | los criterios y los hechos |

- **Criterios.** Cada criterio del escenario, "se cumple" o "no se cumple", con la rúbrica del evaluador automático palabra por palabra (`agentproof.judge.JUDGE_RUBRIC`) y la transcripción que leyó el evaluador, con las llamadas a herramientas. La aprobación de la traza se calcula: todos los criterios cumplidos.
- **Hechos.** Con la guía de D-010: la decisión comunicada (procede, no procede, escalamiento, sin resolver o ninguna) si la tarjeta tiene decisión; si el agente dio un importe, una fecha o un estado que contradice la base, si la tarjeta tiene pedido; y si dio el estado, en las consultas de estado. Se muestran la situación, el pedido en la base y la política verdadera.
- **Llamadas a herramientas.** Se muestran en las trazas que piden criterios, porque el evaluador las leyó. Se ocultan en las que son solo de la auditoría, como en la planilla de D-010, porque sus resultados delatan la mutación. Tres trazas están en la auditoría y además en E2 o en los desacuerdos: muestran las herramientas, y se declara como desvío menor.
- **Cuatro trazas de la auditoría quedan fuera.** Son de tarjetas sin decisión ni pedido (tc-18 a tc-20): el oráculo no lee nada en ellas, así que no hay nada que auditar. Se informan aparte.

**Sesión 2: E3, 20 escenarios.** Cada escenario (objetivo del cliente, primer mensaje y criterios) junto a la conversación semilla de la que se indujo. Se califica en Likert de 1 a 5 con los anclajes del pre-registro, y si requeriría corrección (sí o no). Va en otra sesión, otro día, para reducir el anclaje entre tareas.

## Cómo se presenta

- Una página HTML por anotador y sesión, que funciona sin conexión y guarda el avance en el navegador. Las genera `python -m experiments.annotators --data . --out <carpeta> --annotator X1 --annotator X2 --annotator X3`.
- Los casos llevan un identificador opaco, en un orden sorteado con la semilla `20261111`, igual para los tres anotadores.
- No se muestra la condición, la variante, el modelo, el veredicto del evaluador ni la lectura del oráculo. La clave de los identificadores a las trazas se escribe aparte y no se entrega.
- Se pide a los anotadores no consultar otras fuentes sobre las conversaciones. El repositorio es público y contiene las trazas, así que el cegamiento descansa en esa instrucción.

## Calendario

| Fecha | Paso |
|---|---|
| 12-nov | Se entrega la sesión 1 |
| 15-nov | Se devuelve la sesión 1 y se entrega la sesión 2 |
| 17-nov | Se devuelve la sesión 2 |
| 17–18-nov | Análisis |

Cada anotador devuelve el archivo que descarga la página. Las etiquetas, la clave y las páginas se guardan en `evidence/f6/` al recibirlas.

## Qué se calcula

Lo que fija el pre-registro, sin agregar nada:

- **E2:** κ de Fleiss entre los tres, la matriz de κ de Cohen por pares y la concordancia del evaluador con el voto mayoritario, por traza y por criterio. La proporción natural de aprobaciones de E1, por separado.
- **E3:** el porcentaje de escenarios con mediana de 4 o más, el α de Krippendorff con ponderación ordinal, las comparaciones por pares, la distribución de calificaciones y el porcentaje que requeriría corrección.
- **Auditoría:** el acierto de la decisión, las clasificaciones al revés, los casos sin resolver, los falsos positivos y negativos de atributos y la coincidencia de cada predicado, contra el voto mayoritario. Por estrato (con y sin ticket) y ponderado por la proporción de cada estrato en E1. Concordancia entre los anotadores. Se mide el oráculo de la enmienda 2 y, aparte, el de `preregistro-v2`.
- **Desacuerdos:** la atribución de D-016 (reglas del oráculo, evaluador o alcance distinto), con la mayoría de los tres.
