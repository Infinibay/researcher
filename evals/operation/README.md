# Ensayos de operación

`restored_host.py` prepara una instalación sintética nueva, guarda una solicitud
pendiente, crea/verifica una copia y la restaura en otra ruta. Reinscribe esa copia
con autoridad y acceso nuevos; envía una sola solicitud nueva mediante HTTP,
comprueba Ken, cálculo, citas e informe y reinicia el servicio conservando sus
resultados. La instalación original y su solicitud no se ejecutan ni reemplazan.

```bash
/ruta/al/entorno/bin/python -I evals/operation/restored_host.py \
  --live \
  --assets /ruta/privada/recursos-host.json \
  --output /ruta/privada/ensayo-nuevo
```

El entorno debe tener el paquete instalado. `-I` mantiene sus imports fuera del
checkout; el harness carga sólo su auxiliar de operación desde este repo. Los
recursos tienen el formato de [preparación del host](../../docs/architecture/native-host-installation.md),
incluyendo la cuenta por suscripción, Ken publicado, sus modelos locales y un
cgroup delegado. Configurar `project_turn_limit:1` y `limits.max_turns:1`, además
de límites explícitos de tiempo, herramientas y tokens. El directorio de salida
debe ser nuevo y su padre debe existir. No pasar una instalación del propietario
como salida ni reemplazar recursos existentes.

La intención y su clave quedan en `result.json` antes del envío HTTP. Una pérdida
de respuesta o del observador no autoriza otro turno. Conservar el proceso/handle
original mientras siga vivo; después inspeccionar su base y recibo. El siguiente
comando sólo lee el resultado original y escribe `verification.json`; no arranca
servicios ni modelos:

```bash
/ruta/al/entorno/bin/python -I evals/operation/restored_host.py \
  --verify-root /ruta/privada/ensayo-original
```

La verificación exige el run original, un único dispatch completado, un cálculo
con salida200/exit0, cita literal contenida en su fuente, informe draft, procesos
registrados cerrados y la respuesta de `ken_read` correlacionada con el código
esperado. Un nombre de herramienta o una afirmación del modelo no bastan.
El chequeo del trace está limitado a esta fixture; no es un intérprete general de
JavaScript ni certifica atribución de resultados adversariales.

`host_smoke.py` conserva el ensayo de preparación/arranque nuevo y
`native_container.py` el ensayo rootless con el observador del host. Ninguno de
estos ensayos demuestra por sí solo un reboot del kernel, pérdida de energía,
migración de datos históricos del propietario, calidad científica o comprensión
humana. [Resultado actual del host restaurado](../../docs/modernization/restored-host-evaluation-results.json).

## Reinicio real del kernel en una VM desechable

`reboot_vm.py` construye un initramfs y un disco ext4 privados y arranca un único
proceso QEMU/KVM. El primer arranque crea datos sintéticos, una solicitud y un
registro de proceso pendiente. El segundo observa otro identificador de kernel,
comprueba el rechazo de la autoridad anterior y ejecuta los comandos públicos de
copia tras reboot, restauración y reinscripción. Comprueba un proceso no-op real
y lee los datos retenidos mediante la API nativa instalada.

```bash
/ruta/al/entorno/bin/python -I evals/operation/reboot_vm.py \
  --output /ruta/privada/ensayo-vm-nuevo \
  --qemu /ruta/herramientas/usr/bin/qemu-system-x86_64 \
  --kernel /ruta/vmlinuz \
  --assets /ruta/privada/recursos-host.json \
  --runtime-env /ruta/al/entorno \
  --timeout 240
```

Requiere UID1000, acceso a `/dev/kvm`, Python3.12 portable, `cpio`, `mkfs.ext4`,
Git/bubblewrap y un kernel x86_64 con ext4 y virtio integrados. QEMU debe incluir
sus bibliotecas y firmware bajo el mismo prefijo `usr`. La invocación sigue el
[arranque directo de Linux](https://www.qemu.org/docs/master/system/linuxboot.html)
y las [opciones del emulador](https://www.qemu.org/docs/master/system/invocation.html).

Se copian el entorno instalado y los binarios/modelos públicos ya preparados;
el archivo de cuenta real no se lee ni copia. Se crea una credencial sintética,
no se instala una tarjeta de red y no se admite inferencia. El reinicio y apagado
ocurren dentro del guest, protegidos por PID1 y la marca del initramfs. No ejecutar
los auxiliares `reboot_guest*.py` como administración del host.

El plazo corresponde al proceso QEMU original. Al vencer, el harness termina
ese proceso y conserva `disk.raw`, `serial.log` y `host-result.json`; no reintenta.
Un timeout del observador externo requiere seguir el mismo handle. Este ensayo
no cubre pérdida de energía, datos reales del propietario, un agente nativo
ejecutándose durante el reboot ni prueba de cierre del host original.
[Resultado y alcance del ensayo actual](../../docs/modernization/reboot-recovery-results.json).

## Importación de SQL, archivos y Chroma reales sobre datos sintéticos

`legacy_import.py` usa el backend instalado y un entorno separado con
`chromadb==1.5.9`. Crea dos colecciones con105 registros, incluido uno sin texto;
exporta en páginas de100 y ejecuta el comando público de importación. Comprueba
la captura de texto con procedencia histórica, un informe sólo en archivo y
lecturas HTTP del host reinscrito, incluido rechazo desde otro proyecto.

```bash
/ruta/al/entorno/bin/python -I evals/operation/legacy_import.py \
  --output /ruta/privada/ensayo-importacion-nuevo \
  --legacy-python /ruta/al/entorno-chroma/bin/python \
  --assets /ruta/privada/recursos-host.json
```

El entorno de compatibilidad se puede preparar exportando el lock de
`scripts/export_legacy_chroma.py` e instalándolo en un virtualenv separado.
Fixture y exportador corren con bubblewrap sin red; usan vectores explícitos y
no generan embeddings. El host usa recursos reales, pero una cuenta sintética
y cero solicitudes de inferencia. El archivo de cuenta real no se copia.
El proceso original conserva `result.json` incluso ante fallo; no reintenta.
[Guía del operador](../../docs/architecture/legacy-import.md),
[resultados y límites](../../docs/modernization/legacy-import-results.json).
