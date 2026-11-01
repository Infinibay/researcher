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

**La configuración interna de pypdf no es un límite duro de CPU/RSS.** El host ya
la ejecuta dentro del worker limitado/cancelable descrito debajo; esto no cierra
por completo `read_paper/pdf_search` ni retira herramientas heredadas. Todavía faltan
adquisición de PDF por URL, OCR si se decide admitirlo,
DOCX y recuperación estructurada CSV/JSON/XML, interfaz Documentos rediseñada,
previsualización de páginas/citas en producto y migración de consumidores antiguos.
El límite de captura no demuestra que el endpoint heredado de upload limite el
cuerpo antes de almacenarlo; ese endpoint sigue pendiente de modernización.

Fuentes primarias consultadas para el contrato de pypdf:
[extracción y sus límites](https://pypdf.readthedocs.io/en/6.21.4/user/extract-text.html),
[modo estricto](https://pypdf.readthedocs.io/en/6.21.4/user/robustness.html).
La firma/configuración se contrastaron con la distribución instalada; no se pasó
una opción `configuration=` inexistente a `PdfReader` ni se mutaron constantes globales.

## Ejecución del parser bajo el host

La adquisición productiva ya llama a `PDFParser`, que envía únicamente el snapshot
binario a un programa fijo en otro proceso. No acepta comandos, rutas de documentos
ni código del modelo. Arranca con Python aislado, sin `site`, entorno mínimo,
`close_fds=True` y sin shell. La dependencia se localiza en la instalación efectiva
de `pypdf`, incluso si el host arrancó con dependencias explícitas y `-I -S`.

Antes de importar el parser o leer el PDF, el worker aplica `RLIMIT_CPU` (señal a2s,
límite duro3s), `RLIMIT_AS`256MiB, core/tamaño de archivo cero,32 descriptores y
límite de creación de procesos. El host impone5s de plazo de pared,1MB de entrada
y2MB de salida acumulada, leyendo/escribiendo ventanas de pipe sin buffer ilimitado.
Estos valores son configuración del host. **AS limita espacio virtual; no es una
cuota cgroup de RSS agregado ni un sandbox general de filesystem/red.** El programa
fijo no ejecuta scripts del PDF ni conversores. No se amplía con ello el catálogo
de comandos que puede ejecutar un agente.

El host fija un pidfd antes de enviar datos y conserva la responsabilidad de matar
y reapear ese hijo. Esta distribución de Python no expone `os.pidfd_open`; se
reutilizan los helpers libc existentes de `peer_process`, sin fallback de parser
en el proceso de la API. Una señal/exit desconocidos no se convierten en éxito.
La procedencia guarda límites observados y `worker_closed=true` después del cierre
comprobado. El proceso también tiene fusible de pared y muerte con el padre Linux.

`LiveGrants.operation` registra el trabajo antes del spawn. Stop/corrección retira
autoridad y señala cancelación sin esperar SQLite; el intercambio comprueba esa
señal cada50ms. El contexto permanece registrado hasta que el hijo se haya reapeado.
El runtime espera esos trabajos antes de finalizar; si el cierre no se confirma,
el intento queda en reconciliación. La recuperación usa los grants de ese intento,
proyecto y tarea, y también espera su cierre. La API hace lo mismo al apagarse.
Una revocación SQL aislada de un grant heredado conserva la validación de commit;
no equivale a la retirada viva de un intento administrado.

Pruebas ejercitan agotamiento real de CPU/AS, proceso dormido, exceso de salida,
secreto/FD heredables, retirada por HTTP, muerte del padre y barreras de cierre en
finalización y recuperación. Los fallos del parser se inyectan después de aplicar
los límites reales; no se afirma aislamiento sólo por leer su configuración.

Esto cierra el paso de límites/cancelación del parser local. Siguen pendientes PDF
por URL, los consumidores heredados, rediseño de Archivos de referencia (`/files`),
previsualización de páginas/citas y comprensión con personas. Documentos (`/wiki`)
es la wiki del producto y requiere su propia identidad/migración y rediseño; no es
la pantalla de uploads. La inscripción global de todos los actores del host y las
cuotas completas por instalación siguen dentro del plan, sin darse por verificadas
a partir de este worker fijo.

Referencias primarias de la semántica de límites:
[resource de Python3.12](https://docs.python.org/3.12/library/resource.html),
[señales y pidfd](https://docs.python.org/3.12/library/signal.html#signal.pidfd_send_signal).
