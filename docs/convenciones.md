# Convenciones de trabajo

Reglas con las que se construye este repositorio. Provienen de la Sección 4 del [plan maestro](specs/2026-09-21-plan-maestro.md).

## Cuándo un paso está hecho

1. El comportamiento nuevo tiene su prueba, escrita antes que el código, y `uv run pytest` pasa.
2. `uv run ruff check .` y `uv run ruff format --check .` no reportan problemas.
3. La integración continua está en verde en GitHub.
4. Si el paso invoca un modelo de lenguaje, además pasa su prueba en vivo (marcada `live`). Esas pruebas se ejecutan a mano con la API key y no en la integración continua; la fecha y el costo de la verificación se anotan en el ROADMAP.
5. El ítem del [ROADMAP](ROADMAP.md) que cumple cita la sección de la planificación y se marca como hecho en el mismo commit que lo completa.

## Commits

- Una idea por commit, con su código y sus pruebas juntos, que pueda explicarse en una frase.
- Tamaño: en código, entre 50 y 150 líneas modificadas (código más pruebas, sin contar `uv.lock`); por encima de ~200 se divide por comportamiento. En documentos y en la tesis, una sección por commit.
- Cada commit deja el repositorio funcionando. No hay commits "WIP" ni commits que arreglan el anterior.
- Las dependencias se agregan en commits `build:` separados.
- Título: `tipo(alcance): resumen`, en minúsculas, sin punto final y con hasta 72 caracteres. El alcance es opcional.
- Tipos: `feat`, `fix`, `test`, `refactor`, `docs`, `build`, `ci` y `thesis`.
- Cuerpo: qué cambia y por qué. La última línea cita la planificación.

Ejemplo:

```
feat(judge): evaluador ciego a la condición del agente

El evaluador recibe solo la transcripción y los criterios del
escenario; la condición y el id de corrida nunca llegan al prompt.

Plan: §5.1
```

## Idioma

- Código, identificadores, docstrings y metadatos del paquete: inglés.
- Commits, ROADMAP, documentación y tesis: español.

## Ramas, pull requests y tags

- Una rama por fase: `f0-cimientos`, `f1-esqueleto`, …
- Al cerrar la fase se abre un pull request con el resumen y la lista de secciones de la planificación que cubre. Antes de integrar, el código se revisa contra esas secciones.
- La integración se hace con merge commit (`gh pr merge --merge`), nunca con squash ni rebase: así se conservan los commits pequeños y la fase queda visible como unidad.
- Tags obligatorios: `preregistro-v1`, antes del piloto, y `entrega-final`.

## Secretos

La API key de Anthropic se lee de la variable de entorno `ANTHROPIC_API_KEY`, definida en un archivo `.env` que git ignora. Nunca se escribe en código, commits ni documentos.
