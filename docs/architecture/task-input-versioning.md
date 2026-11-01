# Versiones de entradas de tarea y retirada de autoridad

Editar una tarea puede cambiar el problema aunque el usuario no use el formulario
«Corregir contexto». Antes de la migración 29, una descripción modificada podía
conservar context_version=1 y terminar como propuesta vigente. Una prueba con
SQLite y el coordinador reales reprodujo ese resultado.

La nueva frontera está en SQLite para que alcance tanto la API como los escritores
heredados que hacen UPDATE tasks. Un cambio efectivo en cualquiera de estos campos
incrementa una sola versión por fila y sentencia:

- título, descripción, tipo, criterios de aceptación y context_json;
- prioridad, complejidad, rama, responsable y revisor;
- épica, hito y tarea principal.

Reasignar el mismo valor, incluyendo NULL→NULL, no crea otra versión. Un UPDATE
que cambia varios campos crea una versión con todos sus cambios. Estado, fechas,
contador de reintentos y recibos de PR son observaciones operativas separadas; no
se convierten en nuevas instrucciones por este trigger. Sus políticas de transición,
aceptación y candidatos de Git todavía tienen obligaciones propias.

## Un solo commit, con hechos diferentes

La escritura conserva antes/después y versión, retira grants, incrementa el fence de
los runs afectados, invalida propuestas/solicitudes en cola, deja las ejecuciones
activas en reconciliación y vence sus preguntas pendientes. El evento
context.task_inputs_changed se guarda en la misma transacción. Si falla el evento,
no se modifican tarea, versión, historial ni autoridad. Otros proyectos y tareas
conservan sus versiones.

La revocación durable impide nuevas herramientas/reservas con la versión anterior.
No demuestra que un proceso se haya detenido. La API notifica después del commit
al propietario local para interrumpir su worker; las escrituras externas/heredadas
se detectan también por la renovación de autoridad del coordinador (hasta cinco
segundos entre comprobaciones) y por la vigilancia de comandos registrados. La
parada física depende de los peers registrados y conserva el protocolo de cierre.
No se presenta una retirada de autoridad como confirmación de ese cierre.

El finalizador vuelve a derivar Stop/cambio de contexto del journal después del
cierre físico. Así, si la respuesta nativa llega antes que el heartbeat, no convierte
una propuesta obsoleta en needs_review. Sólo tras comprobar cierre puede quedar
superseded; Stop explícito conserva prioridad. Sin prueba de cierre sigue pendiente
la reconciliación. No hay replay, nueva inferencia, aceptación ni tarea done implícitos.

## Procedencia sin atribución inventada

Cada cambio se expone como task_metadata, con actor NULL. Se conoce la escritura y
sus valores; no se deduce quién la decidió. Una corrección explícita conserva su
propia clasificación user_message/user_example, referencia y versión. Ambas clases
comparten contador, pero los cambios de metadata no se fabrican como afirmaciones
del usuario ni evidencia científica.

Ejemplo: descripción «Base 100» → «Base 200» crea contexto 2. Un ejemplo explícito
«200 × 0.21 = 42» puede crear contexto 3 con procedencia user_example. El próximo
inicio explícito recibe la tarea actual, cambios y correcciones; una respuesta
pendiente bajo contexto 1 no autoriza actuar bajo el 3. La web muestra antes/después,
versión y autor no registrado; escapa contenido de tarea como texto.

context_snapshot incluye ahora los criterios y demás campos versionados; antes
sólo enviaba título, descripción, tipo y estado. Los cambios y correcciones se leen
en la misma transacción que los datos actuales. El historial previo a esta migración
permanece desconocido: no se inventan versiones ni autores retrospectivamente.

## Evidencia y límites

Las pruebas usan SQLite, filesystem, API autenticada y coordinador reales, con
inferencia doblada. Cubren los trece campos, no-op, dos campos en una sentencia,
rollback del evento, alcance, preguntas obsoletas, respuesta antes del heartbeat,
interrupción local, próxima entrega y rechazo de retiro sin peers cerrados. La
presentación se verifica con React SSR y contenido escapado, no mediante navegador.
Resultados y hashes: [evidencia](../modernization/task-inputs-evidence.json),
[resultados](../modernization/task-inputs-results.json),
[migración](../modernization/task-inputs-migration.json).

Esta frontera cubre escrituras UPDATE tasks, no toda dependencia del proyecto.
Cambios de dependencias, contenido de épicas/hitos/proyecto, adjuntos, fuentes,
archivos/Git y permisos necesitan sus propias revisiones y políticas de invalidez.
No se añadió un registro del autor verificado ni un snapshot completo del contexto
efectivamente enviado. También quedan comandos tipados de edición con control de
concurrencia/recibos, migración de los escritores heredados, paginación/retención del
historial, restauración verificable y aceptación humana/accesible en navegador.
Tener un número de versión no prueba por sí solo que todo el contexto esté congelado.
