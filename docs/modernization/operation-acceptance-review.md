# Eventos y recuperación de instalación: D13

Inicio **2026-11-07 22:37:44 UTC**, base `018155d`.
Verificado **2026-11-07 22:45:25 UTC**, **7 min 41 s** desde el inicio hasta
verificar, sin documentación/checkpoint posteriores. **78 casos instalados pasan,
cero fallos y omisiones**, en 55,287 segundos. Los 674 archivos Python/SQL coinciden
entre fuente, rueda e instalación; los 247 módulos backend importados proceden
de la instalación. **D13 queda comprobado** dentro de esta matriz: 35/43 escenarios
cerrados, ocho abiertos. Ver [resultados](operation-acceptance-results.json) y
[recibo instalado](operation-acceptance-packaging.json).

No cambia código de producto: sus 360 archivos Python/SQL coinciden con la rueda
anterior. La primera selección reutilizó ese paquete; la final incorpora únicamente
la corrección del archivo de pruebas históricas. La
[comparación de artefactos](operation-acceptance-artifact-comparison.json)
registra sus identidades y el único archivo diferente.

## Contrato y prueba

| Qué pasaría si… | Respuesta y evidencia actual |
| --- | --- |
| Un navegador deja de consumir mensajes | `ConnectionManager` conserva un emisor y una página acotada por conexión, sin cola global. El plazo cubre tanto la espera por su lock como el envío. `test_durable_events.py` bloquea un socket: se cierra con 1013 mientras otro recibe sus 205 eventos en páginas de hasta 100; ambos emisores se drenan. |
| Se interrumpe la conexión mientras entran eventos | `EventHistory` lee filas comprometidas por ID ascendente y proyecto. Los ensayos recuperan más de una página y nuevas llegadas sin duplicados; HTTP y WS usan el mismo contrato. Se comprueba reutilización del gestor después de cerrar el loop anterior. |
| El cursor perdió historia o el payload está dañado | La retención tiene un límite durable y transaccional; un gap exige resincronización explícita. El cliente conserva el aviso aunque vuelva a conectar, refresca las lecturas y no ejecuta trabajo como efecto de recuperar eventos. Los IDs decimales no pierden precisión en JavaScript; un payload dañado queda marcado como no disponible. |
| Se intenta copiar una instalación todavía activa | Backup exige exclusión sobre servicio, autoridad y SQLite. Rechaza escritores o permisos sin cierre probado, verifica registros y contenido, y publica el manifiesto completo al final. Una interrupción conserva una copia parcial identificable; no inventa éxito. |
| La restauración cambia de carpeta | Primero se verifica el manifiesto; después se copia a un destino nuevo. Se recolocan registros de adjuntos/repositorios/worktrees y referencias administrativas Git. Las pruebas conservan hashes, revisión Git, archivos sin commit, relaciones, integridad SQLite y lectura HTTP del informe/adjunto en su proyecto. |
| Los datos o enlaces cambian durante la copia | Se rechazan contenido cambiado, manifiesto dañado, referencias Git externas y destinos que solapan el origen por un alias. Los sidecars transitorios de SQLite se distinguen de archivos normales: los primeros no invalidan una instantánea consistente; los segundos no desaparecen silenciosamente. |
| Una copia conserva una orden pendiente o credenciales viejas | Restore archiva la autoridad anterior y queda inactivo. La inscripción usa autoridad/testigo y emparejamiento nuevos; conserva la incertidumbre de trabajos incompletos, pausa planes y no repite preguntas, inferencias o efectos. Los resultados completados siguen siendo historia completada. |
| El host original todavía existe al restaurar | La operación de borrado copiada permanece pendiente y no toca el origen. Una decisión nueva puede recuperar los bytes del archivo de retención dentro de la instalación nueva. El ensayo D08 reutilizado comprueba ambos efectos en el mismo caso. |

## Evidencia y reutilización

La selección instalada incluye nueve archivos/casos de eventos, transporte del
dueño, backup, inscripción restaurada, política de recuperación, historial tras
cambio de kernel y archivo de retención. Se ejecuta fuera del checkout, desde
una rueda no editable, con CPU/memoria/PIDs disponibles mediante una unidad
transitoria. La primera rueda se reutilizó; la final se reconstruye/reinstala
tras terminar todos los procesos originales para incorporar el fixture corregido.
No hay llamada generativa ni nueva ejecución de una VM.

La primera selección conserva **60 casos correctos y un fallo** en
[su recibo](operation-acceptance-initial-packaging.json). El fixture de reinicio
intentaba aplicar la inversa de schema58 sobre una base que ya tenía schema68;
el producto lo rechazó correctamente antes del ensayo de restore. Ahora la
preparación crea los prefijos reales 56 y 57, y añade el esquema actual como caso
separado. La inscripción utiliza de nuevo el migrador vigente. Una prueba propia
con schema57 y archivo usado conserva todos los valores de peers/procedencia
ante la inversa rechazada; el prefijo sin uso sí puede revertirse y, una vez
actualizado, vuelve a rechazar esa inversa antigua. No se relaja ninguna protección
ni se omite el caso fallido. **Los 15 casos dirigidos pasan en 8,60 segundos**.

Los **14 contratos de frontend y dos pruebas DOM pasan**: cursores, deduplicación,
feed acotado, generaciones y reconexión por cursor, aviso persistente de historia faltante y conservación
de intención al detectar otra instalación. No se modifica UI ni dependencias.

La [comparación de nueve módulos](operation-acceptance-source-comparison.json)
confirma identidad byte a byte de los lectores/gestores de eventos y de la puerta
de sesión con sus entregas previas. Sus ensayos de navegador siguen siendo
**evidencia histórica**: recuperación de 488 eventos por HTTP/WS reales en
[eventos durables](durable-events-results.json), y tres estados controlados del
[cambio de instalación](restored-enrollment-results.json). Los contratos actuales
no convierten esos ensayos en una ejecución nueva del navegador ni prueban
equivalencia de toda la aplicación.

## Límites y trabajo separado

- Los datos son sintéticos. No se migra ni acepta el archivo histórico real del
  usuario; tampoco se promete un downgrade general después de escrituras nuevas.
- Las pruebas seleccionadas de cambio de kernel controlan esa identidad; no son
  otro reinicio físico. Los ensayos anteriores de VM y de suscripción/Ken tras
  restore conservan su alcance histórico y no se vuelven a contar.
- La retención conoce eliminaciones desde schema59; no puede reconstruir las
  anteriores. Backup exige layout administrado y explicita recursos externos.
- Los permisos copiados no prueban cierre del host original. Recuperar datos y
  autorizar ejecución son decisiones distintas y quedan registradas como tales.
- DD079 conserva las incidencias de presentación/accesibilidad del panel de
  actividad. Aceptar este contrato funcional no acepta ninguna de las doce páginas.
- No se declara suite global verde, comprensión humana, desastre universal ni
  seguridad frente a un operador host hostil. Los detalles quedan para después
  de las capacidades principales.

No hay definiciones de producto nuevas o modificadas. Las cinco definiciones
nuevas o modificadas del archivo de pruebas tienen docstrings en inglés, según
[el recibo](operation-acceptance-docstrings.json). La lista y los tiempos se
actualizan en el tablero y el chat al cambiar de tarea.
