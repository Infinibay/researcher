# Capacidad temporal y salidas del lector Chroma

Base `7047b91`. Bloque **12:45:45–13:00:49 UTC**, **15 min 4 s** hasta
validación. Continúa la tarea principal de recursos; el servicio completo aún
no tiene una nueva frontera agregada comprobada.

## Cambio de comportamiento

El lector ya no puede escribir en carpetas del host. Recibe la copia cruda en un
montaje de sólo lectura y prepara la copia que puede migrar dentro de un tmpfs.
Datos temporales, HOME, caché y `/tmp` comparten su capacidad de datos. El valor
predeterminado es256MiB; `--scratch-bytes` permite elegir entre1MiB y2GiB.
No hay fallback hacia un directorio sin límite cuando se agota.

Sólo dos archivos persistentes se montan para escritura: registros y recibo.
Están creados por el padre y fijados mediante descriptores; el hijo no puede
sustituirlos por enlaces. Conservan el límite por archivo de RLIMIT_FSIZE y la
validación de tipo/tamaño/recibo antes de promover registros. Raíz, `/dev` y
`/proc` se remontan de sólo lectura. El ensayo confirma que no quedan descriptores
de directorios heredados que el lector pueda usar como otro acceso al host.

El padre drena el log, conserva hasta64KiB y descarta el excedente sin bloquear
al productor. `log_truncated` distingue un diagnóstico recortado de uno completo.
Esto no autoriza truncar documentos ni declarar exportados registros faltantes.

El snapshot crudo también aplica los límites durante la enumeración y la copia,
sin ordenar antes todo el árbol. La copia SQLite considera sus páginas lógicas,
incluido contenido confirmado que aún estaba en el WAL, y su callback controla
el plazo; copia y hashing de archivos se hacen por bloques con comprobaciones.
La copia cruda permanece si algo falla. La copia temporal del lector desaparece
con su namespace; ya no existe un segundo árbol `reader/` durable sin cuota.

## Evidencia

- 8 pruebas finales del exportador pasan.3comprobaciones adicionales pasan tras
  incluir la observación de descriptores. Sin omisiones.
- Un tmpfs de1MiB rechaza con ENOSPC varios archivos pequeños antes de alcanzar
  los64intentados. Intentos de escribir en la raíz y `/dev/shm` fallan con EROFS.
  La prueba mide la barrera de datos del kernel, no una cuota de memoria total.
- 2 MiB de log quedan drenados y sólo64KiB se retienen, con truncamiento explícito.
- El intento de sustituir la salida por un enlace falla con EBUSY. La prueba
  anterior esperaba rechazo posterior del padre; ahora el kernel impide crear
  ese enlace. El archivo fijado permanece regular y no se lee el secreto de prueba.
- Persisten las pruebas de entorno/red/origen inaccesibles, entrada estándar
  cerrada, deadline, ausencia de fallback y rechazo del punto interno sin namespaces.
- Chroma1.5.9 real conserva105registros de2colecciones, sin cambiar los hashes
  de la fixture original ni generar embeddings.
- El ensayo completo usa el backend instalado, importa el esquema17 al59,
  conserva105registros/104adjuntos textuales/1registro sólo de metadatos y lee
  datos con sus límites de proyecto por HTTP. Servicio original cerrado con143,
  cero dispatches de inferencia y cero llamadas al modelo. La cuenta del ensayo
  es sintética.

El primer test falló porque aún no existía `--scratch-bytes`. La primera corrida
completa tuvo6aprobadas y1expectativa de symlink anterior; ambos recibos se
conservan. No se ocultaron ensayos ni se reinició un proceso por timeout de observación.

16definiciones cambiadas documentadas;83revisiones de prompts vigentes. Lock de
Chroma comprobado sin cambios. No se reconstruyó el backend: los616archivos
Python/SQL siguen coincidiendo con el wheel instalado del bloque anterior.
DD100 conserva11avisos de estilo. [Pruebas](chroma-capacity-results.json),
[importación instalada](chroma-capacity-import.json), [docstrings](chroma-capacity-docstrings.json).

## Límites que siguen siendo trabajo principal

La capacidad del tmpfs limita sus bloques de datos, no toda la memoria del host,
los metadatos/inodos ni todos los procesos descendientes. Tampoco impone una
cuota del volumen durable donde quedan copia cruda, salidas y manifiesto.
`aggregate_disk_quota` permanece explícitamente falso; no se infiere un límite
de filesystem a partir de dos límites por archivo. El tamaño adecuado para datos
históricos del propietario todavía requiere esos datos; no se certifica un
dataset mayor que el espacio elegido.

Continúan los recursos globales del supervisor, cuotas durables de operaciones
administrativas, migración/recuperación con almacenamiento acotado, seguridad
Ken/ONNX/Chroma, comunicación humana/otros perfiles, datos históricos y aceptación
de12páginas. Los43escenarios amplios siguen abiertos. No hay nueva suite global
verde, porcentaje global sustentado, push ni despliegue.
