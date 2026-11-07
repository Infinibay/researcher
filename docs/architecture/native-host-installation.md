# Preparar y arrancar una instalación nativa nueva

`researcher-bootstrap init-host` prepara almacenamiento y configuración usando
recursos explícitos del operador. `researcher-start --installation` arranca esa
instalación desde el paquete instalado y sirve la web compilada desde la API.
La configuración incluye el modelo; no está fijado por el launcher.

## Recursos necesarios

Partir del [ejemplo de recursos](../config/host-assets.example.json) y sustituir
todas las rutas por las de esta instalación:

- Codex CLI 0.166.0 y su ejecutable `codex-code-mode-host` del mismo paquete.
- Instalación aislada del paquete publicado `ken-rank==0.18.0`, con su comando
  `ken`, y caché de los modelos fijados por ese paquete. La preparación verifica
  tamaño y SHA-256 de cada artefacto; no descarga pesos durante el arranque.
- Archivo de cuenta de la suscripción de Codex, privado y administrado por el
  usuario. Se conserva su ubicación; los tokens no se copian a la configuración.
- Linux con cgroup v2 delegado al usuario del servicio, controladores `memory`
  y `pids` habilitados, y soporte de los dominios nativos del proyecto.
- Web ya compilada, con `index.html`, si se desea servir la interfaz. Sin
  `static_dir`, el launcher sólo sirve la API.

`model`, límites de recursos, límites de turno y presupuesto del proyecto son
opciones explícitas. Que el archivo de cuenta sea válido localmente no demuestra
disponibilidad remota del modelo ni saldo/cuota de la suscripción. Se mantiene
la validación del runtime al admitir una tarea.

## Inicialización y comprobación

Los directorios padre deben existir. Los dos destinos deben ser nuevos y
separados; el testigo de autoridad queda fuera del directorio de instalación.

```sh
researcher-bootstrap init-host \
  --directory /srv/researcher/new-installation \
  --witness-dir /srv/researcher-witness/new-installation \
  --assets /etc/researcher/host-assets.json

researcher-bootstrap check-host \
  --directory /srv/researcher/new-installation --probe

researcher-start --installation /srv/researcher/new-installation --port 8000
```

`init-host` crea una base nueva, autoridad y testigo, directorios de fuentes,
control, adjuntos, autenticación, logs y servicio. Guarda `runtime.json` y el
marcador `installation.json` con permisos privados. Las comprobaciones previas
no llaman a modelos. Un fallo posterior conserva el estado parcial para
inspección; volver a inicializar sobre ese estado se rechaza.

`check-host` verifica recursos, autoridad y base. `--probe` añade un hijo de
cómputo fijo que termina inmediatamente, dentro de un dominio nuevo con límites;
observa su cierre y eliminación. No es una tarea de investigación ni acredita
el ciclo completo del producto. `researcher-start --check` tiene un alcance
menor: comprueba requisitos del servicio sin arrancarlo.

La API escucha en `http://127.0.0.1:8000`. Emparejar al propietario con el archivo
privado indicado al arrancar; nunca enviarlo al agente como contexto de tarea.
El supervisor observa sus procesos originales al cerrar. Un SIGTERM ordenado
devuelve 143, y el reinicio requiere un nuevo emparejamiento.

## Ensayo de extremo a extremo

Con una instalación **vacía, desechable y sintética**, el runner ejecuta el
launcher instalado, comprueba HTTP y acceso, cierra, reinicia y compara el estado:

```sh
python evals/operation/host_smoke.py \
  --installation /srv/researcher/test-installation \
  --output /tmp/researcher-host-check
```

Añadir `--live` envía exactamente una admisión a la suscripción configurada:
Ken localiza y lee código, el agente captura una referencia, calcula un total
y guarda un hallazgo provisional y un informe borrador. El ejemplo le pide
explicar en español qué leyó y qué ejecutó. El runner no acepta ni publica
resultados y no reintenta una ejecución incierta. No usar datos del operador.
La salida conserva metadatos y logs privados; no subir historiales ni credenciales
al repositorio. [Resultados y límites](../modernization/host-installation-results.json).

## Alcance pendiente

Esta ruta prepara un host con recursos ya disponibles. Siguen pendientes el
aprovisionamiento automático/delegación portable, la incorporación o recuperación
de actores anteriores y la restauración de datos reales. La
[ruta de contenedor nativo](native-container-operation.md) tiene ahora su propio
ensayo de admisión y reinicio, con alcance Linux explícito. La ruta no migra una instalación existente ni
reemplaza sus identidades de autoridad. La renovación de cuenta debe respetar
el contrato de autenticación; no se ha probado aquí como un ciclo completo.

La prueba del transporte incluye el event loop que selecciona Uvicorn en el
launcher instalado. Los pipes transfieren descriptores independientes al loop
y liberan los originales: así, el cierre diferido no puede cerrar un descriptor
que ya se reutilizó, y cerrar stdin sí entrega EOF al proceso. Se comprueba tanto
con `asyncio` como con `uvloop`, incluyendo comandos y operaciones Git.


## Copiar y restaurar los datos

`researcher-bootstrap` incorpora `backup-host`, `verify-backup` y `restore-host`.
Ver la [guía de copia y restauración](installation-backup.md). La copia incluye
base, archivos y repositorios/worktrees; las cuentas y herramientas externas
permanecen como referencias. Restaurar produce datos comprobados en otra ruta,
con acceso/autoridad originales archivados y ejecución pendiente de reinscripción.
`enroll-restored-host --directory ... --witness-dir ... --assets ...` crea una
autoridad nueva, pausa planes copiados y conserva trabajo anterior como historial.
El navegador conserva/archiva decisiones anteriores antes de entrar en la nueva
instalación. El comando no adopta procesos ni efectos remotos del host original.
La recuperación operativa completa tras reboot sigue abierta.
