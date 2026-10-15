# F3 Aparato experimental: especificación

- **Autor:** Jarod Tierra Medina
- **Fecha:** 13 de octubre de 2026
- **Estado:** aprobado
- **Contexto:** fase F3 del [plan maestro](2026-09-21-plan-maestro.md). "§" remite a la [planificación](../planificacion.pdf).

## 1. Alcance

F3 construye lo que hace falta para medir si AgentProof detecta regresiones: las versiones degradadas del agente, la verdad de referencia contra la que se mide, el criterio estadístico de regresión, las métricas de detección y el registro de costo. Termina congelando el protocolo.

**Hito:** tag `preregistro-v1` y corrida piloto de 5 escenarios × 2 repeticiones × 2 condiciones (§7c), que mide el costo y la latencia reales antes de comprometer el volumen completo.

**Distinción que F3 hace explícita.** Hasta F2 existe el recorrido de punta a punta; no existen todavía las mutaciones, los conjuntos expuesto y manifestado, la prueba de Fisher con Benjamini-Hochberg, TPR y FPR ni el pre-registro. Todo eso es F3.

**Fuera de F3:** la ejecución de E1 y E4 (F5), la concordancia del evaluador y la fidelidad de la inducción, con su muestreo y sus anotadores (F6), y los demás frameworks (F4).

## 2. Lo que F3 no puede romper

| Restricción | Cómo se garantiza |
|---|---|
| La variante `baseline` del agente no cambia: las semillas del corpus se graban con ella, antes y después de F3 | Una prueba fija que su prompt, sus herramientas, su modelo, su política y su límite de pasos son los de hoy |
| Las trazas, escenarios y juicios ya guardados siguen leyéndose | Todo campo nuevo es opcional y tiene valor por omisión; se prueba con la evidencia de F1 y el corpus |
| El núcleo no conoce el caso de estudio ni el aparato experimental | La guarda de arquitectura ya lo verifica; el criterio de regresión es parte de la herramienta y vive en el núcleo, la verdad de referencia vive en `experiments` |
| La verdad de referencia no depende del sistema evaluado (§5.4) | El oráculo no importa el evaluador ni lee escenarios inducidos; una prueba de arquitectura lo fija |

## 3. Mutaciones como datos (`casestudy/domain/mutations`)

Cada operador es un dato que declara qué cambia; cada edición del agente aplica la misma definición, de modo que entre frameworks la única variable sea el framework (§5.8).

| Op. | Familia | Qué cambia | Valor |
|---|---|---|---|
| D1 | A | herramientas disponibles | sin `lookup_order` |
| D4 | A | política que devuelve `get_refund_policy` | ventana de 90 días, umbral de USD 5000 y sin categorías excluidas |
| D6 | A | límite de pasos por turno | 2 |
| D2 | B | prompt de sistema | sin la instrucción de consultar la política antes de decidir |
| D5 | B | prompt de sistema | con una instrucción añadida: aprobar todo reembolso |
| D3 | B | modelo del agente | el modelo degradado de la §5.6 |

**Por qué esa política para D4.** Calculada contra el catálogo, cambia la decisión en siete de las quince tarjetas con decisión y deja ocho intactas: la mutación tiene dónde manifestarse y dónde no. Las corrupciones de un solo parámetro cambiaban entre una y cuatro.

**Por qué 2 para D6.** Medido con el agente de Claude Agent SDK: con el límite en 2 se completan las conversaciones de una y dos llamadas a herramientas y se truncan las de tres o más, que es como la §5.4 define el conjunto expuesto de D6. Con 3 no se trunca ninguna. La equivalencia se documenta como decisión y se vuelve a calibrar en cada framework (plan maestro, §2).

Una prueba verifica que cada edición aplica las seis mutaciones.

## 4. Condiciones (`experiments/conditions`)

Ocho condiciones por framework: `baseline-a`, `baseline-b` y las seis mutaciones. `baseline-a` es la referencia de todas las comparaciones con versiones candidatas; `baseline-b` queda reservada al control negativo (§5.4, §5.5).

## 5. Oráculo (`experiments/oracle`)

La verdad de referencia, con tres fuentes anteriores a la ejecución y ajenas a AgentProof: la base de conocimiento del caso de estudio, la tarjeta de situación y los eventos de la traza. Nunca usa el evaluador automático ni los criterios inducidos.

**Conjunto expuesto**, por regla computable sobre información fijada antes de la inducción:

| Op. | Expuesto cuando |
|---|---|
| D1 | la traza semilla llama a `lookup_order` |
| D4 | la traza semilla llama a `get_refund_policy` |
| D6 | la traza semilla tiene tres o más llamadas a herramientas |
| D2 | la tarjeta plantea una decisión de reembolso |
| D5 | la tarjeta espera que el reembolso no proceda |
| D3 | no define conjunto expuesto |

**Extracción del desenlace.** Se extraen, por reglas, la decisión comunicada dentro del vocabulario cerrado (procede, no procede, escalamiento) y los atributos de pedido que el agente enuncia (estado, fecha, importe), que se contrastan contra la base de conocimiento. Lo que las reglas no resuelven no se adivina: pasa a anotación manual.

**Qué mensaje comunica el desenlace.** La §5.4 habla de la respuesta final y define el predicado sobre la decisión comunicada al usuario. En una conversación de varios turnos las dos cosas pueden no coincidir: el agente decide en un turno y el último mensaje es una despedida o la respuesta a una pregunta de seguimiento. Se fija por eso cómo se operacionaliza:

- la **decisión comunicada** es la del mensaje más reciente del agente que enuncia una decisión; los mensajes posteriores sin vocabulario de decisión no la sustituyen, y si el agente cambia de decisión cuenta la última. Si el mensaje más reciente con vocabulario de decisión es ambiguo o contradictorio, el caso pasa a anotación manual;
- los **atributos de pedido** se revisan en todos los mensajes del agente: un dato que discrepa de la base de conocimiento es un resultado incorrecto comunicado al usuario aunque aparezca antes del último turno.

La regla precisa cómo se mide, no qué se mide, y se pre-registra como el resto. Medido sobre las trazas disponibles al diseñar F3, la respuesta final contiene la decisión en las cuatro corridas con usuario simulado, que termina la conversación sin mensaje de cortesía, y solo en dos de las cuatro conversaciones con personas.

**Predicados de fallo:**

| Op. | Falla cuando |
|---|---|
| D1 | la respuesta final enuncia un atributo del pedido que discrepa de la base de conocimiento, u omite el que la tarjeta pedía obtener |
| D2, D4, D5 | la decisión comunicada contradice la que la política verdadera dicta, que la tarjeta declara de antemano |
| D6 | la conversación termina por el límite de pasos y el desenlace que la tarjeta pedía no aparece en la respuesta final |

En las tarjetas sin decisión de reembolso no hay decisión que contradecir, así que el predicado de D2, D4 y D5 es falso por definición; el atributo que piden obtener las tarjetas de estado del pedido es el estado. Ambas reglas se pre-registran.

**Cola de anotación manual.** Los casos sin resolver se presentan al autor sin indicar de qué condición provienen y en orden aleatorio con semilla fija; se anotan contra la base de conocimiento y la tarjeta, se guardan como tales y se reportan en el recuento.

**Conjunto manifestado.** El predicado se evalúa en las cinco ejecuciones candidatas y en las cinco de `baseline-a`. Un escenario expuesto pertenece al conjunto manifestado cuando la tasa de fallo del candidato supera a la de la referencia en al menos 0.4. Es la única condición. Se calcula además con 0.2 y 0.6 como análisis de sensibilidad.

## 6. Criterio de regresión (`agentproof/stats`, `agentproof/report`)

Un escenario se declara regresado si se cumplen las dos condiciones de la §5.5: la prueba exacta de Fisher de dos colas entre referencia y candidata es significativa tras la corrección de Benjamini-Hochberg con α = 0.05 sobre los escenarios comparados, y la caída absoluta de la tasa de aprobación es de al menos 0.4.

El reporte distingue tres estados:

| Estado | Condición | Código de salida |
|---|---|---|
| regresión | las dos condiciones | 2 |
| señal débil | caída ≥ 0.4 sin significancia | 0 |
| ok | el resto | 0 |

Con R = 5 y veinte escenarios, una comparación aislada no puede superar el primer umbral de la corrección (0.0025 frente a p = 0.0079 en el caso extremo): la declaración de regresión depende de que varios escenarios regresen juntos, y una caída aislada se reporta como señal débil (§5.5). Esto reemplaza al criterio provisional de F1, que usaba solo la caída.

La prueba de Fisher y la corrección se implementan sin dependencias nuevas.

## 7. Métricas (`experiments/analysis`)

- **Matriz de confusión** por operador sobre los veinte escenarios: es positivo el escenario con regresión manifestada y negativo todo el resto, esté o no expuesto. TPR y FPR salen de ahí (§5.5).
- **Desglose de falsos positivos** entre no expuestos y expuestos sin regresión manifestada.
- **Control negativo:** `baseline-a` contra `baseline-b` con el mismo criterio; todo escenario marcado es un falso positivo.
- **pass^k** como métrica de confiabilidad.
- **Distribución conjunta** de tasas de fallo de referencia y candidata por escenario y operador.

Las métricas principales se calculan sobre la familia A. La familia B se reporta aparte con su tamaño de efecto, y D3 solo como tamaño de efecto.

## 8. Repeticiones inválidas y reanudación (`agentproof/runner`)

Se implementa la regla [D-001](../decisiones.md): se reintenta una repetición que termine por fallo del usuario simulado, o cuyo juicio falle, con un tope de dos reintentos por repetición y cinco por par escenario-condición; nunca se reintenta un fallo atribuible al agente. La traza gana un campo opcional con el número de intento, los intentos fallidos se conservan y el reporte informa los reintentos por condición.

Una corrida interrumpida se puede reanudar sin repetir lo ya ejecutado: con ochocientas conversaciones por framework, una caída a mitad de camino no debe costar la corrida entera.

## 9. Costo y latencia por componente

El inductor, el usuario simulado y el evaluador registran los tokens que consumen, que hoy se descartan; el agente ya lo hace. El costo se reporta en tokens y en USD con una tabla de precios fechada, y se concilia con la facturación de la consola de Anthropic al cerrar el piloto: las cifras de la herramienta son cálculos propios y las del SDK del agente, estimaciones del cliente (§5.8, §7).

## 10. Pre-registro

`docs/preregistro.md` congela, antes de ejecutar cualquier experimento: los prompts y los modelos de los cuatro componentes, R = 5, el criterio de regresión, las reglas de exposición, los predicados y las reglas de extracción, la regla de agregación y los umbrales de sensibilidad, la regla de repeticiones inválidas y los conjuntos expuestos que resultan del corpus.

**Huella del protocolo.** Una prueba compara la huella de los prompts y los modelos con la que el pre-registro declara: cualquier cambio posterior al tag hace fallar la integración continua. Cambiar el protocolo sigue siendo posible, pero deja de ser posible hacerlo sin darse cuenta.

El tag `preregistro-v1` se pone con el corpus completo, porque los conjuntos expuestos dependen de las veinte trazas semilla.

## 11. Pruebas

- **Mutaciones:** `baseline` idéntica a la de hoy; cada mutación cambia solo lo que declara; la política de D4 cambia exactamente las siete decisiones previstas; cada edición aplica las seis.
- **Oráculo:** exposición por operador sobre trazas y tarjetas de prueba; extracción sobre respuestas reales del corpus y de la evidencia de F1; predicados; cola ciega con orden reproducible; conjunto manifestado con sus tres umbrales.
- **Criterio:** los valores p que cita la §5.5 (0.100, 0.029, 0.0079, 0.0022); la corrección sobre veinte comparaciones; los tres estados del reporte.
- **Runner:** reintento solo ante fallos de instrumentación, topes, reanudación sin duplicar.
- **Costo:** cada componente registra su consumo; los artefactos anteriores sin ese dato siguen leyéndose.
- **En vivo:** cada mutación produce el cambio que declara en el agente real.

## 12. Orden de construcción

| Parte | Contenido | Depende del corpus |
|---|---|---|
| A | mutaciones y condiciones | no |
| B | oráculo | no |
| C | criterio de regresión y métricas | no |
| D | repeticiones inválidas, reanudación y costo | no |
| E | pre-registro, tag y piloto | sí |

Cada parte se integra por separado y deja el repositorio en verde. Si la elicitación del corpus se retrasa, A–D avanzan con trazas de prueba y solo E espera.

## 13. Ajuste al ROADMAP

F3 cumple los ítems pendientes de su sección. El capítulo de diseño experimental de la tesis se redacta junto con la parte E, porque el pre-registro es su contenido principal.
