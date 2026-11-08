# Archivos: catálogo e inspector

Se conserva [Archivo con inspector](../../concepts/files/archive-inspector.png)
y su [adaptación móvil](../../concepts/files/archive-inspector-mobile.png): catálogo
e inspector simultáneos en escritorio; en móvil la selección ocupa el lector.
El papel claro, la tipografía editorial, las líneas y el acento verde mantienen
la dirección elegida. Se añade recuperación explícita del intento original, una
necesidad funcional que no aparecía completa en el concepto.

El navegador integrado no estaba disponible; se usa Chromium con el harness del
repositorio y el backend instalado. No se inventan respuestas de negocio. Los
datos y fallos son sintéticos y se identifican como tales.

- **Operación principal.** [Antes](before/01-representative-archive.png), el
  historial desplazaba el catálogo hasta 4858 px. [Después](current/01-representative-archive.png),
  empieza a 649 px y el historial confirmado se abre a demanda. Los pendientes
  siguen expuestos para recuperar sus bytes, sin nueva subida automática.
- **Catálogo.** Se cargan 55 referencias, se recorren dos páginas y se busca por
  nombre/descripción. La revisión complementaria muestra [coincidencia](review/01-current-search-result.png)
  y [búsqueda sin resultado](review/02-current-no-search-result.png) completas.
  Las capturas originales de estos estados no centraban el resultado y no son
  prueba visual suficiente por sí solas.
- **Lectura y descarga.** [Selección móvil](review/03-selected-original-mobile.png)
  y [PDF extraído](review/04-current-pdf-text-mobile.png) separan adjunto, previa y
  fuente capturada. Las marcas de página y de estructura se conservan. El texto
  de prueba es una fixture, no una respuesta generada ni una explicación aceptada
  por el usuario. Se comprueba descarga exacta de los originales.
- **Recuperación.** [Pendiente](observed/15-pending-recovery-visible.png) ofrece
  comprobar ese intento; [original incompleto](observed/16-incomplete-recovery-refused.png)
  explica el rechazo y permite conservar los restos. Los efectos se verifican
  por separado en SQLite y filesystem, no sólo por el mensaje de la interfaz.
- **Borrado y errores.** El [diálogo](observed/17-delete-dialog.png) enfoca Conservar
  y devuelve el foco con Escape. [Borrado fallido](observed/18-delete-failure-keeps-bytes.png)
  conserva el original; el [recibo perdido](observed/19-lost-delete-receipt-history.png)
  se resuelve por su historia. Un error de previa conserva el texto anterior y
  lo identifica como anterior; el error de descarga no se presenta como éxito.
- **Vacío real.** La revisión corregida exige proyecto seleccionado y mensaje
  final: [móvil](review/05-actual-empty-mobile.png),
  [escritorio](review/06-actual-empty-desktop.png). Se llega desde el enlace de un
  adjunto ajeno, por lo que aparece su aviso de alcance. Las dos capturas del
  [primer ensayo](rejected/evidence.json) se rechazan: una estaba cargando y otra
  mostraba el proyecto anterior. La ausencia transitoria de filas no prueba vacío.

Se inspeccionan capturas y se comparan con el concepto; no se declara que toda
imagen programática haya recibido inspección individual. [Registro con hashes](image-review.json).
Axe no encuentra infracciones en las regiones comprobadas; reflujo a 320 px,
teclado y capturas no equivalen a una prueba completa con lector de pantalla o
zoom nativo. La cabecera y el bloque de operaciones aún ocupan demasiado espacio
en móvil; algunos mensajes técnicos necesitan traducción. DD127 los deja para la
pasada final, junto con los detalles ya registrados.

Aceptación técnica y visual delegada de `/files`; cero inferencias. No acepta U08
ni resuelve la contención del engine. [Alcance completo](../../../modernization/files-page-review.md).
