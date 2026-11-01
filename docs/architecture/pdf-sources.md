# PDF como fuente de investigación

El recorrido nuevo admite PDF con texto desde referencias subidas al proyecto:
`researcher_reference_list` → `researcher_capture_reference` →
`researcher_source_read/search` → hallazgo con cita exacta → informe borrador.
Reutiliza la misma API, credencial, transacción de fuente y clave de operación.
Ken sigue siendo obligatorio para código; no sustituye la lectura documental.

## Contrato disponible

`BoundedReferenceReader` abre el archivo mediante descriptores relativos a la raíz
de uploads y rechaza traversal, symlinks, archivos no regulares y cambios durante
la lectura. El default sigue siendo1.000.000 bytes de archivo: admitir PDF no
amplía silenciosamente ese límite ni el de los adjuntos de texto.

`extract_pdf` recibe esos bytes, sin rutas ni credenciales. Usa pypdf6.21.4 en modo
estricto y configuración local al contexto. No descifra archivos, ejecuta JavaScript,
lanza conversores externos ni hace OCR. Limita100 páginas,200.000 bytes UTF-8 de
texto resultante y1.000.000 bytes por stream decodificado, además de presupuestos
para filtros, objetos, árbol de páginas e invocaciones de formularios.

El texto guardado lleva marcadores `[Page 1]`, `[Page 2]`, etcétera. Su procedencia
incluye SHA-256 de los bytes originales, tamaño, MIME, extractor/versión, límites,
número de páginas, offsets de caracteres de cada página y páginas sin texto.
Los offsets usan la misma unidad que las ventanas de `source_read/search`, no
coordenadas visuales ni offsets binarios del PDF. El SHA del texto guardado y el
SHA del archivo original identifican cosas distintas.

Un PDF mixto conserva los marcadores de las páginas sin texto y declara
`pages_without_text` y `ocr_performed=false`. Uno sin texto extraíble devuelve
`source_unavailable`422 y explica que necesita OCR. Cifrado y formato inválido
también fallan422; exceso de tamaño/páginas/decodificación/texto falla413. Ninguno
guarda el prefijo leído como si fuera un documento completo. Una clave reintentada
recupera la captura ya guardada aunque se haya borrado o cambiado el original.
La autoridad se vuelve a validar al commit; una extracción terminada después de
revocar el grant no puede guardar evidencia.

## Explicación al usuario y uso de citas

La descripción de la herramienta anuncia formatos y fallos, diferencia extracción
de OCR y exige leer la fuente antes de citarla. Ejemplo de explicación apropiada:
«Pude extraer texto de las páginas1 y3. La2 no devolvió texto; no comprobé su contenido.
La frase citada está en el texto capturado de la página3». Esa explicación requiere
que la procedencia observada contenga esos datos; no es una plantilla para inventarlos.
El orden de lectura, las tablas, fórmulas e imágenes pueden requerir inspección visual.
Una cita exacta demuestra correspondencia con el texto extraído, no verdad científica.

Los documentos siguen siendo datos no confiables; una instrucción dentro de un PDF
no autoriza herramientas, publicación ni cambiar de proyecto. El informe conserva
su estado de borrador y una finalización del runtime no acepta la tarea.

## Validación y límites pendientes

Hay pruebas con PDF binario real, dos páginas, páginas vacías, cifrado, compresión,
página inicial válida seguida de otra que excede el límite, retry tras borrar el
original y revocación entre extracción y commit. Los recorridos HTTP y fachada
nativa ejercitan lectura, búsqueda exacta, cita y borrador sin inferencia ni red
externa. No son una evaluación de comprensión con un modelo o una persona.

**La configuración del parser no es un límite duro de CPU/RSS del sistema operativo.**
Falta la ejecución del parser con recursos y cancelación bajo el dueño del host
para cerrar por completo `read_paper/pdf_search`. No se retiran aún las herramientas
heredadas. También faltan adquisición de PDF por URL, OCR si se decide admitirlo,
DOCX y recuperación estructurada CSV/JSON/XML, interfaz Documentos rediseñada,
previsualización de páginas/citas en producto y migración de consumidores antiguos.
El límite de captura no demuestra que el endpoint heredado de upload limite el
cuerpo antes de almacenarlo; ese endpoint sigue pendiente de modernización.

Fuentes primarias consultadas para el contrato de pypdf:
[extracción y sus límites](https://pypdf.readthedocs.io/en/6.21.4/user/extract-text.html),
[modo estricto](https://pypdf.readthedocs.io/en/6.21.4/user/robustness.html).
La firma/configuración se contrastaron con la distribución instalada; no se pasó
una opción `configuration=` inexistente a `PdfReader` ni se mutaron constantes globales.
