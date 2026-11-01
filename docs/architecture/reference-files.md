# Adjuntos del propietario y previas de texto

`/files` administra archivos de referencia del proyecto visible. `/wiki` conserva
su propósito de documentos de conocimiento. Subir, listar, abrir, previsualizar,
descargar y borrar un adjunto no inicia inferencia ni una tarea.

El catálogo está paginado (50 filas por defecto, máximo 200), con orden estable
por subida e identidad descendentes. La búsqueda de nombre/descripción es literal;
no interpreta `%` o `_` como comodines. Las consultas y cachés del frontend llevan
proyecto e identidad de archivo; un enlace de otro proyecto pide elegirlo antes de
habilitar acciones. Los clientes propietarios antiguos pueden consultar metadatos,
descargar o borrar sin `project_id`; la interfaz nueva siempre lo envía y el servidor
rechaza una discrepancia antes de leer o eliminar bytes. La previa exige proyecto.
Esto es aislamiento entre proyectos dentro de la sesión propietaria local, no un
sistema de cuentas o permisos multiusuario.

La subida exige un proyecto existente. Admite un archivo por operación, hasta
1.000.000 bytes de contenido y 1.016.384 bytes de cuerpo multipart completo, con el
plazo del middleware de entrada. La UI exige confirmar «Subir archivo» después de
elegirlo y no descarta silenciosamente archivos adicionales de un arrastre. El
nombre visible no determina el nombre físico: se crea un archivo privado con UUID,
`O_EXCL`, permisos 0600 y fsync antes de registrar sus metadatos. No hay reintento
automático. Un fallo de commit incierto conserva los bytes y se comunica como fallo;
consultar la lista precede a repetir una subida. No hay reconciliador general de
huérfanos ni transacción atómica entre SQLite y el sistema de archivos.

`ReferenceStorage` comparte recorrido confinado con `BoundedReferenceReader`.
Comprueba raíz/proyecto/uploads y abre cada directorio sin seguir enlaces simbólicos.
Las rutas proceden de metadatos, no de una ruta enviada por el navegador. Los
archivos deben ser regulares; la descarga retiene su descriptor abierto y transmite
la longitud inicial. Los adjuntos históricos mayores de 1 MB siguen descargándose;
la previa rechaza el exceso, sin truncarlo. El navegador prepara la descarga en un
Blob: archivos históricos muy grandes requieren memoria en el cliente. La raíz de
configuración sigue siendo de confianza; no se promete un sandbox general del host.

La previa obtiene texto UTF-8, PDF con texto o [DOCX/CSV/JSON/XML](structured-sources.md) mediante el worker limitado existente. Las fuentes estructuradas explican normalización y alcance; no reproducen el formato original. Guarda
fecha, hashes de texto/bytes y procedencia en la respuesta, sin crear un registro de
`research_sources` ni un permiso de agente. En PDF conserva marcas y offsets de página,
señala páginas sin texto y declara que no hace OCR. No valida conclusiones, tablas,
imágenes ni orden visual. Los PDFs escaneados sin texto, cifrados o inválidos fallan;
el original puede descargarse. La previa es explícita, sin extracción al navegar,
recuperar foco o reconectar. Una nueva extracción fallida identifica como anterior
cualquier previa aún visible.

Un adjunto registrado no prueba que una tarea lo haya leído. Una fuente capturada
es una revisión persistida que una tarea puede citar. Borrar el adjunto elimina su
registro y archivo; conserva fuentes, citas e informes anteriores. Se verifica con
captura, finding, informe y borrado reales sobre datos sintéticos. Un archivo físico
y sus metadatos no comparten transacción: ante fallo de borrado/commit no se promete
restauración automática, y el propietario debe volver a consultar.

El diálogo de borrado identifica nombre/referencia, explica qué se conserva, enfoca
«Conservar adjunto», limita Tab/Shift-Tab y permite Escape antes de confirmar. En móvil
el detalle vuelve a la lista y restaura el foco de selección cuando el registro sigue
visible. Los errores de lista, detalle, extracción, descarga y borrado son distintos;
no se sustituyen por listas vacías ni confirmaciones de éxito.

Verificación: [resultados](../modernization/files-results.json),
[paquete](../modernization/files-packaging.json),
[recorrido visual](../design/audits/2026-11-01-files/report.md).
La migración de consumidores heredados, OCR, otros formatos, aceptación humana,
lector de pantalla y restauración integral mantienen su trabajo pendiente.
