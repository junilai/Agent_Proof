# Protocolo de elicitación del corpus semilla

Cómo se obtienen las veinte conversaciones que originan la suite de pruebas (§5.2 de la [planificación](planificacion.pdf)).

## Qué son estas conversaciones

Son **interacción elicitada**: personas reales conversando con el agente del caso de estudio a partir de una situación que se les entrega. No provienen de un sistema en producción ni de usuarios finales, y el documento de tesis nunca las llama tráfico de producción. La generalización hacia tráfico de producción se declara como limitación del estudio.

De cada conversación se induce exactamente un escenario, así que las veinte conversaciones producen los veinte escenarios sobre los que se aplica el análisis estadístico. El número es fijo: si una conversación no permite inducir un escenario utilizable, se elicita otra hasta completar veinte.

## Participantes

Entre cuatro y seis personas: el autor y estudiantes de la carrera ajenos al proyecto. Cada sesión dura unos diez minutos y cada participante puede atender varias tarjetas en una misma sesión.

## Materiales

- Una [tarjeta de situación](../src/experiments/cards.py) por conversación, de las veinte del catálogo.
- Una terminal con el proyecto instalado y la clave de la API configurada.

## Antes de empezar

Se le dice al participante, en estas ideas y con sus propias palabras:

1. Va a conversar por escrito con un agente automático de atención al cliente de una tienda de electrónica ficticia.
2. Va a recibir una situación. Que converse como lo haría en la vida real para resolverla; no hay respuestas correctas ni incorrectas, y no se evalúa a la persona sino al agente.
3. La conversación se guarda y **se publica en un repositorio público**, junto con el resto del trabajo.
4. Que **no escriba datos personales reales**: ni su nombre, ni correos, ni números de cédula, ni teléfonos. Si el agente se los pide, puede inventarlos.
5. Puede detenerse cuando quiera y pedir que esa conversación no se use.

Que confirme que está de acuerdo antes de empezar. La sesión no registra la identidad del participante: en la traza solo queda el identificador de la tarjeta.

## Durante la sesión

Se graba con el comando, indicando la tarjeta:

```bash
uv run --env-file .env agentproof record --adapter claude_sdk \
  --agent casestudy.editions.claude_sdk:build_options --card tc-01 --data .
```

Una línea vacía termina la conversación. Cada respuesta del agente tarda unos segundos.

Durante la conversación **no** se hace nada de esto:

- decirle al participante cómo conversar, qué tono usar o qué preguntar;
- mostrarle la política de reembolsos de la tienda;
- corregir al agente, sugerirle respuestas o intervenir si se equivoca;
- pedirle al participante que repita la conversación porque "salió mal".

Que el agente falle es información válida: de eso trata el trabajo.

## Después de cada sesión

1. Revisar la cobertura:
   ```bash
   uv run python -m experiments.coverage --data .
   ```
   El informe dice qué tarjetas faltan, qué grabaciones quedaron sin tarjeta y cómo van los conjuntos expuesto y de control de los operadores de degradación.
2. Leer la conversación guardada. Si contiene por descuido un dato personal, se elimina esa traza y se elicita un reemplazo con la misma tarjeta.
3. Si la conversación terminó por un fallo de la herramienta, o quedó tan corta que no permite inducir un escenario, se repite la tarjeta.
4. Comparar el desenlace con el resultado esperado de la tarjeta. Si no coinciden, distinguir dos casos:
   - **el agente decidió mal**: la conversación se conserva, porque es justo la evidencia que el trabajo busca capturar;
   - **un dato que la tarjeta daba por sentado nunca salió en la conversación** (por ejemplo, el motivo en una tarjeta donde el motivo cambia el resultado): se elicita un reemplazo con la misma tarjeta, porque esa conversación no pone a prueba lo que la tarjeta pretendía.
5. Si al completar las veinte algún conjunto de control quedara vacío, se elicitan conversaciones adicionales con tarjetas que lo llenen, como prevé la §5.2 para las conversaciones que no sirven.

## Qué queda registrado

El agente no sabe con qué tarjeta se está conversando: recibe únicamente los mensajes que la persona escribe. La tarjeta la lee el participante y su identificador se guarda en la traza, pero nunca llega al modelo, ni en la grabación ni en las reejecuciones ni en el juicio. Cada conversación se ejecuta además en una sesión nueva y aislada, así que el agente tampoco recuerda las conversaciones anteriores.

Cada conversación se guarda en `corpus/seeds/` con sus mensajes, las llamadas a herramientas del agente, el motivo de terminación, los modelos usados, el consumo y el identificador de su tarjeta. Los atributos de la tarjeta (intención, tono, resultado esperado y pedidos) quedan fijados antes de inducir nada, y por eso pueden usarse después como verdad de referencia independiente del sistema evaluado.
