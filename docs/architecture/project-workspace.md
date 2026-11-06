# Expediente del proyecto y control de trabajo observado

Proyectos muestra el alcance guardado, fuentes admitidas y enlaces a decisiones
originales. La etiqueta del proyecto, la actividad de un intento y la vigencia de
un informe son observaciones distintas. Elegir un proyecto no inicia agentes.

## Lectura y autoridad

`ProjectWorkspace` recibe el store existente, la política real de carpetas y la
consulta de controladores anteriores registrados. `GET /api/projects/{id}/workspace`
proyecta metadata/hash, historia, fuentes, intentos activos o sin cierre, grafos
activos, solicitudes originales de planificación y recibos de cierre. Los enlaces
incluyen proyecto, tarea y `planRun`; Tareas verifica ese alcance. No elige una
investigación por fecha. Un recibo de cierre anterior se muestra como historia;
la vigencia completa se vuelve a comprobar al abrir su informe original.

El límite es256registros por conjunto observado. Si no cabe todo, la consulta
rechaza sin omitir objetivos ni elegir arbitrariamente un plan. Sin raíz real de
runtime, la disponibilidad física es desconocida. Un error de consulta no se
presenta como ausencia de carpetas o de historia. El listado conserva su propia
lectura y errores. La respuesta de workspace no se almacena en caché HTTP.

## Crear, editar y registrar una fuente

La creación guarda nombre, descripción y clave original inmutables en
`projects.metadata_json.owner_creation`, dentro del write lock existente. Reenviar
la misma intención devuelve el mismo ID mientras el recurso existe, incluso tras
editar sus datos. Misma clave y otro alcance rechaza. La web persiste el paquete
antes del POST y recupera su recibo tras recarga o respuesta perdida. No inicia
inferencia ni crea carpetas/repositorios. La compatibilidad sin clave se conserva
para consumidores antiguos; no ofrece aquella garantía de recuperación.

La edición incluye el hash del nombre/descripción/descripción original observados.
Se compara dentro del mismo `BEGIN IMMEDIATE` que escribe: una edición concurrente
rechaza el editor obsoleto. La descripción original y las decisiones previas se
conservan; editar metadata no modifica un intento ya admitido. Cambiar de proyecto
desmonta su editor para evitar transferir un borrador a otro alcance.

`POST /{id}/sources` registra exclusivamente una carpeta absoluta ya existente,
con nombre/ruta explícitos, bajo la política real de `WorkspaceRegistry._bind`.
Validación e inserción usan la misma transacción. Repetir la selección devuelve
el mismo recurso; una selección distinta, archivada, ajena o fuera de política
rechaza. No crea `.git`, clona, configura origin, contacta remotos ni modifica
archivos. Que la carpeta esté disponible no prueba salud Git o remota: se devuelve
`git_state=not_checked`. Inicializar/clonar/crear/adoptar/reparar repositorios es
una capacidad principal pendiente, no un resultado implícito de este formulario.

## Planificación y Stop

La web pide una fuente concreta y usa el start nativo original. Si se perdió una
respuesta, el paquete guardado y su fuente prevalecen sobre otra selección visual.
Mientras esta vista observa trabajo, dirige al intento original antes de iniciar
otro. Planificar propone; aceptar un grafo, ejecutar y aceptar entregas son pasos
distintos. La etiqueta registrada puede ser planificación sin ser executing.

Stop congela los IDs/revisiones de grafos e intentos observados y su hash. Dentro
del write lock existente, `request_stop` compara el alcance, pausa sólo esos
grafos, retira sólo esos intentos mediante `SQLiteRunStore._cancel`, registra
estado/evento y guarda el recibo original en `runtime_commands`. Después la API
pide al runtime original que cierre los trabajadores capturados. Un reenvío lee
primero el recibo: no enumera ni detiene trabajo nuevo. El recibo expresa
`closure=unconfirmed`; la vista exige consultar el cierre. No hay otro scheduler,
loop de inferencia, tabla de órdenes o prueba de cierre derivada del texto.

Un controlador antiguo registrado conserva su control compatible explícito; un
fallo de respuesta no autoriza un reintento ciego sobre otro dueño. El ensayo
instalado de Stop utiliza el kernel/broker real y comprueba cierre y retiro de la
concesión global. La generación y Ken de esa prueba están controlados.

## Conservación y límites de ciclo de vida

El borrado exige ausencia de historia runtime/agent_runs/flow_snapshots/agent_events
bajo el mismo write lock de admisión. La API vuelve a comprobarlo aunque la UI
haya mostrado un recurso sin historia. El diálogo tiene foco inicial en Conservar;
confirmar elimina sólo metadata del proyecto, sin borrar carpetas. El borrado
antiguo consultaba una tabla agent_roster inexistente y una columna project_id
inexistente en developer_session_notes; ahora usa el esquema real y conserva las
estadísticas globales de agentes.

La intención original de creación vive en el recurso: eliminar definitivamente
un proyecto sin historia elimina también esa intención. Un reenvío posterior de
una creación perdida podría crear otro ID. Hace falta decidir y probar la
retención de identidades/tombstones durante el ciclo de vida antes de aceptar la
integración completa. No se afirma idempotencia universal tras borrado/restore.
No se cambia silenciosamente el contrato de hard delete en esta entrega.

[Resultados acotados](../modernization/projects-results.json),
[QA y procedencia visual](../design/audits/2026-11-06-projects/report.md).
No prueban comprensión humana, calidad del modelo/ranking, restore, aceptación
visual completa ni cumplimiento íntegro del plan.
