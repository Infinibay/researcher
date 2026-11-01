# Jobs nativos con dueño y recibos durables

La migración 20 incorpora `runtime_jobs`. `OwnedCommandExecutor` usa una conexión
nativa dedicada a un intento; `command_executor` compone el proceso privado y su
perfil de permisos. La integración productiva de análisis utiliza un peer por job,
descrito en [host-analysis-tools.md](host-analysis-tools.md). Los flows antiguos
siguen activos en sus rutas; no heredan estos controles sin migrar sus consumidores.

## Autoridad y efectos

Antes de enviar `command/exec`, SQLite registra identidad de run/intento,
contexto, fence, conexión, operación e intención. La misma operación devuelve el
recibo anterior; cambiar sus argumentos produce conflicto. Un job incierto o
activo impide otro despacho. Reabrir el backend nunca repite un comando perdido.

El `processId` es el UUID de job elegido por el host y vive en esa conexión; no
es un PID del sistema. El peer pertenece a un intento, no a un singleton global.
Stop, corrección y vencimiento retiran autoridad para nuevos efectos. Un hecho
tardío del dueño original puede cerrar el recibo, pero no recuperar autoridad ni
marcar la tarea como aceptada. Observar el vencimiento lo persiste: atrasar el
reloj después no revive el permiso. Los tiempos de espera locales son monótonos.

La petición de terminación física se envía en paralelo con la persistencia de
su intención. Esperar primero por el writer de SQLite permitía que el comando
hiciera su escritura diferida mientras la DB estaba ocupada. El recibo terminal
espera ambas operaciones; una confirmación de control sola no demuestra salida.
La pérdida de la conexión produce `unknown`, reconcilia el run y revoca sus
grants en la transacción que guarda esa observación. Nunca se informa éxito.

## Salidas y aislamiento

Cada stream conserva bytes hasta el límite explícito. Alcanzarlo solicita
parada y queda registrado. La respuesta RPC lleva el número de notificaciones
que la precedieron; se drenan antes de persistir salida terminal. Así, una cola
lenta no descarta la contraevidencia al final. La DB conserva la salida canónica;
los buffers en memoria se liberan y la cantidad de handles recientes es acotada.

El peer de comandos usa HOME/CODEX_HOME temporal sin cuenta, credenciales,
configuración heredada ni MCP. El host selecciona un workspace, lectura mínima,
binario explícito y toolchains de sólo lectura; la red está deshabilitada. Se
valida configuración efectiva antes de admitir comandos. El diseño usa perfiles
nombrados de la [configuración de Codex](https://learn.chatgpt.com/docs/config-file/config-reference);
la evidencia de compatibilidad corresponde al CLI instalado 0.166.0. Su modo
estricto rechazó el alias `tools.view_image`; se usa `features.view_image=false`.
No extender estas restricciones a un MCP o proveedor externo por analogía.

`run_commands.py --live --peer-loss --db-contention` verificó con el ejecutor y
SQLite reales: homónimos en dos proyectos, rechazo de lectura cruzada pese a
config local hostil, rechazo de socket, Stop de hijo separado ya iniciado,
conservación del otro job, pérdida de peer y parada con writer ocupado. No se
envió ningún turno de modelo. Ensayos inválidos y límites permanecen en
`docs/modernization/owned-command-evidence.json`.

## Trabajo pendiente

Componer servicio de ejecución, auth HTTP/WS y control humano antes de exponer
jobs; recuperar dueños de procesos anteriores sin replay; migrar todas las
herramientas, presupuestos, aceptación Git y recorridos. Esto no demuestra Stop
para todos los flows antiguos ni aislamiento de cualquier servicio externo.
