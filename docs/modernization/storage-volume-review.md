# Almacenamiento durable con capacidad agregada

Una instalación nueva puede vincular todos sus directorios persistentes a un
volumen ext4 dedicado y limitado. El filesystem impone el máximo agregado de
bloques e inodos; crear muchos archivos no evita ese límite. El host verifica
también el tamaño del dispositivo completo para incluir el espacio de metadatos.
No se usan escaneos periódicos ni límites por archivo como sustitutos de la cuota.

El operador prepara el volumen. El producto no monta, formatea, redimensiona,
borra ni repara almacenamiento. El [ejemplo de recursos](../config/host-assets.example.json)
y la [guía de instalación](../architecture/native-host-installation.md) seleccionan
un volumen de hasta32GiB con256MiB de margen para admitir trabajo nuevo.

## Contrato implementado

- `StorageVolume` captura identidad, capacidad del filesystem/dispositivo e inodos
  mediante mountinfo, un descriptor del directorio, statvfs y sysfs. Rechaza una
  carpeta ordinaria, el filesystem raíz, montajes anidados/apilados, un bind de
  subdirectorio, permisos ajenos, rutas redirigidas y un dispositivo demasiado grande.
- `init-host` verifica instalación y testigo antes de crear datos. Persiste el
  recibo original en runtime.json. El testigo queda fuera de la instalación,
  dentro del mismo límite; esa separación no constituye un backup físico.
- Apertura, composición y arranque verifican el volumen y las rutas de fuentes,
  control, DB, autoridad/testigo, adjuntos, autenticación y logs. El arranque ASGI
  comprueba el contrato antes de logging, migraciones o emparejamiento.
- Nueva admisión y despacho exigen identidad y margen de espacio. Una falta de
  espacio informa que se conserva el trabajo y que debe liberarse explícitamente.
  Stop y la pausa de planes no exigen el margen de admisión. El margen **no es
  espacio reservado**: una operación admitida puede consumirlo y fallar al escribir.
- Se rechazan montaje ausente, sustitución y capacidad modificada. No hay
  recreación vacía, borrado de trabajo parcial, adopción ni repetición automática.

Los campos de [mountinfo](https://man7.org/linux/man-pages/man5/proc_pid_mountinfo.5.html)
identifican filesystem, dispositivo, raíz y punto de montaje. La contabilidad de
bloques/inodos y espacio disponible corresponde a
[statvfs](https://man7.org/linux/man-pages/man3/statvfs.3.html). La cota usa el
filesystem completo, cuya asignación se realiza en
[bloques ext4](https://www.kernel.org/doc/html/latest/filesystems/ext4/blocks.html).

## Prueba real e inspección independiente

Se ejecutó una sola VM, sin tarjeta de red, credenciales reales ni modelos. El
paquete instalado preparó una instalación real con Codex/Ken comprobados y un
volumen separado de128MiB. Cuatro procesos de un mismo dominio escribieron
archivos de64KiB en índice Ken, desarrollo, estado nativo y adjuntos. Entre todos
terminaron1758 archivos completos antes de recibir ENOSPC; se conservaron también
los intentos parciales. No son cuatro cuotas de128MiB.

La admisión fue rechazada. El dominio se retiró físicamente con el volumen lleno.
Después se desmontó: el producto rechazó el montaje ausente sin crear nada en
su lugar. Tras montar el mismo disco, el código pendiente y ambas bases
conservaron su integridad. Esto prueba un remount ordenado, **no pérdida de energía**.

La VM terminó con código0 en19,99segundos, incluyendo preparación. Se extrajeron
el código pendiente y las dos bases directamente del disco detenido mediante
debugfs en sólo lectura. El hash del código coincide y ambas bases pasan integridad
y claves foráneas; la tarea original sigue presente y hay0 despachos de inferencia.
[Recibo de VM](storage-volume-vm.json),
[inspección independiente del disco](storage-volume-disk-inspection.json).

## Validación del cambio

Bloque **11:38:40–11:58:03 UTC:19min23s**, hasta el corte de validación.
Tres pruebas reprodujeron la falta de integración antes del cambio. Primer
conjunto:37aprobadas; límites de servicio/arranque/recuperación:46aprobadas.
El conjunto final de almacenamiento contiene14aprobadas y sustituye los13casos
anteriores de ese archivo: **84casos distintos desde fuente**, sin omisiones.

El paquete final pasa **55pruebas instaladas**, incluidas composición, Stop,
planes y catálogo de prompts.612archivos Python/SQL coinciden entre fuente,
wheel e instalación.57definiciones cambiadas tienen documentación.83decisiones
de prompts vigentes tras revisar3consumidores; catálogo6 y texto de instrucciones
sin cambios. No se presenta esto como nueva suite global verde.

Tras la VM se hizo un ajuste: la pausa de planes también evita el margen de
admisión, y se agregó la regresión de Stop con margen agotado. Sólo service.py
y su test adicional difieren entre ambos wheels; almacenamiento, instalación,
composición y arranque son idénticos al paquete ensayado en la VM. No se repitió
el ensayo para ese cambio. [Paquetes](storage-volume-packaging.json),
[resultados](storage-volume-results.json), [docstrings](storage-volume-docstrings.json).

## Pendientes principales y detalles diferidos

Las instalaciones antiguas sin política siguen siendo **explícitamente no
acotadas** (`storage.enforced:false`). No se migró el host existente de este
equipo ni se cambiaron sus montajes. La incorporación/migración y recuperación
de instalaciones reales con esta política todavía requiere trabajo, incluido
el cambio de volumen/capacidad y la reinscripción tras restaurar en otra ruta.

Temporales de procesos del supervisor, exportaciones/backups fuera del volumen,
operaciones auxiliares y recursos remotos necesitan sus propios límites. Tampoco
se prueba aquí escritura concurrente de la DB durante ENOSPC, pérdida de energía,
agotamiento de inodos, ampliación segura ni recuperación completa del servicio
con el disco lleno. Son alcance principal pendiente, no detalles cosméticos.

DD096 conserva los avisos de estilo/imports para después de todas las capacidades
principales. Siguen43escenarios amplios abiertos y0/12páginas completamente
aceptadas. No hubo push ni despliegue.
