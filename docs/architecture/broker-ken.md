# Ken publicado bajo el broker de procesos

`PeerBroker.run_ken` y `AsyncPeerBroker.ken` permiten ejecutar la preparación y
el servidor MCP de `ken-rank==0.18.0` dentro del dominio original del intento.
La preparación y el servidor tienen peers separados, ambos de tipo `ken`.
Comparten la reserva global, publicación, bind local y gate de los otros perfiles;
no se crea otro lanzador dentro del proceso Codex ni se interpreta Ken como shell.

## Identidad, fuente y modelos

El host exige una `KenInstallation` inspeccionada y el caché público para los
assets declarados. El manifiesto durable conserva instalación, modelos, modo,
perfil, hashes del worker/gate/perfil y límites. Reutilizar una clave devuelve
sólo el recibo; cambiar la intención con esa clave se rechaza.

La fuente se abre por descriptor y se compara con el binding admitido. Se monta
en `/run/researcher-source` en lectura; sólo `.ken` queda en escritura. Sustituir
el nombre del directorio después de preparar el perfil no redirige el proceso.
El hogar es temporal y no contiene credenciales del host. Los modelos se verifican
por tamaño/SHA-256 y se montan desde descriptores en lectura, con modo offline.
No hay descargas ni fallback sin aislamiento. El filtro deniega sockets de red
y Unix con dirección; admite `socketpair` privado para el self-pipe de asyncio.

La migración 31 amplía explícitamente el CHECK de tipos de `runtime_peers`.
Reconstruye la tabla en una transacción, conservando filas, rowids, columnas
adicionales, índices, triggers y referencias externas. Comprueba integridad y
restaura los PRAGMA originales incluso al fallar. No migra una base del usuario.

## MCP sobre las tuberías originales

`broker_mcp(endpoint)` usa `mcp.ClientSession` del SDK fijado, sin `stdio_client`
ni otro subprocess. El endpoint ya pertenece al broker. La entrada/salida usa
tuberías no bloqueantes y canales de ocho mensajes. Hay como máximo ocho
solicitudes simultáneas; el deadline incluye espera de escritura y resultado.
Los frames tienen un límite configurable de 1.024 a 1.000.000 bytes. Se drena
stderr con buffers fijos sin guardar diagnósticos crudos.

El adaptador valida los mensajes antes de pasarlos al SDK, cuyos errores de
validación podrían registrar contenido privado. Los errores de protocolo,
desconexión o timeout se convierten en `McpTransportError` sin el payload. Un
resultado MCP con `isError` sigue siendo un resultado explícito del servidor.
No hay retry automático de herramientas. Sampling, raíces y elicitación no se
habilitan. La sesión SDK se abre y cierra en la misma tarea por sus cancel scopes.

El cierre físico del peer precede la cancelación de las tareas de transporte.
Cerrar o cancelar esta sesión conserva los peers hermanos y la concesión del
intento; Stop del propietario sigue retirando todo el dominio. El broker conserva
supervisión y reaping, y proyecta el cierre sobre el peer de origen.

## Memoria: evidencia que cambió la política

La preparación real de Ken agotó el límite anterior de 512 MiB: exit 137,
`oom_kill=1`, pico exactamente igual al límite. El dominio se retiró y la fuente
quedó intacta. Con un límite explícito de 2 GiB, la misma preparación y búsqueda/
lectura funcionaron, con un pico aproximado de 1,29–1,30 GiB y sin OOM. Los
assets publicados suman 533.070.470 bytes en disco; ese tamaño no predice RAM.

`BrokerLimits` permite al host seleccionar, antes de la reserva, memoria de
64 MiB a 8 GiB y de 1 a 1.024 procesos. Conserva los valores predeterminados de
512 MiB/128 procesos y swap cero. La política es **compartida por todos los peers**,
se registra en la concesión y forma parte de la intención. Cambiarla dentro de
una concesión activa se rechaza antes de otra reserva/nacimiento. No es una opción
que pueda decidir el modelo. Los 2 GiB son evidencia de este ensayo pequeño;
falta medir la carga conjunta con Codex y herramientas antes de elegir producción.

## Alcance probado y siguiente integración

Las pruebas usan procesos reales para lectura, readonly, exclusión de credenciales,
socketpair, sustitución de rutas, recibos, cierre y MCP. Un ensayo separado con
el Ken publicado preparó el índice e invocó `ken_find`/`ken_read` sin error. Se
repitió desde un wheel extraído con imports aislados; ambos peers se cerraron y
el dominio se retiró, sin generación LLM ni imágenes.

Esto no sustituye todavía los lanzadores de `RuntimeService`. Faltan la mediación
del catálogo obligatorio de Ken, su composición con herramientas de negocio y
code-mode nativo, la prueba conjunta por suscripción y el aprovisionamiento/
inscripción del conjunto completo de actores del host. No prueba renovación
OAuth, transporte WebSocket del proveedor ni todas las capacidades del producto.

Evidencia: [ensayo publicado](../modernization/broker-ken-live.json),
[límites y contratos](../modernization/broker-ken-evidence.json),
[paquete](../modernization/broker-ken-packaging.json).
