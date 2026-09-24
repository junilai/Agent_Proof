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

## Uso

La clave de la API de Anthropic va en un archivo `.env` en la raíz del repositorio, con la línea `ANTHROPIC_API_KEY=<su clave>`; git lo ignora. El agente del caso de estudio se indica con el adaptador de su framework y su constructor como `modulo:atributo`; el adaptador de Claude Agent SDK necesita el extra `claude-sdk`, que el entorno de desarrollo ya incluye.

```bash
# graba una conversación con una persona como traza semilla
uv run --env-file .env agentproof record --adapter claude_sdk \
  --agent casestudy.editions.claude_sdk:build_options --data datos

# induce los escenarios que faltan
uv run --env-file .env agentproof induce --data datos

# reejecuta los escenarios con el usuario simulado
uv run --env-file .env agentproof run --adapter claude_sdk \
  --agent casestudy.editions.claude_sdk:build_options --condition baseline-a --data datos

# juzga una corrida y compara dos
uv run --env-file .env agentproof judge --run <corrida> --data datos
uv run --env-file .env agentproof report --baseline <corrida-a> --candidate <corrida-b> --data datos
```

`--data` es la carpeta que guarda `corpus/` y `results/` (por defecto, la actual). `run` repite cada escenario 5 veces con un presupuesto de 10 turnos (`--repetitions`, `--turn-budget`). `report` termina con 2 si detecta regresiones, con 0 si no y con 1 ante un error de uso.

Las pruebas en vivo llaman a la API real y tienen costo; se excluyen por defecto y nunca corren en integración continua:

```bash
uv run --env-file .env pytest -m live -s
```

## Documentación

- [Planificación aprobada](docs/planificacion.pdf): qué se construye y se demuestra.
- [Plan maestro](docs/specs/2026-09-21-plan-maestro.md): cómo se construye.
- [ROADMAP](docs/ROADMAP.md): estado del trabajo.
- [Convenciones](docs/convenciones.md): reglas de verificación y de commits.
- [Protocolo de elicitación](docs/protocolo-elicitacion.md): cómo se obtienen las conversaciones del corpus.
- [Decisiones](docs/decisiones.md): decisiones de diseño que no se deducen del código, con su motivo.

## Licencia

El código se distribuye bajo la [licencia MIT](LICENSE). El documento de tesis está sujeto además a la Política de Propiedad Intelectual de la USFQ.
