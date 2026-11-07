# Recuperación de datos con disco lleno y restauración acotada

La reinscripción de una restauración aceptaba `storage` pero no capturaba el
recibo del volumen. Publicaba una instalación preparada cuyo siguiente arranque
rechazaba la configuración. Ahora comprueba el volumen elegido, las rutas de
datos/testigo y el margen libre antes de crear autoridad o cambiar el historial.
Guarda un recibo nuevo en `runtime.json` y expone su observación en el resultado.
Las instalaciones sin política siguen identificadas como no acotadas.

Tres pruebas fallaban antes de la corrección: recibo ausente, testigo fuera del
volumen y reinscripción con espacio insuficiente. Después pasan59casos dirigidos
de fuente y59del paquete instalado. Los rechazos conservan la base copiada y el
estado pendiente, sin autoridad nueva. [Corridas](storage-recovery-results.json).

## Ensayo de kernel y disco reales

Una VM desechable, sin tarjeta de red ni credenciales reales, usa el paquete
instalado y un volumen ext4 de128MiB. El ensayo:

1. Arranca el API y abre una transacción sobre la base de producto. Cambia un
   nombre dentro de esa transacción, sin confirmarlo.
2. Cuatro escritores llenan raíces de datos diferentes. Todos observan ENOSPC;
   se llenan también los bloques restantes. La siguiente escritura grande de
   SQLite falla con `SQLITE_FULL`.
3. Comprueba que el nombre original sigue intacto y el evento de la transacción
   fallida no existe. Se rechaza trabajo nuevo y se retiran los grupos de escritores
   y servicio. En esta corrida el servicio sí pudo guardar cierre y salió143.
4. Reinicia el kernel. El fixture elimina exclusivamente sus1762archivos de
   relleno y su archivo de cola; no hay limpieza automática en el producto.
5. Hace backup explícito de la autoridad anterior con `after_reboot`, restaura
   en otra carpeta del volumen y reinscribe con autoridad y recibo nuevos.
6. La copia responde por HTTP, conserva el código de trabajo y los
   datos originales, no crea ejecuciones ni dispatches y cierra su grupo al parar.

[Resultado de VM](storage-recovery-vm.json). Un proceso QEMU, dos identificadores
de kernel,30,09segundos incluyendo preparación; cero llamadas a modelos.
Después de terminar QEMU, una extracción de sólo lectura mediante debugfs
verifica de forma independiente las dos bases, el código y los recibos sobre
el disco retenido: integridad correcta, cero eventos de la transacción fallida,
cero runs/dispatches y contenido preservado.
[Inspección del disco](storage-recovery-disk-inspection.json).

El ensayo se reproduce con `evals/operation/reboot_vm.py --storage-recovery`,
los argumentos explícitos habituales de QEMU/kernel/recursos/env y una carpeta
de salida nueva. El init rechaza ejecutar montajes/reinicio fuera de su PID1
marcado; el controlador no reintenta una VM cuyo resultado desconoce.

## Límites y siguiente trabajo

Es una recuperación comprobada con datos sintéticos y reinicio controlado.
No demuestra pérdida abrupta de energía, inodos agotados, autoridad con concesiones
activas, ni el caso donde un disco lleno impide guardar el recibo de cierre.
El estado `closed` observado no permite dar ese último caso por resuelto.
Tampoco prueba recuperación de los datos históricos del propietario. Esos casos
permanecen principales; no se reclasifican como pulido.

El original y el backup se conservan. Si falla una reinscripción después de crear
estado parcial, la recuperación usa otra copia en una carpeta nueva. No se borran
controles para forzar arranque ni se reejecuta trabajo copiado. La
[guía de backup](../architecture/installation-backup.md) describe la migración.

618miembros Python/SQL coinciden entre fuente, wheel e instalación;
[paquete](storage-recovery-packaging.json).24definiciones nuevas o modificadas
tienen docstrings; [comprobación](storage-recovery-docstrings.json).83revisiones
de prompts siguen vigentes.19avisos Ruff se difieren en DD102, después de todas
las tareas principales. No se repitió la suite global.

Bloque **2026-11-07 13:26:25–13:34:11 UTC**, **7 min 46 s** hasta validación.
Siguen43escenarios amplios abiertos y0/12páginas completamente aceptadas.
