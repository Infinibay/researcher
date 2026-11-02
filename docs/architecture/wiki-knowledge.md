# Wiki con alcance y revisiones verificables

Estado: implementación parcial de la modernización. El adaptador común sirve al
propietario, a las herramientas nativas y a los tres adaptadores Wiki heredados.
No sustituye todavía todos los roles, flows ni proveedores de recuperación antiguos.

## Identidad y corrección

Una página pertenece a un proyecto o a la biblioteca global. La ruta se conserva
exactamente: no se añade `/` ni se busca automáticamente en global al faltar una
página local. La misma ruta puede existir en dos proyectos y en global.

Para actualizar o borrar se necesitan **page_id y revisión observados**. La revisión
sola permitiría editar por accidente una página borrada y recreada con revisión 1.
Una creación declara revisión0 y ninguna identidad previa. Cambiar padre exige que
exista en el mismo alcance, sin ciclos y dentro del límite de profundidad 64.

Ejemplo: Ana lee página 42/revisión 3; Bruno guarda revisión 4. El borrador de Ana
recibe conflicto, se conserva y puede compararse con la revisión 4. Elegir preparar
una sobrescritura cambia explícitamente la base observada; no mezcla texto ni
demuestra que Ana haya comprendido el cambio de Bruno.

La operación y su recibo se guardan en la misma transacción. Un reintento con la
misma clave e intención recupera el resultado original incluso después de otra
edición o borrado; reutilizar la clave para una intención distinta falla. Las
versiones retenidas sobreviven al borrado y verifican su hash. Las lecturas y
ediciones actuales rechazan cambios que eludan el registro de revisiones.

## Herramientas y fuentes

El catálogo de negocio contiene 19 herramientas; cinco corresponden a Wiki:
`researcher_wiki_list`, `researcher_wiki_read`, `researcher_wiki_write`,
`researcher_capture_wiki` y `researcher_capture_wiki_collection`.
El host fija proyecto, tarea y actor; el modelo no elige otra identidad.
Lectura exige `wiki.read`, escritura `wiki.write`; la escritura nativa es sólo
del proyecto. La edición global del propietario requiere selección explícita.
[Schemas canónicos](../modernization/wiki-tool-schema.json).

Leer una nota no crea una fuente para citar. Capturar fija página/revisión/alcance,
texto y hash, incluso cuando posteriormente se edita o elimina la página activa.
La captura de colección admite 1–50 miembros distintos y un máximo de 200000 bytes
de texto; cualquier miembro inválido rechaza el conjunto. Las unidades conservan
identidad de página/revisión, hash y offsets exactos en el snapshot normalizado.

La búsqueda del índice es léxica FTS5. La recuperación semántica opera sobre las
revisiones explícitamente capturadas con el [worker local fijado](semantic-source-retrieval.md).
No afirma haber buscado toda la biblioteca ni demostrar ausencia de ideas similares.
Las notas aportan contexto; ninguna marca de guardado valida científicamente su texto.

## Persistencia y migración 33

La migración reemplaza la unicidad global de ruta por índices parciales por alcance,
conserva identidades, referencias, secuencia, índices/triggers y búsqueda FTS. Amplía
`research_sources` para admitir Wiki y conserva su contenido previo. Todo el cambio
se revierte ante un fallo, comprobando las referencias antes y después.

El estado importado se registra como `legacy_snapshot`: es una observación actual,
no una historia reconstruida. Si falta `updated_by`, el autor de ese texto es
desconocido; `created_by` no demuestra quién lo escribió. Nuevas ediciones registran
el actor y origen `adapter_write`, e invalidan el vector antiguo de la página.
La restauración de esquema heredado sólo admite un estado sin cambios Wiki nuevos
ni fuentes Wiki. Rechaza una reversión con pérdida; no fusiona páginas homónimas.

Límites de edición: ruta 512, título 1200, cuerpo 200000 bytes UTF-8. Índice con cursor,
historial paginado y ventanas de lectura limitadas. Las revisiones retenidas requieren
una política futura de conservación y recuperación integral; no se promete historial
ilimitado gratuito ni una restauración completa de producción.

## Interfaz y límites pendientes

Cuaderno con índice persistente y lector amplio; móvil separa índice y documento.
Alcance, revisión, fecha UTC y autor desconocido permanecen explícitos. Los borradores
viven en memoria y sobreviven a navegación/cambios de proyecto; cerrar el navegador
puede perderlos. Se avisa ante salida pendiente. Un recibo tardío confirma sólo su
intención y no redirige otro documento ni borra una edición posterior.

Los adaptadores antiguos comparten identidad y escritura protegida. `SearchWiki`
todavía utiliza su proveedor semántico configurado, con paginación y limitaciones de
texto explícitas. `wiki_updated` es un aviso heredado, no evidencia de planificación
nativa. La invalidación de hallazgos/contexto dependiente, migración total de roles,
retirada de CrewAI/RAG, retención y aceptación humana permanecen pendientes.

[Pruebas y límites de navegador](../design/audits/2026-11-01-wiki/report.md).
