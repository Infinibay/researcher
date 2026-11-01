# Herramientas de análisis bajo propiedad del host

El runtime productivo con `AttemptPeers` ofrece quince herramientas dinámicas:
once de investigación/preguntas y cuatro de análisis. Ken sigue siendo el MCP
obligatorio, separado de este catálogo. `ProjectTools` une los schemas antes de
abrir el thread, rechaza nombres duplicados y fija el hash del catálogo combinado.
Reanudar una sesión exige el mismo catálogo registrado; no se agregan herramientas
a una conversación antigua silenciosamente.

## Alcance de esta migración

Esta entrega conecta cálculos y diagnósticos de investigación al ejecutor durable;
no completa la migración de las dos clases shell heredadas ni de sus consumidores.
El repositorio está montado en **sólo lectura** y cada comando tiene un peer
dedicado, sin cuenta, sin red y sin variables/credenciales heredadas. El modelo no
elige lease, fence, rutas privadas, perfil de permisos ni intérprete Python.
La edición, instalación de paquetes, librerías científicas adicionales y entrega
de archivos/gráficos producidos siguen pendientes, junto con la propiedad global
del workspace y la aceptación del candidato Git exacto.

El intérprete elegido por el host usa `-I -S -B`: no importa site-packages ni ejecuta
scripts de inicio del usuario. Se monta su toolchain explícita en lectura. Para
archivos temporales puede usar TMPDIR; se descartan al cerrar el peer. El montaje
del workspace, la red y el entorno efectivo se comprueban antes de command/exec.
No hay fallback a subprocess sin sandbox cuando el peer nativo falla.

## Contrato del modelo

| Herramienta | Entrada y resultado |
| --- | --- |
| `researcher_command_start` | Clave estable, argv explícito, cwd relativo, deadline y límite de salida; devuelve ID/recibo del job. No interpreta shell implícitamente. |
| `researcher_python` | Clave estable y código de biblioteca estándar; el host construye argv y devuelve el mismo tipo de job. |
| `researcher_command_read` | ID del job, offsets por stream, tamaño de ventana y espera acotada. Devuelve bytes exactos en base64 y vista UTF-8 con indicación de pérdida. |
| `researcher_command_cancel` | ID del job propio; cancela y cierra su peer, incluidos descendientes desacoplados. |

Schemas estrictos rechazan campos adicionales y coerciones como booleano por
timeout. Cada comando admite hasta 128 argumentos/65536 bytes, 300 segundos y
65536 bytes **por stream**. Cada lectura devuelve hasta 16384 bytes por stream y
espera como máximo 1000 ms. Estos límites locales no representan cuota de OpenAI.
Sólo un job no resuelto puede estar activo por run, como ya exige SQLite.

El resultado canónico de stdout/stderr se persiste al terminar; un job en curso
puede devolver ventanas vacías. `next_offset`, `total_bytes` y `has_more` permiten
seguir leyendo sin presentar una ventana parcial como salida completa. Base64
conserva los bytes incluso si una ventana corta un carácter UTF-8. Un límite de
captura se indica con `output_limited`; no equivale a haber recuperado toda la
salida que el programa habría producido sin ese límite.

## Autoridad, reintentos y cierre

Cada operación, incluidos lectores, verifica el control vivo y la autoridad durable
antes y después de ejecutarse. Un cambio de contexto, Stop o pérdida de lease
retira al lector del modelo; el propietario conserva su recuperación independiente.
Un ID de otro intento no sirve para leerlo ni cancelarlo, incluso en el mismo proyecto.

Antes de abrir otro peer, el host busca un recibo con la misma clave/intención.
Una repetición devuelve el job original. Argumentos distintos generan conflicto;
un job de conexión anterior sin cierre/resultado conocido exige reconciliación.
No se reenvía command/exec para reparar una respuesta perdida.

Al leer un resultado terminal se cierra el peer dedicado antes de devolverlo, para
retirar hijos cuyo padre ya retornó. Al terminar el scope se cierran también jobs
que nadie leyó. Cancelar un lector no abandona el context manager: el dueño conserva
y espera su tarea de limpieza. La prueba final del servicio sigue comprobando todos
los peers registrados, además de los indicadores de cierre de la sesión.

El registro distingue hasta ocho peers sin cerrar y hasta 128 recibos históricos
por intento. Antes contaba ocho filas en total; eso agotaba la capacidad al sexto
comando, aun estando todos cerrados. Cerrar libera capacidad física; no borra sus
recibos ni convierte un resultado desconocido en éxito.

`exit_code`, `local_execution_closed`, validez del cálculo y aceptación de la tarea
son hechos independientes. Perder un recibo conserva unknown/NULL. El cierre de
un namespace no inventa el exit code; un cero no aprueba un informe ni publica nada.

## Verificación y límites

`test_analysis_tools.py` usa SQLite, guards y subprocesses reales con un peer de
protocolo de prueba: verifica alcance, reintentos, cancelación, bytes y limpieza,
pero no demuestra el sandbox del CLI. `run_analysis_tools.py` usa el CLI fijado sin
inferencia para probar lectura/cálculo y bloqueos reales de escritura, otro proyecto,
symlink, red y entorno, incluso con configuración local que intenta ampliar permisos.

`run_analysis_inference.py --live` comprueba un turno autorizado por suscripción,
Ken obligatorio, catálogo combinado, cálculo ejecutado, informe borrador y cierre
de peers. Sus resultados se registran por separado; un ensayo no demuestra calidad
general de prompts, comprensión humana ni migración de todas las herramientas.
La UI de salida del propietario y la integración de los consumidores heredados
siguen pendientes. No se declara aceptación visual por estas pruebas.
