# Datos y persistencia: D01–D04

Base `6b2f938`. Bloque **2026-11-07 19:56:34–20:12:04 UTC**:
**15 min 30 s hasta verificar**, sin incluir documentación/checkpoint posteriores.
Se corrigieron fronteras activas de la API, sin cambiar prompts ni consumir modelos.

## Requisitos y evidencia

| Escenario | Implementación y prueba observable |
| --- | --- |
| D01: migración fallida e integridad | Se conserva el catálogo ordenado 18–65 sobre la base soportada 17. Las 48 interrupciones de escritor antes de confirmar la versión recuperan la misma base, conservan los datos sembrados y comprueban integridad/FK. El arranque propaga fallos; ahora verifica también integridad y relaciones antes de publicar acceso del propietario. Una referencia a proyecto inexistente impide servir. Readiness exige la historia completa actual; borrar el registro 65 durante el servicio devuelve 503. |
| D02: SQLite ocupado | 49 handlers de CRUD, Git e historial pasan a los workers síncronos de FastAPI. Los handlers mixtos delegan sus callbacks DB y conservan los avisos/control del runtime en su loop. Un `BEGIN IMMEDIATE` real bloquea la creación original mientras health y WebSocket responden. Otro ensayo HTTP retira autoridad e interrumpe al trabajador original antes de liberar el lock; no confirma cancelación durable prematuramente. Tras liberar, hay una creación y un evento de Stop. |
| D03: estado y evento durable | Se elimina la copia API posterior al commit: los triggers ya insertaban `task_created` y `task_status_changed` dentro de la transacción. Fallar el trigger no deja tarea creada. Dos procesos hijos terminan justo antes/después del commit y muestran, al reabrir sin repetir la petición, cero/cero o una/una filas de tarea/evento. Las pruebas existentes verifican rollback conjunto de cancelación, permisos y evento, y de aceptación de código con su evento. |
| D04: finalización tardía y reapertura | Se restaura un grafo explícito; `done` y `cancelled` no se reabren por el validador genérico. La API sigue rechazando cambios genéricos de ciclo de vida para todos los tipos nativos, bajo el lock de escritura. Las carreras de Stop/finalización y las correcciones conservan el resultado histórico sin aceptar ni reactivar trabajo obsoleto. La corrección autorizada de trabajo aceptado avanza versión y conserva el recibo; el siguiente trabajo exige admisión explícita y obtiene otro intento trazable. |

El runtime separa tarea, run e intento: detener un run no equivale a declarar
terminada o borrada su tarea. La finalización del transporte tampoco acepta el
resultado. Los controles nativos siguen comprobando identidad, fence, contexto,
estado del sujeto y cierre de peers; el grafo genérico no les concede autoridad.

También se evita un retry peligroso del helper DB: una vez que SQLite informa
cambios de filas, un error posterior se propaga en lugar de repetir el callback.
El ensayo confirma una sola fila aunque falle la observación después de commit.
Es una política conservadora: no reintenta tampoco cambios todavía reversibles.
No convierte DDL ni efectos externos en idempotentes; éstos conservan sus journals.

El pool ASGI observado dispone de 40 tokens de concurrencia. SQLite mantiene
`busy_timeout=5000` y el helper un máximo predeterminado de 5 intentos antes de
cambiar filas. Son límites de trabajo bloqueante, no una promesa de throughput ni
una prueba de saturación masiva. La contención entre escritores sigue existiendo.

## Validación y procedencia

La reproducción inicial dio cinco fallos nuevos y 24 aserciones históricas del
grafo incorrecto. Tras las correcciones pasan 62 casos dirigidos y una selección
de **288 casos de fuente**. El número de casos parametrizados del grafo cambia
porque su prueba de aristas válidas se genera a partir del propio grafo; no se
presenta esa variación como una eliminación de fallos sin corregir. Los ensayos
finales de persistencia/control suman 9 pases; no se suman sus casos solapados.

El primer wheel pasa **323 casos instalados**, sin fallos ni omisiones, en
121,976 s. La revisión posterior encuentra 17 handlers síncronos adicionales de
Git/historial. El wheel final sólo difiere en esos dos módulos Python y pasa
**124 casos de API/coordinación**, sin fallos ni omisiones, en 63,410 s.
Esos 124 están incluidos en la selección anterior; **no son 447 casos distintos**.
Se conservan ambos paquetes, logs y recibos. No se atribuye la ejecución de los
323 al wheel final.

Los **657 archivos Python/SQL**, incluidos **348 de producto**, coinciden entre
árbol, wheel final e instalación no editable. Los 236 módulos backend observados
en la selección final se importan desde la instalación, fuera del checkout.
Los hijos de crash comprueban la huella del código que ejecutan antes de escribir.
Se comprueban 73 definiciones documentadas en 17 módulos. El auditor inicial de
docstrings confundió helpers homónimos; se corrigió a nombres con su ámbito,
sin modificar código para satisfacer ese falso diagnóstico.

Inventario: 305 archivos y 85 candidatos revisados, cero pendientes. Se revisaron
ocho identidades/consumidores afectados; sus AST de contenido no cambiaron.
OpenAPI y descripciones del propietario siguen siendo metadatos, no instrucciones
del agente. Esta revisión estática no mide eficacia ni comprensión humana.

## Alcance y siguiente bloque

D01–D04 quedan comprobados para la instalación administrada y el catálogo
soportado, con datos sintéticos, SQLite/HTTP/WebSocket reales y generación
controlada. La importación de datos históricos reales y sus esquemas concretos,
la prueba de carga, la aceptación de páginas y la suite global siguen separadas.
No hubo llamadas de modelo, cambios frontend ni publicación externa. La última
suite global sigue siendo la histórica con fallos; no se anuncia otra verde.

Siguiente bloque: **D05–D09**, artefactos recuperables y operaciones Git con alcance,
precondiciones, conservación de trabajo y reparación explícita. Detalles secundarios
después de todas las capacidades principales.

[Paquete inicial](data-boundaries-packaging.json),
[paquete final](data-boundaries-final-packaging.json),
[diferencia de artefactos](data-boundaries-artifact-comparison.json),
[resultados](data-boundaries-results.json),
[docstrings](data-boundaries-docstrings.json).
