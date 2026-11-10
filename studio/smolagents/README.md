# La edición smolagents en su interfaz de Gradio

smolagents trae su propia interfaz de chat, `GradioUI`, que permite conversar con el agente del caso de estudio viendo cada paso: qué herramientas pide el modelo, con qué argumentos, qué devuelven, los errores y los tokens de cada llamada. La edición es `src/casestudy/editions/smolagents.py`; `app.py` la abre tal cual, sin cambiar nada de ella.

## Cómo abrirlo

Desde la raíz del repositorio:

```bash
uv sync --extra smolagents --group studio
uv run --env-file .env python studio/smolagents/app.py
```

Después, en el navegador, abrir <http://127.0.0.1:7860>.

- **Variante.** Por omisión se abre la línea base. Para ver una mutación, definir `VARIANT` antes de arrancar, por ejemplo `VARIANT=d6 uv run … python studio/smolagents/app.py` para ver el corte tras dos llamadas al modelo y la respuesta que smolagents fuerza después.
- **API.** Abrir la interfaz no usa la API. Conversar con el agente sí: cada turno cuesta lo mismo que en el experimento (Claude Sonnet 5), y la clave se lee de `.env`.
- **Solo local.** `app.py` escucha solo en `127.0.0.1` y nunca crea el enlace público de Gradio (`share=False`, aunque smolagents lo crea por omisión). También apaga la analítica de Gradio y la descarga del mapa de costos de litellm antes de importarlos.

## Lo que se ve

Por cada llamada al modelo, un bloque **Step N** con:

- la herramienta que pidió el modelo y sus argumentos (si pidió varias a la vez, la interfaz muestra solo la primera, aunque los registros de ejecución traen el resultado de todas);
- los registros de ejecución, con lo que devolvió cada herramienta;
- los errores, si los hubo, y los tokens y la duración de la llamada.

Al final, **Final answer** con la respuesta al cliente, que el agente da con la herramienta `final_answer` de smolagents. Al llegar al límite de pasos (10, o 2 en D6) aparece un paso con error y, después, la respuesta forzada.

Las equivalencias con las otras ediciones están en [D-012](../../docs/decisiones.md).

## Una conversación por arranque

La interfaz usa un solo agente, con una sola memoria, para todas las pestañas, y limpiar el chat no la borra. Para empezar una conversación nueva, detener el script y volver a arrancarlo.

## Cuándo no usarlo

La interfaz nunca corre durante una tanda del experimento: cerrarla antes de `agentproof run`. El adaptador, además, se niega a correr si litellm puede salir a un servicio de terceros.
