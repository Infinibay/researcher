# Entrada inicial registrada y continuidad de conversación

La migración 30 conserva lo que Researcher prepara para un intento: texto inicial
literal, hash, instrucciones de developer, su hash y catálogo de herramientas de
negocio. No reconstruye entradas antiguas a partir de respuestas. Tampoco captura
las instrucciones internas del proveedor, el catálogo MCP completo de Ken ni los
resultados posteriores de herramientas. Es un registro del host, no una prueba de
comprensión, aceptación, coste facturado o posibilidad de repetir el intento.

## Una operación antes de inferir

reserve_input reúne en una transacción la autoridad vigente, alcance del repositorio,
presupuesto, contexto actual, historia admitida, entrada exacta y evento input_frozen.
Si cualquier parte falla, no queda reserva o presupuesto parcial. El coordinador
entrega exactamente el texto devuelto por esa operación; no vuelve a consultar datos
para reconstruirlo después. El API anterior reserve_inference queda como primitiva
diagnóstica/compatibilidad y no genera nada; el camino productivo usa reserve_input.

Una reserva existente devuelve ausencia de permiso para despachar. No se repite ni
se inventa un input para una reserva histórica sin snapshot. Un comienzo no observado
sigue siendo desconocido ante una reserva previa; no se presenta como cero consumo.
Cambiar instrucciones/catálogo al reutilizar una reserva entra en conflicto. Los
registros rechazan UPDATE y sobreviven a ediciones posteriores de mensajes.

run_inputs.py reúne política de conversación, composición y límites; el adaptador SQL
conserva autoridad/persistencia. El coordinador recibe una entrada preparada en lugar
de conocer consultas, serialización y secuencia interna de guardado. Esta separación
aplica la reducción de acoplamiento temporal de la skill de A Philosophy of Software
Design revisada, sin crear otro loop de planificación o inferencia.

## Qué historial entra

El límite temporal es el mensaje de admisión de la solicitud actual, por ID estable.
Se incluyen mensajes anteriores de esa conversación/tarea y registros sin atribución
suficiente; no notas posteriores que el usuario aún no hubiera enviado al admitir.
Una ejecución sin vínculo de conversación lo declara, sin tomar el thread nativo como
si fuera el hilo del producto. La operación nueva no sustituye la política que impide
vincular una conversación nativa activa a otra tarea.

Si un hilo antiguo conserva mensajes vinculados a otra tarea, éstos se excluyen y se
cuentan explícitamente. Cada mensaje incluido conserva ID, contenido completo/hash,
emisor registrado, clase de procedencia, versión y estado de su run al capturar.
Las clases son owner_instruction, owner_answer, agent_question, agent_proposal y
unattributed_record. Una etiqueta user sin recibo nativo no prueba autoría del usuario;
una propuesta previa no pasa a ser evidencia verificada. same_context_version compara
versiones: no afirma aplicación, relevancia o comprensión.

La solicitud actual y las correcciones vigentes definen el trabajo. Se conservan
restricciones compatibles del historial, y las contradicciones relevantes se aclaran
con preguntas concretas. Ejemplos, correcciones y supuestos mantienen su fuerza y
procedencia al explicar el resultado. El prompt de integración sigue administrado en
código, separa esas secciones y añade casos reproducibles, en línea con la
[guía oficial de prompting](https://developers.openai.com/api/docs/guides/prompt-engineering).
El cambio no demuestra una mejora universal ni completa la revisión de todos los prompts.

## Límites explícitos

Hasta 200 mensajes anteriores y 1 MiB combinado de texto inicial, instrucciones y
catálogo de negocio. Son límites locales de registro/trabajo, no la ventana medida
en tokens de cada modelo. No se recorta el final de un mensaje ni se usa un resumen
LLM oculto. Si el contenido completo no cabe, se rechaza antes del turno y se conserva
una explicación; no se consumen una reserva o un turno para intentar un payload parcial.

La interfaz permite iniciar sin los mensajes anteriores como elección explícita.
Conserva tarea/correcciones/respuestas; el usuario debe poner las condiciones del
historial que quiera mantener en su nueva solicitud. Si lo excesivo es el propio
contexto de tarea, separar sólo la conversación no lo arregla: puede necesitar otra
tarea y, a futuro, un checkpoint de contexto con evidencia y aceptación explícitas.
El truncado silencioso no es una solución de continuidad.

## Consulta por el propietario

GET /api/projects/{p}/runs/{run}/input es lectura protegida/no-store. Presenta la entrada
preparada y si se observó el comienzo nativo. Falta de snapshot significa no_record,
incluso si un despacho antiguo tiene modelo o resultado. La UI no lo interpreta como
«no empezó», y no convierte «comenzó» en «comprendió». La consulta se hace al abrir el
detalle y se actualiza mientras está abierto. No puede reenviar ni aplicar el input.

## Evidencia y límites de aceptación

Pruebas con SQLite/coordinador/ASGI reales, inferencia doblada y puerto stdio real:
bytes entregados idénticos al registro, hash, límite al admitir, filtro de tarea,
procedencia, atomicidad, límites de bytes/mensajes, reserva incierta sin replay,
historia ausente y persistencia tras cambiar mensajes. Migración sintética v29→30
repetida preserva 110 tablas originales, sus valores y rowids disponibles; no fabrica
snapshots. No se abrió una base del usuario.

Prueba viva input-continuity-1 fff 674 c: dos turnos gpt-6.1-sol por Codex 0.166.0 y la
suscripción, Ken publicado 0.18.0 en workspace sintético. El primer turno usa base 137;
el segundo recibe dos mensajes históricos y una corrección user_example a base 200,
sin repetir 137 en la nueva solicitud. La explicación compara 28.77/165.77 con 42/242 y
distingue la política del defecto real del fixture. Ambos informes siguen draft, los
cuatro peers cierran, los grants se revocan y los fuentes no se editaron. Releer el
recibo no añade un turno. El registro original permanece idéntico después de corregir.

La respuesta correcta no prueba que el modelo usara exclusivamente el historial: sus
herramientas también podían leer datos del ensayo. Es un recorrido acotado, no un
benchmark estadístico ni una observación de comprensión humana. SSR/build no sustituyen
aceptación visual, teclado o lectores de pantalla. Quedan continuidad/compactación de
historial largo, revisión de todas las dependencias de contexto, procedencia de notas
heredadas, snapshots de otros tipos de entrada/efectos posteriores y la suite completa
de prompting/evaluación humana. Evidencia en docs/modernization/run-input-*.json.
