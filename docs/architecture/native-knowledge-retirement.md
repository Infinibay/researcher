# Conocimiento: reemplazos nativos y retirada de herramientas antiguas

Se retiran 13 herramientas y 15 módulos de `backend.tools.knowledge`. Las
capacidades se conservan en el catálogo nativo y sus almacenes canónicos; no se
borran findings, informes, referencias, páginas Wiki, vectores ni revisiones.

| Herramientas anteriores | Reemplazo y contrato |
| --- | --- |
| `record_finding` | `researcher_finding_record`: alcance y autor del grant, citas sobre fuentes guardadas, estado provisional y recibo por operación. No se importan confianza numérica del modelo, deduplicación aproximada ni embeddings implícitos como prueba científica. |
| `read_findings` | `researcher_finding_list` y `researcher_finding_read`: filtros dentro del proyecto, metadata paginada, cuerpo completo y citas con cursores independientes. Confianza desconocida permanece desconocida. |
| `search_findings` | `researcher_finding_query`: corpus completo acotado, encoder local fijado, resultados por fragmento y fingerprints para continuar. No se conservan vectores antiguos sin versión ni muestreo silencioso; un score de similitud no es confianza científica. |
| `summarize_findings` | `researcher_finding_summary` y lista paginada: conteos completos y temas; no introduce otro LLM para resumir. |
| `validate_finding`, `reject_finding` | Admisión de revisión independiente y `researcher_review_decide` sobre sujeto/hash exactos. No se transporta la mutación directa de flags por nombre de rol. Veredicto, aceptación de tarea y validez científica no son equivalentes. |
| `read_finding_reviews` | `researcher_review_read`: historial real, decisión y sujeto original, ventanas y vigencia explícita. Leer feedback no concede permiso para revisarlo ni aceptarlo. |
| `search_knowledge` | Nueva `researcher_knowledge_search`, reutilizando el buscador canónico con permisos por fuente dentro del mismo snapshot. Conserva la búsqueda conjunta y distingue fuente fallida de ausencia de coincidencias. |
| `write_report` | `researcher_report_write`: informe draft y sus relaciones con findings en una transacción con recibo. No escribe un archivo fuera del control del host ni informa éxito si falta el registro. |
| `read_report` | `researcher_report_read` por ID exacto: texto/citas paginados, ahora también para informes históricos con contenido retenido en DB y procedencia explícita. |
| `read_wiki`, `write_wiki` | `researcher_wiki_list/read/write`: namespace explícito, identidad/revisión observadas y recibos; sin fallback global ni embeddings ocultos. |
| `search_wiki` | Búsqueda léxica nativa; para paráfrasis, captura de las revisiones seleccionadas mediante `researcher_capture_wiki_collection` y `researcher_source_query`. La selección y límites son visibles; no se pretende haber buscado toda la Wiki. |

## Búsqueda conjunta y lectura histórica

Cada fuente solicitada exige su permiso existente: `findings.read`, `wiki.read`,
`sources.read` para metadata de referencias, o `reports.read`. Se comprueban
todos antes de leer, dentro de la misma transacción que obtiene resultados.
No se devuelve silenciosamente un subconjunto autorizado. El modelo no elige
proyecto, actor ni task scope. Un contexto obsoleto bloquea la consulta.

El namespace global sólo se consulta si se pide explícitamente para Wiki.
Cada fuente informa cobertura, error si corresponde y su cursor. Las referencias
se buscan por metadata; eso no significa haber leído el archivo. Las vistas
previas requieren recuperar el registro completo antes de usar su contenido.

Un informe sin registro nativo puede leerse si conserva su texto en `artifacts`.
Se identifica como `legacy_unverified`; su hash se calcula sobre los bytes
observados y no acredita integridad original, revisión o aceptación. No se le
crea un registro nativo ni se lo adopta como resultado aceptado. El lector no
abre rutas del filesystem ni adivina un informe por similitud de nombre.

**Límite principal pendiente de datos:** un informe histórico cuyo contenido sólo
existe en un archivo necesita restauración/importación explícita del artefacto
registrado. El lector comunica que los bytes no están retenidos; no presenta un
texto vacío ni una ruta adivinada como recuperación exitosa. Resolver esa
restauración forma parte del bloque de migración, no del pulido secundario.

## Verificación y alcance

`test_knowledge_access.py` recorre MCP/API/SQLite reales, permisos de todas las
fuentes, cambios de contexto, fallos parciales, paginación, aislamiento y lectura
de informes antiguos. Los contratos existentes conservan citas, revisión,
aceptación de resultados, Wiki y búsquedas semánticas. Se retiran 21 funciones
de test específicas de wrappers; no se contabilizan como fallos reparados.
La prueba de capacidad compartida entre instancias del encoder permanece.

Véanse [resultados](../modernization/knowledge-retirement-results.json),
[paquete instalado](../modernization/knowledge-retirement-packaging.json) y
[alcance del análisis de imports](../modernization/knowledge-retirement-imports.json).
Las pruebas de migración/reversión fallidas se comparan con el paquete anterior;
no se debilitan sus protecciones para convertir este lote en una suite verde.
No hay nueva aceptación global, científica, humana o de páginas completas.
Las cinco dependencias legacy, sus auxiliares y los servicios/CLI antiguos
restantes continúan como trabajo principal.
