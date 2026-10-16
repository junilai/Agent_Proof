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
