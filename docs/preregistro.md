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
