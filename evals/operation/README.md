# Ensayos de operación

## Recorrido web con almacenamiento real

`web_workspace.py` crea un host desechable y lo abre desde Chromium: acceso local,
dos proyectos, grupo/hito, dos tareas con dependencia y corrección como ejemplo
del usuario. Comprueba recarga y aislamiento y contrasta los registros con SQLite.
No simula respuestas HTTP. Sustituye la ruta de cuenta de los assets por un archivo
sintético privado; no utiliza la suscripción ni inicia inferencias.

Construir primero la web con `npm run build`. Con el paquete Researcher instalado
en otro entorno, Node24 y el navegador de Playwright ya disponibles:

```sh
<python-del-producto> evals/operation/web_workspace.py \
  --assets <recursos-host.json> --output <carpeta-nueva> \
  --node <node24>/bin/node
```

El directorio de salida conserva el host privado, logs y capturas; no usar una
instalación existente. El comando rechaza imports del backend desde el checkout.
Desde `frontend/`, `npm run test:e2e` ejecuta sólo el script de navegador, con `RESEARCHER_E2E_ORIGIN`,
`RESEARCHER_E2E_OWNER_FILE` y `RESEARCHER_E2E_OUTPUT` de un host desechable nuevo.
El harness configura esos valores y cierra su proceso original al terminar.
El resultado no acredita comprensión humana, generación ni accesibilidad completa.
[Capturas y resultados](../../docs/design/audits/2026-11-07-workspace-live/report.md).

Con los mismos prerrequisitos, `--journey knowledge` comprueba archivos y documentos:

```sh
<python-del-producto> evals/operation/web_workspace.py --journey knowledge \
  --assets <recursos-host.json> --output <otra-carpeta-nueva> \
  --node <node24>/bin/node
```

Retiene una respuesta auténtica de subida después del commit para entregarla
tras cambiar de proyecto. Comprueba previas CSV, descargas exactas, archivos
homónimos y documentos con igual ruta en dos proyectos y biblioteca global.
`npm run test:e2e:knowledge` ejecuta sólo el navegador con las mismas variables.
[Capturas y límites](../../docs/design/audits/2026-11-07-knowledge-live/report.md).

`--journey wiki` comprueba la ruta completa de Documentos en un host nuevo:

```sh
<python-del-producto> evals/operation/web_workspace.py --journey wiki \
  --assets <recursos-host.json> --output <otra-carpeta-nueva> \
  --node <node24>/bin/node
```

Crea dos proyectos y documentos con igual ruta en ámbitos distintos. Recorre
conflicto y comparación, recibo perdido/tardío, borradores al cambiar de proyecto,
revocación real de sesión y recuperación, eliminación con historia retenida,
55documentos en dos páginas de índice,25revisiones y lectura de110KB a320px.
El coordinador contrasta el resultado con SQLite después del navegador y conserva
el host cerrado; no inicia inferencia. `npm run test:e2e:wiki` ejecuta sólo el
navegador con las mismas variables y requiere una biblioteca global nueva.
El fichero del navegador es `browser/evidence.json`; no reutilizar una instalación
anterior para obtener otra observación del mismo intento. Las pruebas de una
página no aceptan U08 ni sustituyen un ensayo humano de comprensión/lector de pantalla.

`--journey files` acepta Archivos contra un host nuevo, sin inferencias:

```sh
<python-del-producto> evals/operation/web_workspace.py --journey files \
  --assets <recursos-host.json> --output <otra-carpeta-nueva> \
  --node <node24>/bin/node
```

Comprueba55adjuntos, búsqueda/paginación, subida/descarga exacta y previas de texto,
PDF,DOCX,CSV,JSON/XML; recibos perdidos/tardíos, errores y eliminación por teclado.
Inyecta fallos SQLite reales sólo en ese host sintético: recuperación de bytes
completos y rechazo/conservación de un original truncado. Al terminar contrasta
recibos y bytes desde SQLite/filesystem, sin convertir previas en fuentes capturadas.
`npm run test:e2e:files` ejecuta el navegador con las variables comunes y
`RESEARCHER_E2E_FILE_FIXTURES`, `RESEARCHER_E2E_DATABASE`, `RESEARCHER_E2E_PYTHON`,
preparadas por el coordinador. El Python debe ser el del producto instalado;
nunca apuntar esta inyección a datos del propietario. [Resultados y límites](../../docs/modernization/files-page-review.md).

`--journey navigation` reutiliza la preparación por formularios de `workspace`
y recorre las12rutas con Tab/Enter a1440y320px CSS. Mide el contenido interior,
captura cada estado, ejecuta Axe sobre la página completa y comprueba salto al
contenido/cierre del menú móvil. Conserva hallazgos de accesibilidad sin borrar
la evidencia funcional; falla si hay un fallo de navegación, HTTP o reflow.
El ancho estrecho no equivale a probar zoom real o un lector de pantalla.
[Resultado con pendientes conservados](../../docs/design/audits/2026-11-07-navigation-live/report.md).

`repositories_workspace.py` prepara otro host nuevo y reutiliza las fixtures
instaladas de TLS/Git y contrato Forgejo controlado; no usa un servidor del usuario:

```sh
<python-del-producto> evals/operation/repositories_workspace.py \
  --assets <recursos-host.json> --output <carpeta-nueva> --node <node24>/bin/node
```

Recorre creación/adopción/clonado, lectura de commits completos, fallo real de
registro SQLite, observación, Stop y reparación explícita que conserva una nota
local. El Git HTTPS es real y verifica su CA privada; la API Forgejo es una fixture
de contrato con credencial sintética. No acredita una cuenta remota real ni hace
push desde el producto. El coordinador conserva el host y sus recibos de cierre.
Después puede ejecutarse la revisión complementaria del original cerrado:

```sh
<python-del-producto> evals/operation/repositories_review.py \
  --original <salida-pasada-del-comando-anterior> --output <otra-carpeta-nueva> \
  --node <node24>/bin/node
```

Agrega registros explícitos, pérdida de recibo, recarga y respuesta tardía entre
proyectos; comprueba que la historia original de preparación no cambie. No repite
clonados ni contacta el proveedor. Los scripts npm correspondientes ejecutan sólo
el navegador: variables comunes, `RESEARCHER_E2E_REPOSITORY_FIXTURE` y, en la revisión,
`RESEARCHER_E2E_REPOSITORY_RECEIPT`; los coordinadores las configuran. No utilizar
estos controles de fallos sobre datos del propietario. [Alcance y evidencia](../../docs/modernization/repositories-page-review.md).

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

Con `--active-command`, el primer arranque mantiene un peer real de comandos
Codex y su hijo ejecutando hasta el reinicio. Primero guarda un cálculo terminado;
después inicia un comando que espera. PID1 comprueba el dueño original, el init
de su namespace privado y el hijo mediante PID, inicio y namespace antes de
reiniciar. Conserva un recibo de esa observación y no cierra el preparador antes
del reboot. El segundo arranque exige el cálculo anterior intacto, el comando
interrumpido como `unknown`, los peers originales archivados sin cierre inventado
y la corrección de contexto conservada. Ningún comando se repite.

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
no cubre pérdida de energía, datos reales del propietario ni inferencia de modelo
durante el reboot. La prueba con comando activo es distinta de la prueba con sólo
un registro preparado. Sus recibos copiados tampoco prueban por sí solos el cierre
de un host original arbitrario.
[Resultado y alcance del ensayo actual](../../docs/modernization/reboot-recovery-results.json).
[Ensayo con proceso activo](../../docs/modernization/active-reboot-review.md).

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
