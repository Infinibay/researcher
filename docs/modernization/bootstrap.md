# Inicialización explícita y arranque

Esta guía distingue crear una instalación **nueva** de abrir una instalación
existente. El servidor API, `researcher` y `start.sh` ya rechazan una base ausente,
vacía o sin historial reconocido. Los datos no se recrean por arrancar.

## Primera instalación: base de producto

Desde el repositorio de la aplicación:

```bash
uv sync --locked
export INFINIBAY_DB="${XDG_STATE_HOME:-$HOME/.local/state}/researcher/source.db"
uv run --locked researcher-bootstrap init-db --database "$INFINIBAY_DB"
uv run --locked python -m backend.api.run
```

`init-db` exige un archivo nuevo. Crea directorios necesarios y un archivo privado
`0600`, aplica el esquema y sus migraciones, sincroniza y devuelve su ruta en JSON.
Rechaza cualquier archivo existente, incluso vacío o symlink. Repetir el comando
no borra ni adopta datos. Para volver a servir, repetir sólo el arranque del API.

Sin `INFINIBAY_RUNTIME_CONFIG`, el API permite consultar datos y rechaza admitir
trabajo de inferencia con un diagnóstico de configuración pendiente. Para ejecutar
investigación, usar el [perfil de suscripción y Ken](../architecture/owned-product-runtime.md).
La configuración, cuenta, datos y controles del host deben quedar fuera de los
repositorios administrados por los agentes.

## Primera instalación: almacenamiento de autoridad

El perfil `owned-codex-v1` abre una autoridad ya inicializada. Crear ese estado es
una operación explícita de operador, separada de servir y recuperar. Los padres
de las dos rutas siguientes deben existir y ser rutas confiables del operador:

```bash
state_root="${XDG_STATE_HOME:-$HOME/.local/state}"
(
  umask 077
  set -C
  uv run --locked researcher-bootstrap init-authority \
    --database-dir "$state_root/researcher-authority-db" \
    --witness-dir "$state_root/researcher-authority-witness" \
    > "$state_root/researcher-authority-config.json"
)
```

Las dos carpetas deben ser nuevas y no estar contenidas una en la otra. Se crean
con modo `0700`; DB, witness y mutex, con `0600`. El comando escribe el formato
existente, un ID nuevo y su genesis vacío; sincroniza archivos/directorios y abre
el journal para verificarlo antes de devolver configuración. La salida contiene
`database`, `witness`, `mutex` y `authority_id`: colocar ese objeto en `authority`
del [JSON del perfil](runtime-owned.example.json) y conservar la identidad externa.
El ejemplo usa `noclobber` para que el shell también rechace sobrescribir esa salida.

**Separar carpetas no garantiza separar restauraciones.** El witness debe quedar
fuera del conjunto que se rebobina junto con la DB de autoridad. Archivar/restaurar
el padre común completo elimina esa independencia. Este comando crea almacenamiento;
no inscribe actores existentes, no delega cgroups, no instala un servicio ni acredita
que un despliegue anterior esté detenido. No sirve para adoptar un host ya en uso.
El aprovisionamiento completo y restore/handoff siguen pendientes del plan.

## Instalación existente y fallos

| Situación | Comportamiento y siguiente acción |
| --- | --- |
| DB reconocida | El arranque aplica migraciones pendientes y conserva los datos. Probar migraciones históricas sobre copia antes de usar datos reales. |
| Ruta de DB ausente | El arranque falla sin crear ni inicializar la base. Verificar selección, permisos y la copia de recuperación de esa instalación. |
| Archivo vacío/desconocido | El preflight de sólo lectura rechaza inicializarlo. Verificar si es la ruta equivocada o una pérdida; no eliminarlo para volver a ejecutar `init-db`. |
| DB/witness/mutex de autoridad ausente | El perfil rechaza configuración. El arranque y el comando de instalación no reconstruyen una autoridad perdida. |
| Inicialización interrumpida | Se conservan rutas parciales para inspección; otro `init` las rechaza. El fallo no devuelve configuración exitosa ni elimina silenciosamente evidencia. |
| Fallo de configuración o entrada/salida del runtime | El lifespan retira grants, sesiones y pairing file, y cierra su archivo de log. Sólo reconcilia flows heredados después de haber alcanzado el estado de servicio. |
| Cancelación mientras se crea el pairing file | Se drena ese trabajo antes del cierre: el hilo no puede dejar una credencial nueva después de la limpieza. |

Este cambio no agrega una migración de esquema ni una conversión de datos. Volver
al código anterior no restaura datos y reintroduce su inicialización implícita;
conservar el estado y diagnosticar el fallo antes de considerar una reversión.
El procedimiento integral de restore y la inscripción de todos los actores se
completarán antes de declarar la migración de producto terminada.

`start.sh` conserva el stack heredado de proveedores y Forgejo, todavía en migración.
Su guardia inicial usa SQLite en sólo lectura antes de servicios, descargas o `.pids`;
después del entorno bloqueado usa el mismo migrador estricto que API y CLI. Las
herramientas internas conservan temporalmente `ensure_migrations()` con creación
permitida para callers explícitos; eso no certifica a todos los escritores heredados.

## Verificación de esta entrega

Los tests ejercitan los comandos en procesos reales, reapertura y commits del
journal, pérdidas de witness, fallo parcial, arranques repetidos, cancelación,
fallos del runtime y el shell con servicios sustituidos por guardias. La fábrica
owned usa ahora el inicializador de producción en su fixture y conserva el recorrido
HTTP/controlador/kernel; sus respuestas de modelo/Ken son controladas. No se repite
inferencia para probar bootstrap. Evidencias y resultados se enlazan en
[bootstrap-results.json](bootstrap-results.json) y [bootstrap-packaging.json](bootstrap-packaging.json).
