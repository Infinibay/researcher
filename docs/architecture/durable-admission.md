# Admisión durable y comienzo explícito

La solicitud conserva el repositorio que se resolvió al admitirla. Releer un
recibo no vuelve a decidir dónde trabajar ni intenta arrancar una solicitud en
cola. El propietario tiene un control separado para solicitar ese comienzo.

La migración 28 agrega `runtime_workspace_bindings` e `issue_json`. En una sola
transacción se guardan run, selección solicitada, repositorio resuelto, nombre
histórico, path registrado, directorio canónico, dispositivo/inode, conversación,
recibo y evento. El vínculo es inmutable. Si falta el evento no se guarda una
admisión parcial. Un cambio del registro entre resolución y commit se rechaza.

La identidad de la petición incluye el repository_id explícito: con la misma clave
no se cambia de repositorio, incluso si otra elección resolviera la misma carpeta.
La selección automática también queda guardada; añadir otro repo después no la
vuelve ambigua ni la cambia. Los nombres históricos no se sustituyen por el nombre
actual. La vista pública muestra repo admitido y explicaciones, sin paths o inodes.

`WorkspaceRegistry` se separa del coordinador en `workspaces.py`; su import anterior
desde `service` permanece disponible. Revalida registro, alcance, dispositivo e
inode al programar, antes del claim y antes de reservar inferencia. El journal
comprueba además el vínculo al hacer claim y al reservar inferencia/comandos. Esto
detecta cambios observables de identidad bajo el mismo path; no mantiene abierto
un descriptor del directorio ni demuestra una generación global del filesystem.
No congela su contenido ni elimina todas las carreras entre comprobarlo y usarlo.

El [worker de Ken](ken-admitted-identity.md) comprueba además esa identidad sobre
su FD antes de crear estado y monta la fuente por descriptor. Es una frontera
concreta; no sustituye la propiedad/vista global de todos los actores.

## Releer y comenzar son acciones distintas

| Acción del propietario | Comportamiento |
| --- | --- |
| Primer POST válido | Admite una vez e intenta programar su inicio |
| Mismo POST/clave | Devuelve el recibo actual; no programa otra ejecución |
| Capacidad ocupada | Devuelve 202 con la solicitud guardada en cola y una explicación |
| Retry de inicio explícito | Revalida la selección original y el estado; no permite cambiar texto, repo o versión de contexto |
| Retry del mismo control tras perder la respuesta | Devuelve su recibo antes de comprobar precondiciones nuevas; no vuelve a programar |
| Fallo de preparación antes del claim | Permanece en cola, sin intento ni payload; permite otro control explícito |
| Registro/directorio cambiado | Conserva la solicitud y explica el bloqueo; no elige una carpeta sustituta |

El endpoint `POST /api/projects/{p}/runs/{run}/retry-start` recibe solamente
operation_key, expected_fence y context_version. Exige la sesión/CSRF del propietario;
campos como repository_id o request se rechazan. Sólo actúa sobre una solicitud
queued sin intento previo corriente. Un control confirmado que no pudo programar
trabajo no se reejecuta automáticamente; una nueva decisión explícita usa otra clave.
No hay un poller que vacíe la cola al liberarse capacidad.

El cliente conserva la clave, run, fence, contexto y proyecto del control mientras
la respuesta sea incierta. Consulta el mismo control; no reutiliza el proyecto que
se haya seleccionado después. Tras una respuesta confirmada puede emitir otra
decisión explícita. Se conserva el texto original, sin crear otro mensaje de chat.

Las solicitudes antiguas no tienen vínculo: la migración no inventa uno a partir
del catálogo actual. Sus recibos siguen legibles, incluso con la antigua identidad
que no incluía repo. Esto no verifica una selección histórica desconocida. La
respuesta y la interfaz la muestran sin registrar; no habilita un comienzo. Para
trabajar hay que cancelar la solicitud antigua y admitir otra comprobable.

## Explicar sin deducir un inicio

Las explicaciones llevan código estable, mensaje seguro, acción siguiente y
`inference_started`. False sólo se usa antes del despacho; NULL representa una
historia sin prueba suficiente o una reserva con inicio no confirmado; true exige observar el
callback de comienzo. Un fallo no revela el diagnóstico privado del proveedor.
No se transforma falta de respuesta en cero consumo ni en permiso para repetir.

El coordinador serializa programación y revalida que conserva propietario justo
antes de publicar el worker, sin un await entre ambos pasos. Una prueba detectó
que shutdown podía terminar durante la validación en un thread y quedar seguido
de un worker tardío; la comprobación final lo impide. El tipo de tarea se vuelve
a comprobar al reintentar y antes de inferencia; el retry no amplía capacidades.

## Alcance de las pruebas

[Evidencia](../modernization/admission-evidence.json),
[resultados](../modernization/admission-results.json) y
[ensayo de migración](../modernization/admission-migration.json) distinguen control,
datos y presentación. Las pruebas usan SQLite/filesystem/HTTP reales y doblan la
inferencia; no prueban calidad del modelo. No se ejecutó un nuevo turno generativo
ni se tocó una base del usuario. El frontend tiene pruebas de transporte y build;
la presentación, teclado y comprensión siguen pendientes de navegador/personas.

Quedan exclusión de workspaces entre bases, alias del lock de propietario,
transferencia/restauración verificadas y protección durante el uso del filesystem.
También quedan escritores heredados de tareas/contexto y la migración de herramientas.
La [migración 29](task-input-versioning.md) agrega una frontera transaccional para
los trece campos de entrada de tarea, incluso ante UPDATE heredados. No cubre
todas sus dependencias ni congela por sí sola todo el contexto del proyecto.
El vínculo persistido no es una prueba de quiescencia de otro despliegue ni una
versión de Git; esos contratos conservan sus obligaciones en el plan completo.
