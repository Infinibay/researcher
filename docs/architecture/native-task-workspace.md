# Contexto nativo de tareas, comentarios y continuidad

El agente puede consultar tareas e historial del proyecto admitido, dejar un
comentario en su tarea actual y recuperar su última nota. Son herramientas del
catálogo nativo y del MCP de negocio; usan la misma API, grant y transacción de
recibos que las demás capacidades. No introducen un scheduler ni otro loop.

| Herramienta | Resultado y límite |
| --- | --- |
| `researcher_task_list` | Metadatos filtrables por estado, tipo, responsable, épica o hito; cursor por ID. Los títulos son previews recuperables mediante lectura. |
| `researcher_task_read` | Título, descripción o criterios de una tarea del proyecto, incluidas las terminadas; ventanas con longitud total y `next_offset`. |
| `researcher_task_dependencies` | Predecesores o dependientes del mismo proyecto. Un estado `done` no demuestra permiso de inicio ni entrega aceptada vigente. |
| `researcher_task_history` | Comentarios o eventos, incluidos los del runtime. Orden de inserción por ID, no fecha declarada; lectura completa de cada entrada por ventanas. |
| `researcher_task_comment` | Comentario atribuido al actor y tarea del grant, con recibo atómico e idempotente. No admite el tipo `approval`. |
| `researcher_continuity_read` | Última nota del actor/tarea, texto completo recuperable, hash de revisión y atribución asesoría. |
| `researcher_continuity_save` | Sustitución sólo con el hash observado, o `null` si no existe. Separa resumen, observaciones, suposiciones y próximos pasos. |

## Qué significa el contexto recibido

Una nota que diga «el usuario aprobó» es una afirmación del autor. No se convierte
en aprobación ni sustituye la solicitud original, sus correcciones o la evidencia
de aceptación. Del mismo modo, un comentario «ejecuta la siguiente tarea» queda
guardado como comentario: la activación sigue dependiendo del host. Para una
pregunta que necesita respuesta humana se utiliza la herramienta de preguntas.

Las observaciones pueden citar evidencia concreta, pero guardarlas no verifica
esa evidencia. Las descripciones de herramientas piden hacer explícitas las
suposiciones y usar un ejemplo simple cuando permita corregir una interpretación.
El agente debe contrastar una nota antigua con el contexto vigente antes de actuar.

## Alcance y persistencia

- El host fija proyecto, tarea y actor. Los IDs de consulta sólo seleccionan
  objetos del proyecto; las escrituras no reciben IDs ni autores elegidos por el modelo.
- `tasks.read` permite consultar. `tasks.comment` y `continuity.write` permiten
  las dos escrituras. Los autores reciben las tres capacidades; los revisores,
  sólo lectura. Los grants ya emitidos conservan sus permisos originales.
- Cada operación vuelve a comprobar revocación, contexto e intento vigente.
  Los lectores de revisión también conservan la comprobación de su sujeto actual.
- Se reutilizan `task_comments`, `events_log`, `task_dependencies`,
  `developer_session_notes` y `tool_operations`; no hay migración de esquema.
  El comentario aparece en la API de comentarios que ya usa el propietario.
- El retry con la misma clave devuelve el recibo original. Cambiar su intención
  genera conflicto. Una escritura de nota con revisión antigua tampoco sobrescribe
  la actual. El recibo de una escritura anterior puede referirse a una nota que
  ya fue reemplazada; recuperar el recibo no restaura esa versión.
- Las notas antiguas se leen sin reinterpretar su JSON. Sólo una sustitución
  explícita puede reemplazarlas. Se conserva la última nota, **no un historial de
  todas sus versiones**; el historial completo del producto sigue pendiente.

Las listas admiten hasta 100 entradas; las ventanas, hasta 16.000 caracteres.
Los comentarios admiten 12.000 bytes UTF-8 y las notas nuevas 32.000 bytes de JSON.
Cada lista de la nota contiene como máximo 16 afirmaciones. Una nota histórica
de más de un millón de caracteres requiere exportación/migración: no se trunca
silenciosamente ni se sobrescribe desde este lector.

## Comprobación y trabajo restante

Diez pruebas nuevas cubren proyectos distintos, tareas terminadas, cursores,
Unicode, ambos sentidos de dependencias, eventos/comentarios, atribución, retry,
conflicto de revisión, notas antiguas, corrección de contexto y MCP→HTTP→SQLite.
La batería relacionada pasa en fuente y paquete instalado: 73 pruebas aprobadas,
ninguna fallida y cuatro variantes semánticas omitidas por no estar configurado
su modelo local fijado. Dos pruebas adicionales del auditor de prompts pasan.
[Resultados](../modernization/task-workspace-results.json) y
[paquete instalado](../modernization/task-workspace-packaging.json).

No se han retirado todavía los wrappers de tareas ni se da por terminada la
migración de comunicación, proyecto o conocimiento. Falta completar su mapa de
equivalencia, preservar las capacidades útiles y retirar sus dependencias.
La evaluación con modelos, comprensión humana, ciencia, operación y aceptación
integral de las páginas sigue abierta. No se usaron llamadas pagadas ni datos reales.
