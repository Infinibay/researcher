# Código: Ken y edición en la copia privada

La ejecución nativa usa Ken para descubrir y leer código y los comandos poseídos
por el host para modificarlo. Se retiran 44 módulos: `backend/code_intel/`,
`backend/tools/code_intel/`, `backend/tools/file/` y los dos indexadores CLI sin
consumidores activos. También se retiran las seis dependencias directas
`tree-sitter*`. El extra `legacy` conserva otras bibliotecas hasta completar sus
migraciones. [Inventario de retirada](../modernization/code-operations-retirement.json).

## Destino de las capacidades

| Capacidad anterior | Recorrido actual |
| --- | --- |
| Definiciones, referencias, símbolos, estructura y lectura de código | Ken obligatorio del workspace admitido; verificar fragmentos y cobertura. Consultas vacías o relaciones incompletas no demuestran ausencia. |
| Lectura parcial, directorios, glob y búsqueda literal/regex | Ken cuando cubre la consulta; comandos/Python con lectura acotada en el mismo workspace para resolver dudas o formatos no indexados. |
| Escritura, append, reemplazo, inserción y edición múltiple | `researcher_python` o `researcher_command_start`, recibo original y `researcher_command_read`; sólo la copia privada de desarrollo es escribible. |
| Aplicar un diff | Git u otra herramienta disponible dentro del comando poseído, comprobando antes el patch y después el diff completo. No se conserva el intérprete casero de patches. |
| Añadir, editar, eliminar, renombrar o mover símbolos | Composición de lectura Ken, transformación explícita con herramientas locales, actualización de imports/callers, nueva lectura y comprobaciones. Ken no realiza esas escrituras. |
| Diagnósticos de imports/símbolos sin uso o no definidos | Relaciones de Ken y comprobadores del lenguaje disponibles/configurados. Declarar cobertura, falsos positivos y herramientas ausentes; no fabricar un resultado limpio. |
| Indexación al iniciar o cola de cambios | Preparación del Ken admitido y refresco tras cierre de escritores; no existe una segunda cola `ci_*`. |

Éste es un cambio deliberado de interfaz: no se conservan clases CrewAI ni sus
schemas de escritura como API compatible. El modelo elige una transformación
adecuada al lenguaje y al código leído. No se promete un rename semántico universal.
Las implementaciones antiguas también tenían límites: rename reemplazaba palabras
en líneas indexadas y move actualizaba imports por texto; podían omitir archivos
que no lograban leer/escribir. Esas heurísticas no se convierten en garantías del
recorrido nuevo.

## Resultado y límites observables

`test_native_code_operations.py` usa el request boundary del runtime con Git,
kernel, comandos y SQLite reales. Lee código, edita un método, añade otro, elimina
uno, cambia nombres y mueve una clase entre archivos; actualiza su consumidor y
preserva un literal que contiene el nombre anterior. Ken vuelve a prepararse al
cambiar el contenido. Después se ejecuta un turno nativo controlado, se captura el
SHA exacto y se comprueba el comportamiento del candidato. El original conserva
archivos y HEAD; la tarea no queda aceptada.

La generación y las respuestas de Ken son fixtures de protocolo que leen los
archivos reales. El ensayo demuestra la composición y los efectos, no la calidad
de un modelo ni la corrección de refactors arbitrarios en todos los lenguajes.
Las pruebas existentes de workspace/desarrollo/comandos cubren aislamiento,
autoridad, Stop, captura, salida y revisión de contexto. La evaluación real y la
aceptación integral siguen pendientes.

El inventario incluye imports absolutos/relativos y strings de módulo exactos de
todo `backend/`. Los únicos imports externos al conjunto retirado pertenecían a
tests antiguos. No demuestra ausencia de consumidores externos al repositorio ni
imports calculados arbitrariamente. Se retiran 17 pruebas de wrappers eliminados;
esa retirada no se cuenta como reparación de fallos.

Las tablas y filas `ci_files`, `ci_symbols`, `ci_references`, `ci_imports`,
`ci_diagnostics` y su FTS permanecen en la base. Esta entrega no migra ni destruye
sus datos; la política de migración/restore se verificará en su bloque principal.
La memoria técnica de Ken sigue separada de fuentes, citas y hallazgos científicos.

## Espera detectada durante la validación

La prueba alcanzaba el límite de 60 segundos durante el check, después de guardar
el candidato. El perfil de doce lecturas del registro retenido empleó 1,564 s;
1,450 s correspondieron a reinterpretar/verificar el historial. Se repetía ese
trabajo en numerosas lecturas internas del broker.

El registro ahora relee los bytes y reutiliza sólo un prefijo idéntico ya validado.
Revalida la inscripción del observador, los registros añadidos, las filas SQL y el
acuerdo entre ambos almacenes. No confía en mtime/tamaño, no omite fsync ni altera
el formato durable. El buffer está limitado a 8 MiB; historias mayores conservan
la validación por streaming. El checkpoint/capacidad global sigue siendo trabajo
de operación. Las nuevas pruebas cubren append desde otro handle, alteración con
igual longitud/timestamp, cambio de observador y el límite del buffer.

La batería ampliada reveló además tres fallos al arrancar el broker con `-I -S`:
`backend.git` inicializaba servicios web y cargaba Pydantic indirectamente. El
paquete raíz ahora sólo contiene documentación; la API importa los mismos
servicios compartidos desde `backend.git.services`. Las tres recuperaciones y la
lectura HTTP histórica pasan con esa composición explícita. No se mantienen los
exports de instancias en el paquete raíz, que colisionaban con módulos homónimos.

[Resultados de fuente](../modernization/code-operations-results.json): 153 casos
distintos con última observación satisfactoria en dos baterías; no es una nueva
suite global. [Paquete instalado](../modernization/code-operations-packaging.json):
73 pruebas pasan, sin omisiones, y 757 fuentes coinciden con el wheel final.
[Medición aislada](../modernization/code-operations-journal-benchmark.json): veinte
lecturas del mismo corpus sintético pasan de 0,196 s a 0,064 s; no es una medida
de rendimiento global. [Docstrings](../modernization/code-operations-docstrings.json).
