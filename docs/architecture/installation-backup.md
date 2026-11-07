# Copia y restauración de datos de una instalación

El comando de administración puede copiar los datos de una instalación nativa
preparada y restaurarlos en otra carpeta. La restauración conserva los datos y
el historial y termina en `pending_enrollment`. El comando separado
`enroll-restored-host` habilita la nueva instalación con recursos y autoridad
nuevos. Se han comprobado su arranque, un turno completo de modelo/Ken y el
reinicio del servicio. También se comprobó la recuperación tras reiniciar una VM
con datos sintéticos; siguen pendientes los datos históricos del propietario.
No es todavía una aceptación integral de
recuperación tras un desastre.

```bash
researcher-bootstrap backup-host \
  --directory /ruta/instalacion \
  --destination /ruta/copias/copia-nueva

researcher-bootstrap verify-backup --backup /ruta/copias/copia-nueva

researcher-bootstrap restore-host \
  --backup /ruta/copias/copia-nueva \
  --destination /otra/ruta/instalacion-restaurada

researcher-bootstrap enroll-restored-host \
  --directory /otra/ruta/instalacion-restaurada \
  --witness-dir /otro/volumen/testigo-nuevo \
  --assets /ruta/recursos-del-nuevo-host.json

researcher-bootstrap check-host --directory /otra/ruta/instalacion-restaurada --probe
researcher-start --installation /otra/ruta/instalacion-restaurada
```

Los destinos deben ser nuevos y tener un padre existente. Se rechaza cualquier
solapamiento con los datos originales, su testigo de autoridad o la copia,
incluidos alias mediante enlaces simbólicos. Cada comando acepta `--max-bytes`,
`--max-files` y `--timeout`; los valores predeterminados son 20 GiB, 200 000
entradas y 300 segundos. Un límite agotado produce un error; no se omiten ni
truncan archivos para declarar éxito.

Antes de copiar, cerrar el servicio y conciliar los agentes pendientes. La
operación mantiene congelada la autoridad verificada y bloquea los escritores
SQLite de la instalación. Rechaza una concesión activa, procesos registrados sin
cierre, bloqueos de otro escritor y entradas especiales como sockets. Comprueba
también que los uploads, repositorios y worktrees activos registrados estén
incluidos. Las rutas Git que dependen de almacenamiento externo requieren una
migración explícita de ese almacenamiento; no se omiten silenciosamente.

### Recuperación explícita tras un cambio de kernel

Si el sistema se reinició, la autoridad anterior rechaza su uso normal. El modo
`backup-host --after-reboot` permite capturar esa autoridad como evidencia para
seguir con `verify-backup`, `restore-host` y `enroll-restored-host` en rutas nuevas.
Exige un identificador de arranque diferente, las identidades originales de los
tres archivos, una cadena de testigo válida y acuerdo con el estado SQL. Cambiar
sólo el observador de procesos no alcanza. Conserva las transiciones preparadas
y colas incompletas del testigo sin aplicar concesiones ni reparar el journal.
SQLite puede efectuar su propia recuperación al abrir sus archivos; este modo
no promete una copia forense de todos los bytes de un disco después de perder energía.

Los registros de procesos pendientes deben pertenecer al kernel y observador
originales. La reinscripción conserva su estado original y registra por separado
su procedencia en `runtime_peer_archives` (migración57). **Archivado no significa
cerrado**: un kernel diferente también puede corresponder a una copia en otro
equipo. El host original y los efectos remotos pueden seguir requiriendo
comprobación. Los registros archivados no se adoptan para ejecutar ni acreditar
resultados en el host nuevo.

La reinscripción actualiza una copia de esquema56 antes de activar el servicio.
Con el servicio detenido, `restore_peer_archive_schema` permite deshacer el paso57
únicamente si todavía no contiene historial y no hay versiones posteriores.
Si existe historial archivado, se conserva y se recurre a reparación hacia
adelante o a restaurar una copia verificada; la inversa nunca lo elimina.

La copia incluye los archivos bajo la instalación, snapshots SQLite consistentes
y el testigo independiente de autoridad. Los journals transitorios de SQLite se
incorporan mediante su API de backup, en lugar de copiar un archivo `.db` aislado
de su WAL. El manifiesto contiene rutas, permisos, enlaces, tamaños, SHA-256,
conteos por tabla, versión de esquema e integridad/referencias. Los archivos se
leen sin seguir enlaces simbólicos; los enlaces se conservan como tales.
Los binarios, modelos públicos y archivo de cuenta externos quedan referenciados,
sin copiar sus contenidos. Esto es una copia de datos, no de todos los recursos
necesarios para reconstruir el host.

Se comparan el inventario inicial/final y los hashes de archivos para detectar
ediciones ajenas a los bloqueos SQLite. El manifiesto de finalización se publica
al final, después de sincronizar los objetos. Si falla la operación, se conserva
la carpeta parcial para inspección. `verify-backup` exige un manifiesto completo
y valida todos sus objetos; una carpeta parcial nunca cuenta como copia válida.

La restauración verifica antes de crear el destino. Conserva commits, ramas,
índices y cambios Git sin commit, y repara los archivos administrativos de los
worktrees enlazados. Ajusta únicamente los registros actuales de repositorios,
adjuntos y worktrees; las identidades e instrucciones históricas de runs,
candidatos, concesiones y efectos conservan su procedencia original. Un recibo
registra cada ubicación anterior y nueva.

Por ejemplo, un adjunto registrado en `/viejo/uploads/101/uploads/doc.txt` pasa
a `/nuevo/uploads/101/uploads/doc.txt`, conservando bytes e identidad17. Un run
que había usado `/viejo/sources/proyecto` mantiene esa evidencia histórica: no
adquiere permisos sobre el nuevo árbol por haber cambiado de carpeta.

El runtime, la autoridad y el acceso originales quedan archivados bajo una
carpeta privada `.restorations/<id>`. El runtime activo contiene sólo una marca
de reinscripción pendiente y el nuevo acceso no reutiliza sesiones copiadas.
El launcher de instalación rechaza ese estado hasta la reinscripción explícita.

La reinscripción valida el modelo y los recursos nativos/Ken/cuenta/cgroup
explícitos, comparte el bloqueo del propietario de la base y crea una autoridad
independiente nueva. Conserva la autoridad anterior archivada. Los planes activos
quedan pausados; los runs pendientes, en ejecución, esperando respuesta o revisión
quedan como historial `superseded` en esta copia. Se conservan resultados aceptados,
prompts, recibos, handoffs y evidencias originales. Se revocan concesiones copiadas,
caducan preguntas pendientes y el consumo reservado sin desenlace queda desconocido.
Los eventos y `enrollment.json` registran el estado anterior y esta decisión.

Esto no afirma que el host original o sus efectos remotos estén detenidos. Por
ejemplo, una publicación enviada después del snapshot podría haber terminado en
el remoto sin aparecer en la copia. Hay que consultar ese resultado original
antes de formular otra petición. Cambiar de instalación no reenvía la anterior.

La configuración y el historial se guardan antes de publicar la marca `prepared`.
Un fallo deja los directorios parciales para inspección; el comando no los
reinicializa al repetirse. Para recuperar una reinscripción interrumpida antes de
la activación, conservar esa evidencia y restaurar la misma copia verificada en
**otra carpeta nueva**, con otro testigo nuevo. La prueba incluye salida abrupta
de un proceso propio después de guardar configuración/historial. Las nuevas
restauraciones separan un recibo de activación pequeño de `details.json`, que
contiene todas las reubicaciones y conteos. El primero mantiene64KiB; el segundo
admite hasta128MiB, con tamaño/hash exactos e identidad comprobados antes de
crear autoridad, sin seguir enlaces. Los recibos pequeños de formato1 siguen
admitidos. Un fallo entre los dos archivos no publica la instalación terminada.

La salida de restauración y reinscripción incluye `data_recovery`: las escrituras
posteriores al snapshot no están incluidas, no se comparó el original y tampoco
se comprobó que siga disponible. El comando no lo reemplaza. Conservar una copia
actual cuando sea posible; restaurar una copia anterior no equivale a deshacer
una migración conservando los cambios nuevos.
[Política, ejemplos e inversas admitidas](migration-recovery-policy.md).

Al emparejar el navegador, la identidad incluye la base física. Si cambia, aparece
una explicación con un ejemplo y una descarga de las solicitudes y borradores
anteriores. El propietario elige archivarlos antes de entrar en la instalación
actual. Se conservan exactamente sus paquetes bajo claves
`researcher:archived-owner-state:v1:*` de `sessionStorage`; cerrar la pestaña puede
eliminarlos, por lo que la descarga permite guardarlos fuera del navegador.
Un error de almacenamiento mantiene el acceso bloqueado y los paquetes originales.
Cada petición protegida lleva la identidad de instalación; el servidor rechaza
una identidad anterior antes de ejecutar la acción. El terminal conserva su
protección equivalente existente.

La evidencia cubre SQLite real, archivos, Git con worktree y cambios sin commit,
comandos públicos, lectura HTTP con separación de proyectos, corrupción,
objetos ausentes, rutas inválidas, cambios durante copia, escritores ocupados,
límites y salida abrupta de un hijo durante restore. El código sincroniza
archivos/directorios; el ensayo no simula pérdida física de energía.
[Resultados](../modernization/installation-backup-results.json) y
[paquete instalado](../modernization/installation-backup-packaging.json).

La reinscripción tiene pruebas de fuente y del paquete instalado, dos arranques
del servicio con emparejamiento nuevo, rechazo HTTP de un endpoint anterior,
pausa de planes con handoff conservado y prueba física de un proceso no-op.
Ese tramo no ejecutó turnos de modelo. El ensayo posterior de
[`restored_host.py`](../../evals/operation/restored_host.py) sí ejecutó una solicitud
nueva con la suscripción: Ken devolvió código restaurado, Python produjo200,
se conservaron un finding provisional con dos citas y un informe draft, y otro
arranque mantuvo los mismos resultados. El run anterior sigue pendiente en el
original y como historial en la copia. Cinco peers quedaron cerrados; el
verificador de sólo lectura no generó otro turno.
[Resultado y límites](../modernization/restored-host-evaluation-results.json).
El aviso del navegador
se revisó en escritorio/móvil y ante falta de almacenamiento; esto no acepta las
12 páginas completas. [Resultados](../modernization/restored-enrollment-results.json),
[paquete](../modernization/restored-enrollment-packaging.json),
[revisión visual](../design/audits/restored-session/report.md).

El ensayo de [`reboot_vm.py`](../../evals/operation/reboot_vm.py) completa dos
arranques reales dentro de un proceso QEMU, con identificadores de kernel
diferentes. Comprueba rechazo de autoridad anterior, los comandos públicos de
recuperación, un proceso no-op con cierre y lecturas HTTP de tareas/adjuntos.
Conserva un registro pendiente anterior, sin declarar que sea prueba de cierre.
El servicio y la VM terminan; no hubo inferencia ni cuenta real dentro de la VM.
Los cinco fallos de preparación previos y sus causas quedan registrados junto
al resultado exitoso. No simula pérdida de energía ni un agente nativo ejecutándose
durante el reboot. [Evidencia](../modernization/reboot-recovery-results.json).

La [importación histórica](legacy-import.md) ya tiene un recorrido comprobado
para Chroma, informes sólo en archivos y rutas externas explícitas. Siguen
pendientes el inventario/migración de los datos del propietario, la compatibilidad
con sus formatos/versiones reales y la aceptación integral de recuperación.
Restaurar una copia anterior tampoco conserva escrituras realizadas después de
aquella copia.
