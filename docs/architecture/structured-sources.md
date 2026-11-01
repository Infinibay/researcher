# Fuentes estructuradas: CSV, JSON, XML y DOCX

`researcher_capture_reference` captura estos adjuntos por el mismo permiso de proyecto,
almacenamiento y recibo idempotente que texto/PDF. No usa CrewAI, un índice global ni
inferencias dentro de una herramienta. La búsqueda literal y la semántica local
existentes operan sobre la revisión guardada.

La fuente conserva SHA-256 de bytes originales, SHA-256 del texto normalizado,
formato, método, límites, interpretación y offsets. Una cita corresponde a ese texto
normalizado; no demuestra el formato visual, una lectura completa ni validez científica.
Una repetición con la misma clave devuelve el recibo comprometido, incluso después de
borrar el adjunto. Las capturas históricas conservan su contenido; no se reinterpretan.

| Formato | Contexto conservado | Interpretación y límites |
|---|---|---|
| CSV | Todos los registros; columna numerada, encabezado supuesto y valor; distingue celda vacía, ausente y columna extra | La primera fila se conserva y **se supone** encabezado. El delimitador se infiere entre coma, punto y coma, tabulador y barra; si la detección falla, se elige coma. Se registra el elegido, sin verificar que represente la intención del autor. Los registros multilínea son un registro lógico, no números de línea física |
| JSON | Punteros RFC 6901, índices de listas, escalares y contenedores vacíos; tokens numéricos originales | Claves duplicadas y NaN/Infinity fallan. `0.10000000000000001` y `1e+03` conservan sus tokens; no se convierten a float. Espacios y escapes del original no son citas literales |
| XML | Rutas con nombres expandidos por namespace, atributos, texto, colas y elementos vacíos | DTD, entidades y referencias externas prohibidas, también con UTF-16. Comentarios/instrucciones de procesamiento y serialización original fuera del alcance |
| DOCX | Párrafos del cuerpo principal y texto en celdas de tabla, con su ruta y orden | Lee dos partes conocidas del ZIP sin extraer al disco. Omite imágenes/objetos, notas, comentarios, encabezados/pies, revisiones eliminadas e instrucciones de campos. Los resultados visibles de campos pueden estar desactualizados. No inventa páginas ni verifica el diseño |

Ejemplo: un resultado extraído de Word puede tener el locator
`/body/tbl[1]/tr[1]/tc[1]/p[1]`: primer párrafo de la primera celda, en la primera fila
de la primera tabla del cuerpo. Identifica de dónde procede el texto extraído; no
significa «página 1» ni demuestra que una imagen de esa tabla haya sido analizada.

```mermaid
flowchart LR
    A[Adjunto del proyecto] --> B[Worker limitado y cancelable]
    B --> C[Snapshot normalizado con hashes y unidades]
    C --> D[Lectura o búsqueda literal/semántica]
    D --> E[Cita exacta y hallazgo provisional]
    E --> F[Informe borrador]
```

## Recuperar texto y estructura sin llenar el contexto

- `researcher_source_read` pagina texto con `offset/max_chars` y `next_offset`.
  La procedencia resume `unit_count`; no repite miles de locators en cada ventana.
- `researcher_source_structure(source_id, after_index=0, limit=50)` lee las unidades,
  hasta 100 por página y 12.000 bytes de unidades codificadas. Seguir `next_index`
  hasta `null`; no confundir unidades omitidas con ausencia de evidencia.
- Cada unidad contiene `index`, `kind`, `locator`, `start_offset`, `end_offset`.
  Son caracteres Python en el snapshot, no bytes originales. Las búsquedas devuelven
  `unit_indices` para recuperar el contexto estructural del pasaje.
- HTTP: `GET /api/research-tools/sources/{id}/units`. El proyecto/actor/tarea provienen
  del grant, no de argumentos del modelo. Un lector de otro proyecto recibe 404.
- Los PDFs conservan su metadata de páginas; un texto/PDF sin unidades devuelve una
  página estructural vacía. El catálogo de negocio tiene ahora 14 herramientas.

[Schema y anotaciones canónicos](structured-tool-schema.json).

## Límites y cierre

Se reutilizan `DocumentParser` y el worker/IPC existentes; `PDFParser` conserva su API.
Formato/programa seleccionados por el host, sin rutas ni ejecutables elegidos por el
modelo. El worker no hereda credenciales; aplica CPU 2 s (hard 3), AS 256 MiB, plazo
5 s, entrada 1.000.000 bytes y salida IPC 2.000.000 bytes. El resultado sólo se
publica después de recoger el proceso. Cambiar de formato conserva permiso y límites.
Esto no es una sandbox general de filesystem/red ni un presupuesto agregado del host.

El snapshot admite 200.000 bytes UTF-8, 5.000 unidades y locators de 1.024 bytes.
JSON/XML: profundidad 64 y 20.000 nodos; CSV: 256 columnas y campos de 65.536 caracteres;
DOCX: 512 miembros, 8 MB de expansión declarada total y 4 MB por parte leída.
ZIPs con traversal, entradas duplicadas, cifrado o compresión no soportada fallan.
No se guarda una fuente parcial ante exceso o sintaxis ambigua/inválida.

`defusedxml 0.7.1` ya estaba instalado transitivamente y ahora es dependencia directa.
No cambia ninguna versión resuelta. La previa del propietario reutiliza la misma
extracción, explica sus límites y permite descargar bytes exactos; no crea una fuente.

## Evidencia y pendientes

[Pruebas y regresión](../modernization/formats-results.json),
[paquete aislado](../modernization/formats-packaging.json),
[previas reales en navegador](../design/audits/2026-11-01-structured-files/evidence.json).
Se prueban los cuatro formatos por fachada nativa → API → cita → draft; además,
embeddings reales locales sobre JSON, contraevidencia tardía en una tabla DOCX,
paginación completa y aislamiento. No hubo turnos LLM ni evaluación de síntesis.

Los antiguos registries/roles/flows que usan CrewAI o el RAG global todavía requieren
migración explícita. Esta ampliación no retira sus consumidores ni cierra la evaluación
representativa de documentos complejos. La UI conserva cuatro pilotos y cero páginas
con aceptación completa; este ajuste de previas no es otro rediseño aceptado.
