# Creación de tareas del propietario

POST /api/tasks crea metadatos y dependencias; nunca admite una ejecución.
El cliente web guarda su cuerpo original y operation_key antes del primer envío.
Reenvío de la misma clave/cuerpo/proyecto recupera el recibo original201. Cuerpo o
kind distinto409; tarea retirada después409sin recrearla. Una edición posterior
no altera el recibo ni se revierte al recuperarlo. GETdel detalle muestra el estado
actual. Usuarios antiguos sin clave conservan una creación por llamada, sin
promesa de recuperación tras pérdida de respuesta.

OwnerPlanningRecords comparte BEGIN IMMEDIATE con la creación de grupos/hitos.
Todo padre y dependencia debe pertenecer al proyecto; hito/grupo explícitos deben
coincidir. La inserción de tarea, aristas, auditoría del trigger y recibo se confirma
o revierte junta. Tareas AUTOINCREMENT impiden reutilizar el ID retirado.
complexity es el campo canónico; estimated_complexity es alias compatible. Si se
proporcionan ambos y difieren, se rechazan en vez de elegir silenciosamente.

Migración70 amplía los kinds de owner_planning_commands conservando sus registros.
restore_task_commands_schema sólo vuelve a69sin recibos task.create ni versiones
posteriores. No elimina solicitudes usadas o historial para hacer pasar inversas.
El ensayo completo de inversas sigue como gate final separado.

TaskCreationForm conserva una intención por proyecto y valida el recibo antes de
retirar su copia exacta. Un formulario desmontado puede conservar una copia aun
cuando la respuesta llegó a la red; al volver se recupera explícitamente con la
misma clave, sin crear otra tarea. Cambio de instalación usa el archivo existente
de prefijos researcher:. Descartar copia es explícito y no revierte una creación.

[Pruebas y límites](../modernization/task-creation-review.md). No aceptación completa
de Tareas, comprensión humana o nueva calidad generativa por este cambio.
