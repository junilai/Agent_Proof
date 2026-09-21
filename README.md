# AgentProof

Inducción automática de escenarios multi-turno desde trazas de interacción y reejecución adaptativa con usuarios simulados para la detección de regresiones en agentes basados en LLM.

Proyecto integrador de Ingeniería en Ciencias de la Computación, Universidad San Francisco de Quito USFQ, 2026. Autor: Jarod Tierra Medina. Tutor: Ricardo Flores Moyano.

## Qué hace

AgentProof toma conversaciones reales con un agente y, de cada una, induce un escenario de prueba: el objetivo del usuario, un mensaje inicial y criterios verificables de éxito. Después reejecuta ese escenario contra otra versión del agente mediante un usuario simulado que adapta la conversación a lo que el agente responde. Un evaluador ciego califica cada conversación, y el reporte compara versiones y termina con un código de salida apto para integración continua cuando detecta una regresión.

## Estado

En desarrollo. El avance por fases está en [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Desarrollo

Requiere [uv](https://docs.astral.sh/uv/); Python 3.12 se instala automáticamente.

```bash
uv sync                        # entorno y dependencias
uv run pytest                  # pruebas
uv run ruff check .            # análisis de estilo
uv run ruff format --check .   # formato
```

## Documentación

- [Planificación aprobada](docs/planificacion.pdf): qué se construye y se demuestra.
- [Plan maestro](docs/specs/2026-09-21-plan-maestro.md): cómo se construye.
- [ROADMAP](docs/ROADMAP.md): estado del trabajo.
- [Convenciones](docs/convenciones.md): reglas de verificación y de commits.

## Licencia

El código se distribuye bajo la [licencia MIT](LICENSE). El documento de tesis está sujeto además a la Política de Propiedad Intelectual de la USFQ.
