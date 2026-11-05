# Consultar una publicación remota incierta

La recuperación consulta qué ocurrió con la **operación original**. No es otro
push, otro PR ni otro merge. La migración 46 guarda el cliente HTTP original y
los observadores nuevos sin cambiar las identidades de los efectos emitidos.

Ejemplo: el cliente envía A y se detiene antes de recibir respuesta. El servidor
termina después. Un observador nuevo encuentra el recibo de A y guarda ese hecho.
Si no lo encuentra, informa «incierto»: cerrar el cliente y recibir una consulta
vacía no demuestra que el servidor haya terminado o rechazado el efecto.

## Cierre antes de consulta

1. El scheduler retira el intento anterior y espera su worker local.
2. El host comprueba el scope HTTP del intento exacto. Se registra antes de la
   primera petición con PID, tiempo de inicio, kernel, namespace, fence y origen
   de la base. El controlador guarda cierre sólo después de cerrar su cliente.
3. Un proceso original todavía vivo sin cierre registrado bloquea recuperación.
   Tras un crash, ausencia o reemplazo de ese proceso en el mismo kernel/namespace
   puede probar cierre local. Visibilidad ambigua o namespace cambiado bloquean.
4. El journal global retira cada dominio Git original y comprueba todas sus
   operaciones. Peers de SQLite cerrados, por sí solos, no prueban este cierre.
5. Sólo entonces se crea otro intento/fence con autoridad de lectura.

El cliente HTTP pertenece exclusivamente al proceso confiable del host: no se
transfieren sus sockets a otros procesos. No se mata el servicio para comprobar
cierre. El resultado nunca afirma que se haya detenido el servidor remoto.
Intentos anteriores al esquema 46 sin identidad HTTP guardada no pueden adoptar
una identidad inventada retrospectivamente.

## Permiso nuevo y hechos conservados

`RemoteObservationLaunch` sólo admite el `ls-remote` de destino/recibo originales.
El broker distingue ese tipo de la autoridad del escritor. Su capsule sólo monta
el origen y `.git` en lectura con configuración segura; no requiere que siga
existiendo la carpeta del candidato. No admite push, fetch, stdin de transacción
ni comandos de modelo. HTTP usa GET para identidad, PR o registro de merge;
el hook rechaza cualquier POST y `RemotePublications.issue` rechaza al observador.

La identidad y registro del origen/remoto deben seguir coincidiendo. Una
corrección del contexto no impide consultar historia; sí impide adoptarla como
trabajo aprobado para el contexto nuevo. El recibo original positivo es inmutable.
El resultado de cada consulta conserva además el estado observado ahora.

Para merge se consultan por separado el recibo Git y el registro del mismo SHA
en Forgejo. Una etapa que nunca se emitió no se crea al recuperar. Un merge
parcial puede seguir pendiente: una acción explícita para esa etapa faltante
requiere implementación posterior, sin repetir las etapas ya emitidas.

## API y repetición

`POST /api/projects/{project}/remote-publications/{run}/recovery` usa pairing/CSRF
y sólo admite `operation_key`, `attempt_id`, `expected_fence`. Identidades,
credenciales, permisos y pruebas físicas se derivan del host.

El mismo comando completado devuelve su recibo guardado sin otra conexión. Una
consulta que sigue siendo incierta conserva su recibo separado y el run pendiente;
no autoriza reenvío. Si un observador se interrumpe antes del recibo, se inspecciona
el intento actual y su cierre antes de preparar otra consulta explícita.

## Evidencia y pendientes

[Resultados](../modernization/remote-recovery-results.json),
[wheel](../modernization/remote-recovery-packaging.json) y
[docstrings](../modernization/remote-recovery-docstrings.json). Pasan 88 casos
dirigidos; seis nuevos cubren autoridad, incertidumbre, cierre HTTP, rechazo de
push y repetición owner HTTP. Sus pruebas físicas sintéticas están etiquetadas.

La integración TLS ampliada usa Git real y API Forgejo controlada: detiene el
cliente, deja terminar al servidor, retira la carpeta del candidato y recupera
mediante un observador nuevo. También pierde la respuesta después de crear el PR
y registrar el merge y recupera ambos con sólo lectura. No aumenta los push/POST
ni los turnos de modelo;
repetir el comando no abre una consulta nueva. No prueba compatibilidad con un
binario Forgejo real ni una instalación completa del host.

Siguiente entrega: controles de Tareas con solicitud persistida. La adopción
explícita tras retirada, continuidad de un merge parcial, crashes ampliados e
inversas de migración siguen dentro del alcance completo.
