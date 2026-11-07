# Configuración de modelos durante una exportación de datos

El exportador histórico ahora desactiva los descriptores de funciones de
embeddings en la copia desechable, antes de importar Chroma. Sólo reescribe
los JSON de configuración/esquema de colecciones; conserva parámetros del índice,
textos, metadatos e identidades. La copia cruda mantiene los bytes originales
para inspección. El manifiesto registra cuántos descriptores fueron desactivados.

La revisión de la biblioteca fijada distingue datos JSON de construcción de
objetos: `get_collection` con función explícita `None` no construye el modelo,
pero cargar ciertas propiedades de configuración sí puede llamar a un constructor
registrado. El cambio elimina esa instrucción de configuración en la copia de
lectura, incluso si una ruta de la biblioteca intenta deserializarla después.
[Cliente oficial](https://github.com/chroma-core/chroma/blob/1.5.9/chromadb/api/client.py),
[carga de configuración](https://github.com/chroma-core/chroma/blob/1.5.9/chromadb/api/collection_configuration.py),
[schema](https://github.com/chroma-core/chroma/blob/1.5.9/chromadb/api/types.py).

Se conserva el lector oficial: el segmento de metadatos puede consumir una cola
pendiente a partir de su secuencia aplicada. Leer sólo sus tablas materializadas
no demuestra que se haya recuperado todo el estado.
[Segmento SQLite](https://github.com/chroma-core/chroma/blob/1.5.9/chromadb/segment/impl/metadata/sqlite.py).

## Validación

- 2pruebas rojas reproducen la ausencia de neutralización/recibo.14pruebas finales
  pasan, incluidas las8fronteras existentes de proceso/archivos/red/plazo y la
  lectura real; la cuenta incluye esos casos previos, no14capacidades nuevas.
- Una configuración real con `trust_remote_code` y nombre de modelo no confiable
  exporta105registros. Sus4descriptores quedan desactivados en la copia de lectura;
  el original y la copia cruda conservan la configuración original.
- Un constructor registrado de control sí se activa con la configuración original.
  Después de neutralizarla, el cargador de Chroma devuelve función ausente y no
  llama a ese constructor. No se descarga ni se ejecuta código remoto de prueba.
- Se rechazan claves JSON duplicadas, configuración mayor de1MiB y triggers de
  colecciones, conservando las filas originales. La profundidad se acota a64.
- El ensayo de importación con backend instalado conserva105fragmentos,
  104adjuntos textuales y1registro sólo de metadatos. Se comprueban captura,
  procedencia y lectura HTTP; servicio cerrado con143. Cero modelos/embeddings.
  [Ensayo](dependency-reader-import.json), [corridas](dependency-reader-results.json).

El backend no cambió:618miembros Python/SQL siguen coincidiendo con el wheel
instalado del bloque anterior.13definiciones nuevas/modificadas están documentadas,
83revisiones de prompts vigentes y el lock del exportador verificado.14avisos de
Ruff en los archivos revisados se difieren en DD103. No se repitió la suite global.

## Dependencias que siguen pendientes

La comprobación del registro mantiene Ken0.18.0 con requisito exacto ONNX1.20.1;
ONNX publicado es1.23.2. Chroma publicado sigue en1.5.9 y sus avisos no indican
versiones corregidas. No se cambió un pin por una instalación incompatible ni
se publicó una distribución de Ken. [Metadata observada](dependency-reader-registry.json),
[Ken en PyPI](https://pypi.org/pypi/ken-rank/json),
[ONNX en PyPI](https://pypi.org/pypi/onnx/json),
[Chroma en PyPI](https://pypi.org/pypi/chromadb/json).

La nueva auditoría conserva19entradas/12IDs en ONNX y5entradas/4IDs en Chroma.
Los demás locks Python y el lock frontend no muestran avisos conocidos en esta
consulta. Esto no certifica ausencia de vulnerabilidades. La primera llamada
frontend usó una ruta equivocada de Node; el reintento terminó0 con JSON de npm
sin hallazgos, aunque la etiqueta de salida hizo que el wrapper eligiera el parser
de pip. Se conserva ese error y se interpreta explícitamente la salida original;
no se repiten ni se inventan resultados. [Auditoría](dependency-reader-audit.json).

Los avisos de Chroma siguen visibles. Esta mitigación cubre el lector local aislado;
no certifica un servidor Chroma, todos los formatos o seguridad integral. Ken/ONNX,
licencias y aceptación integral permanecen principales. La siguiente tarea es
comprobar compatibilidad de Ken con ONNX corregido y preparar una distribución
coherente para revisión, sin cambiar el repositorio hermano ni publicar nada.

Bloque **2026-11-07 13:37:40–13:50:53 UTC**, **13 min 13 s** hasta validar.
Siguen43escenarios amplios abiertos y0/12páginas completamente aceptadas.
