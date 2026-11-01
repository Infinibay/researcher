# Consulta de comandos y salidas por el propietario

El propietario puede recorrer los comandos de una ejecución y leer sus recibos
sin configurar el motor, reactivar al agente ni repetir una operación. El visor
está en el trabajo de la tarea y en sus ejecuciones históricas disponibles. Esta
entrega no amplía la admisión de herramientas de escritura ni migra los flows
heredados; tampoco completa la paginación del historial general de ejecuciones.

## API y alcance

| Lectura | Parámetros |
| --- | --- |
| `GET /api/projects/{p}/runs/{run}/jobs` | `after_seq=0`, `limit=25` —máximo100—; devuelve metadatos, total y `next_after_seq`. |
| `GET /api/projects/{p}/runs/{run}/jobs/{job}` | Offsets de stdout/stderr en bytes y `max_bytes=8192` —máximo16384 por stream—; devuelve argumentos, límites, estado y ambas ventanas. |

Ambas rutas requieren sesión del propietario. Un bearer de herramientas no permite
consultarlas. Proyecto, run y job se comprueban conjuntamente, incluidos los jobs de
otras tareas del mismo proyecto. La lectura del propietario sigue disponible después
de Stop, pérdida de lease o resultado desconocido; no reutiliza autoridad del agente.
Las respuestas usan `Cache-Control: no-store`. El API no agrega credenciales,
entorno ni rutas privadas de control al recibo. Los argumentos registrados se
muestran sólo al expandir su detalle, como evidencia reproducible.

La lista no devuelve cuerpos de stdout/stderr. Cada página usa un snapshot de lectura
para total y filas. El cursor es la secuencia durable del job en SQLite y debe usarse
literalmente; no es el ID del comando ni un contador de comandos de ese proyecto.
`seq` y `next_after_seq` viajan como strings decimales, preservando IDs de64 bits
que JavaScript no puede representar exactamente como números. Los metadatos
conservan intento/contexto y señalan si el registro pertenece a un
intento anterior. No se retiran recibos para hacer espacio en esta vista.

Cada consulta de salida extrae ventanas con `substr` sobre BLOB, sin cargar ni enviar
la salida completa. Offsets de entrada son cero-based; el visor etiqueta los bytes
mostrados desde1. `next_offset`, `total_bytes` y `has_more` describen los bytes
**guardados**, no toda la salida que el proceso habría producido sin límites.
SQLite devuelve NULL al aplicar substr a un BLOB vacío en este entorno; la proyección
lo normaliza a bytes vacíos. No convierte un resultado desconocido en éxito.

`command_output.output_window` comparte la representación entre el modelo y el
propietario: base64 exacto, vista UTF-8 y señal de decodificación con reemplazos.
Un carácter partido entre ventanas puede producir reemplazos aunque el stream
completo sea UTF-8 válido. Los bytes originales siguen accesibles. Una captura
limitada tiene una advertencia independiente: recorrer todas sus ventanas no
recupera el resto que nunca se guardó.

## Interfaz y significado de la evidencia

El panel se abre a pedido y permite paginar comandos, seleccionar un recibo y
recorrer cada stream, volver al inicio o consultar los últimos bytes directamente.
Los argumentos y el base64 se expanden por separado. No hay un control de
reejecución dentro del lector. Sigue accesible en tareas detenidas o con runtime
sin configurar, siempre que su historial se conserve.

La composición distingue código de salida, cierre local registrado y aceptación.
Un cero no valida el análisis. Cierre registrado no inventa el exit code de un job
unknown, ni autoriza controlar un proceso de una base copiada. La recuperación
mantiene sus comprobaciones independientes de origen/kernel/identidad.

El texto de salida se presenta como texto de React, no Markdown/HTML ejecutable.
Los controles de terminal y de dirección bidireccional se vuelven visibles como
escapes; el base64 mantiene el original. No se interpreta la salida como órdenes
para el usuario ni como contenido autorizado del proyecto.

Al cambiar proyecto/run/job se reinician selección, offsets y datos de transición.
Dentro del mismo job se conserva la ventana anterior mientras llega la siguiente,
con un aviso explícito y navegación deshabilitada durante esa transición. El
sondeo no mueve foco ni desplaza el scroll; el foco cambia al abrir una salida
por acción del usuario. Cerrar el panel deshabilita el sondeo de su recibo.
Fallos detienen el sondeo y ofrecen una nueva lectura, sin repetir trabajo.

## Evidencia y pendientes

Las pruebas HTTP en proceso cubren bytes inválidos, ventanas multibyte, salida de
4MiB con contraevidencia al final, paginación de27 jobs, scope, sesión/bearer,
unknown/NULL y validación de límites/identidades. Las pruebas SSR y del cliente
verifican escaping, etiquetas, controles de lectura, scope y transporte GET.
No prueban foco real, teclado, zoom, pantalla móvil o comprensión humana.

`evals/runtime/run_owner_command_inspection.py --source-root <ensayo-sintético>`
abre un servidor HTTP local sobre una copia de un ensayo anterior, con motor sin
configurar. Reconstruye exactamente los bytes del job nativo por ventanas de7,
comprueba restricciones HTTP y compara nueve tablas del original y la copia antes
y después. No genera inferencia ni toca una base de usuario. El ensayo no sustituye
una prueba de restore/transferencia de control ni aceptación visual.

Ver [evidencia](../modernization/owner-command-evidence.json),
[HTTP real](../modernization/owner-command-http.json) y
[resultados](../modernization/owner-command-results.json). El navegador sigue sin
estar disponible. Los escenarios productivos ampliados de Stop/corrección y las
otras herramientas, el engine y el rediseño completo siguen en el plan.
