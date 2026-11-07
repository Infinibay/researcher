# Importación de datos históricos

`stage-legacy-host` prepara una instalación nueva desde una base anterior al
runtime nativo, con versión reconocida hasta17. Conserva identificadores,
relaciones, archivos originales y una copia SQLite previa a las migraciones.
El resultado queda pendiente de reinscripción. No ejecuta tareas antiguas ni
convierte informes históricos en resultados revisados o aceptados.

Detener primero los escritores de la instalación antigua. El bloqueo SQLite y
las comprobaciones de archivos detectan cambios normales durante la captura;
no garantizan coherencia de un índice que otro proceso sigue modificando.
El original conserva sus filas de aplicación. SQLite puede hacer checkpoint y
cambiar sus archivos físicos; no se promete identidad binaria de WAL/SHM.

## Asignación explícita

Crear un manifiesto como este, sustituyendo rutas y proyectos por los reales:

```json
{
  "format": 1,
  "storage": [
    {"name": "reports", "path": "/datos/antiguos/informes", "stored_prefix": "/artifacts"},
    {"name": "uploads", "path": "/datos/antiguos/adjuntos", "stored_prefix": "/research/uploads"},
    {"name": "repos", "path": "/datos/antiguos/repos", "stored_prefix": "/research/repos"}
  ],
  "chroma_exports": [
    {"path": "/datos/exportacion-chroma", "projects": {"coleccion-alpha": 101, "coleccion-beta": 202}}
  ]
}
```

Las listas pueden estar vacías si no hay material de ese tipo. Los prefijos son
las rutas guardadas por el sistema antiguo, a menudo dentro de un contenedor;
`path` es la carpeta real del host. Cada ruta registrada debe tener una única
correspondencia. Las raíces y prefijos no pueden solaparse. La base original
debe estar fuera de las carpetas de almacenamiento asignadas.

```bash
researcher-bootstrap stage-legacy-host \
  --database /datos/antiguos/infinibay.db \
  --storage-manifest /datos/asignaciones.json \
  --destination /datos/instalacion-importada-nueva
```

El destino no debe existir y su padre sí. Se copian los árboles completos,
incluidos archivos sin registro y cambios Git sin commit. Los adjuntos registrados
se trasladan al almacenamiento del proyecto; repositorios y worktrees activos
reciben las rutas nuevas, incluidas sus referencias administrativas Git.
Los enlaces se conservan como evidencia, pero no se siguen para leer informes
o adjuntos. Una ruta ambigua, ausente o no asignada detiene la importación.

Sólo los informes cuyo contenido en SQLite es `NULL` se leen desde su archivo
exacto, con UTF-8 y límite de16MiB. El contenido ya guardado prevalece. No se
buscan nombres parecidos ni se inventan revisiones. La API de investigación los
identifica como `legacy_unverified`.

## Documentos que sólo quedaron en Chroma

El exportador separado usa Chroma1.5.9 fijado en su lock; no añade esa dependencia
al servidor. Ejecutarlo sobre datos detenidos y conservar su salida completa:

```bash
uv run --locked scripts/export_legacy_chroma.py \
  --source /datos/antiguos/chroma \
  --output /datos/exportacion-chroma
```

Primero copia SQLite y los índices; abre con Chroma una segunda copia desechable.
Cualquier actualización de formato afecta esa copia. El lector requiere Linux y
bubblewrap con soporte `--bind-fd`; si no están disponibles, no hay ejecución sin
aislamiento. El proceso recibe sólo el intérprete y sus bibliotecas, el script,
la copia de lectura y su salida temporal. No recibe el directorio original,
credenciales del entorno, entrada estándar ni la red del host. Los namespaces
separan también procesos y montajes. El proceso principal supervisa su tiempo;
al vencerlo conserva la copia y no publica `manifest.json` completo.

El lector limita espacio de direcciones a4GiB, CPU, descriptores y tamaño por
archivo. Esto **no** impone una cuota agregada de disco ni límites de memoria/PIDs
para todo un árbol de procesos. Sigue siendo necesario detener los escritores
originales antes de copiar; la prueba del lector no certifica cambios hostiles
concurrentes durante el snapshot. No se ha eliminado el aviso de Chroma ni se
consideran seguros todos los formatos por haber añadido una barrera de proceso.
[Evidencia y alcance](../modernization/chroma-isolation-review.md).

Exporta colecciones, IDs,
texto y metadatos mediante `get`, paginados, sin generar embeddings. La API
[Get de Chroma](https://docs.trychroma.com/docs/querying-collections/query-and-get)
recupera registros directamente; el
[cliente persistente](https://docs.trychroma.com/reference/python/client)
permite abrir almacenamiento local y seleccionar sus colecciones.
La instalación inicial del entorno aislado puede descargar dependencias.

Cada colección necesita una asignación explícita a un proyecto existente. Un
campo `project_id` dentro de sus metadatos se conserva como dato histórico, sin
usarlo como autorización. Por ejemplo, el operador puede asignar la colección
al proyecto101 aunque un metadato diga202; ambas afirmaciones quedan distinguidas.

Cada registro con texto crea un adjunto independiente. No se reconstruye un PDF
completo a partir de fragmentos ni se inventa una tarea de origen. Los registros
sin texto permanecen en el manifiesto y la exportación, sin adjunto ficticio.
Al capturar después el fragmento como fuente, se conserva colección, ID, página
y otros metadatos, asignación explícita y la advertencia de documento incompleto.
El esquema58 vincula esa procedencia al hash de los bytes: un archivo modificado
no hereda la atribución anterior. La inversa de58 sólo admite una tabla sin uso;
rechaza borrar procedencia ya registrada o esquemas posteriores.

## Activación, límites y recuperación

La salida incluye `.imports/<id>/original.db`, los archivos copiados y el
manifiesto completo. El recibo pequeño de restauración referencia ese manifiesto
por ruta y hash, sin crecer proporcionalmente al número de fragmentos. La marca
`restored_pending_enrollment` se publica al final. Seguir entonces
[la reinscripción con autoridad nueva](installation-backup.md).

Un fallo conserva el destino parcial inactivo. Inspeccionar el error y repetir
sobre otra ruta nueva, preservando la evidencia original. Para instalaciones
que ya usan el runtime nativo se requiere `backup-host` y su evidencia de
autoridad; este importador no evita esas comprobaciones.

Importación y exportación tienen límites explícitos de bytes, archivos y tiempo;
los valores predeterminados son20GiB,200000 entradas y300 segundos. Cada registro
Chroma tiene un límite de16MiB. Reservar además espacio para las copias SQLite,
índices, lector temporal y adjuntos; el límite no representa una cuota total de
disco de todo el procedimiento. No se afirma compatibilidad con cada versión
histórica de Chroma ni con modificaciones hostiles del filesystem durante la copia.

[Ensayo y alcance comprobados](../modernization/legacy-import-results.json).
La ubicación de los datos reales del propietario sigue pendiente: este trabajo
no constituye su migración ni aceptación integral del producto.
