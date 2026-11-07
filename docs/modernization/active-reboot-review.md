# Reinicio real con un comando activo

La VM se reinició mientras seguían vivos el preparador original, el init del
namespace del peer de comandos y el comando hijo. Tras restaurar los datos,
conservó el cálculo terminado (`200`), la instrucción y la corrección del usuario.
El comando interrumpido quedó con resultado desconocido y no se repitió.

Se corrigió una omisión de la reinscripción: los jobs copiados podían conservar
un estado que parecía ejecución actual. Ahora los estados `dispatching` y
`cancelling` pasan a `unknown`, con el estado anterior registrado en
`historical_work.jobs`. Se conservan salidas, errores e intención de cancelar;
los comandos terminados mantienen su recibo íntegro. No cambia la base original
ni se inventan salida, aceptación o prueba de cierre. No requiere migración SQL.

## Qué se ejecutó

El evaluador usa el wheel instalado, el Codex CLI real en modo comandos y los
recursos públicos de Ken verificados. El invitado no tiene tarjeta de red ni
credenciales reales. No se solicitó inferencia de modelo.

1. Crear una instalación sintética y registrar una corrección de contexto.
2. Ejecutar mediante Codex un cálculo que termina con salida200 y código0.
3. Iniciar otro comando y observar su salida de preparación mientras sigue vivo.
4. PID1 comprueba las identidades vivas y reinicia el mismo invitado, sin cerrar
   primero el preparador. Un único proceso QEMU atraviesa ambos arranques.
5. El segundo arranque rechaza la autoridad anterior para uso normal. Ejecuta
   los comandos públicos de backup tras reboot, verificación, restauración y
   reinscripción con autoridad nueva.
6. Comprueba el cálculo terminado, resultado desconocido del comando interrumpido,
   contexto original y tres peers archivados con sus estados anteriores.
7. Arranca el servicio instalado, lee tareas y un adjunto por HTTP y cierra servicio
   y VM. El proceso no-op de comprobación también confirma su cierre.

| Registro | Base original | Copia reinscrita |
| --- | --- | --- |
| Cálculo terminado | `exited`, código0, salida200 | Recibo idéntico |
| Comando interrumpido | `dispatching`, sin código final | `unknown`, sin código final |
| Peer de comandos | `bound`, kernel anterior | Mismo estado y origen, más procedencia archivada |
| Instrucción y corrección | Versión2 | Conservadas; sin replay |
| Despachos de modelo | 0 | 0 |

Se extrajeron en modo de sólo lectura las dos bases del disco conservado y se
comprobaron independientemente identidades, estados, salida, corrección, integridad
y claves foráneas. La comprobación no depende únicamente del `status: passed`
del evaluador. [Inspección del disco](active-reboot-disk-inspection.json),
[recibo de VM y validación](active-reboot-results.json).

## Evidencia y fallos conservados

Bloque medido08:26:45–08:42:42UTC: **15min57s**, hasta el corte de validación y registro.

Tres regresiones reprodujeron la omisión de estado/historial de los jobs copiados;
las tres pasan con el cambio. La ejecución dirigida final tiene30 casos:27 pasan
y3 fallan en preparaciones históricas de esquema ya registradas en la suite global
anterior. El wheel reproduce24 aprobados y los mismos3 fallos; no es una suite verde.
Coinciden607 archivos Python/SQL,324 productivos.
[Paquete y nombres exactos](active-reboot-packaging.json).

La primera VM terminó antes de iniciar el peer: el evaluador esperaba un objeto
en una función interna que devuelve el número de versión. Se corrigió esa llamada
y se creó una VM nueva, conservando el disco/log anteriores. La segunda pasó en
23,95segundos incluyendo preparación y ambas fases. La duración completa del
bloque se registra aparte. Un error de ruta relativa en el extractor se corrigió
releyendo el mismo disco, sin volver a ejecutar la VM.

Las guardas rechazan identidades de proceso cambiadas o terminadas y una invocación
accidental del init en el host antes de llegar a syscalls de administración.
Se comprobaron23 definiciones con docstrings. Los avisos de estilo se mantienen
en DD086 para después de todas las capacidades principales.

## Alcance que permanece abierto

El ensayo demuestra un reinicio controlado de este invitado y recuperación de
sus datos sintéticos con un comando activo. No cubre pérdida de energía,
inferencia de modelo dentro de la VM, formatos/datos históricos del propietario
ni recuperación distribuida. La prueba previa de caída del servicio sí usó
inferencia real; no se intercambian sus alcances.

**Archivado no significa cerrado.** Un identificador de kernel diferente puede
pertenecer a otra máquina. Los datos copiados no constituyen una prueba general
de muerte del host original, aunque en este ensayo el controlador observó el
reinicio del mismo proceso QEMU. No se debilitan las guardas del producto para
actuar sobre procesos de otro origen.

Siguen43 escenarios amplios abiertos y0/12 páginas completamente aceptadas.
El siguiente bloque principal es revalidar los prompts y sus consumidores;
después siguen evaluación de comunicación, seguridad/licencias, datos históricos,
interfaz y demás recuperación. Todos los detalles secundarios y la revisión
independiente del conjunto quedan después de las capacidades principales.
