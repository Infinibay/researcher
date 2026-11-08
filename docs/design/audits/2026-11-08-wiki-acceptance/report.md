# Documentos: cuaderno operativo con alcance visible

Aceptación técnica y visual delegada del recorrido completo; mantiene el
[concepto elegido](../../concepts/wiki/scoped-notebook.png). El índice y el lector
comparten papel, tipografía y acento verde; en móvil quedan en vistas separadas.
La comparación del concepto y las capturas actuales se hizo en la misma revisión.
La selección no representa una prueba con usuarios ni una medición de comprensión.

Se utilizó Chromium mediante el harness del repo contra el backend instalado;
el navegador integrado devolvió que su host no estaba disponible. El conjunto
`initial-current` fue inspeccionado visualmente, con sus estados sintéticos reales.
`canonical-fresh` conserva la ejecución del comando final y la captura final del
lector también inspeccionada. `review` y `reflow` completan observaciones visuales
específicas; sus identidades pertenecen a otra fixture desechable de este mismo
bloque. No se presentan como una única ejecución con IDs compartidos.

1. **Entrada y lectura.** Título, proyecto, ruta y revisión son legibles y el
   documento termina con su alcance. [Lectura actual](canonical-fresh/desktop-current-reading-final.png).
   El contenido del ejemplo es material sintético escrito por el evaluador, no
   una respuesta del agente ni un ejemplo aceptado por la persona usuaria.
2. **Alcance local/global.** Las notas homónimas conservan identidades distintas.
   Elegir global muestra su efecto compartido antes de editar.
   [Lectura global móvil](initial-current/mobile-global-reader.png).
3. **Edición concurrente.** Una escritura real desde otro editor provoca409 y
   conserva el borrador. El propietario consulta la revisión y elige preparar
   su sobrescritura; no hay mezcla automática.
   [Conflicto](initial-current/desktop-conflict.png) y
   [panel de comparación actual completo](review/01-current-comparison-panel.png).
   La captura original `desktop-comparison` sólo muestra el encabezado al final
   del viewport; no se usa como prueba visual del panel completo.
4. **Pérdida de recibo.** Tras un commit real, se pierde sólo la respuesta. El
   borrador permanece y repetir el mismo intento devuelve la única revisión.
   [Estado de respuesta incierta](initial-current/desktop-uncertain-receipt.png).
5. **Nueva selección.** Una respuesta posterior no cambia el documento elegido.
   [Documento posterior](initial-current/desktop-late-response-new-document.png).
   El aviso de un guardado anterior persiste con su título/revisión: DD125 propone
   contextualizarlo o retirarlo al cambiar de selección; no se modifica ahora.
6. **Borradores y sesión.** Cambiar de proyecto conserva el texto y recuperar el
   borrador vuelve al ámbito original. Una revocación real bloquea la vista;
   asociar de nuevo la sesión recupera ese borrador en memoria.
   [Borrador recuperado](initial-current/desktop-recovered-draft.png),
   [sesión bloqueada](initial-current/session-locked-draft-retained.png) y
   [borrador tras renovar sesión](initial-current/mobile-session-restored-draft.png).
   Se comprobó cancelación de recarga. Eso no significa persistencia del texto
   después de cerrar la ventana; la interfaz explica su carácter temporal.
7. **Creación y eliminación.** La puntuación de rutas y el HTML literal no cambian
   alcance ni ejecutan scripts. El diálogo enfoca Conservar, encierra Tab/Shift+Tab
   y Escape devuelve el foco. Borrar conserva la versión histórica.
   [Texto literal](initial-current/mobile-literal-reader.png),
   [diálogo](initial-current/mobile-delete-dialog.png) y
   [lectura de texto retenido](review/02-original-retained-text.png).
8. **Error y recuperación.** Un GET abortado muestra error; volver a consultar
   recupera el mismo documento sin escribirlo.
   [Error](initial-current/mobile-connectivity-error.png) y
   [lectura recuperada](initial-current/mobile-connectivity-recovered.png).
9. **Índice e historia.** Se recorren dos páginas con55documentos y se encuentra
   por búsqueda lexical el último, sin convertir un resultado vacío en prueba
   de ausencia. La historia pagina25revisiones y conserva el texto original.
   [Búsqueda](initial-current/mobile-paginated-search.png),
   [sin resultados](initial-current/mobile-no-search-result.png),
   [historia](initial-current/mobile-paginated-retained-history.png).
10. **Vacío y lectura.** Una biblioteca realmente vacía ofrece crear la primera
    nota;110674bytes permiten llegar al final a320px. A720px el lector usa su
    ancho, sin una columna estrecha artificial.
    [Vacío móvil](review/03-actual-empty-mobile.png),
    [vacío escritorio](review/04-actual-empty-desktop.png),
    [final largo](initial-current/narrow-long-document-tail.png) y
    [lectura720px](reflow/01-reduced-reading-720.png).

Las capturas muestran controles operables y estados claros sobre el estilo
seleccionado. Axe no encontró infracciones en las regiones de Documentos probadas;
la comprobación de sesión bloqueada no incluyó Axe. Teclado/foco, reflujo y lectura
no acreditan accesibilidad exhaustiva en todos los lectores de pantalla/sistemas.

La [exploración CSS200%](initial-current/desktop-css-magnification-200.png) produjo
un lector visualmente inadecuado aunque el control de ancho pasara. Se rechaza
como evidencia de zoom/accesibilidad; no se borra ese resultado. Los atajos no
activaron zoom nativo observado, por lo que no se afirma haberlo comprobado.
DD125 conserva esa verificación manual y los ajustes secundarios; el caso de720px
es distinto. Las capturas programáticas no inspeccionadas se identifican como
tales en [image-review.json](image-review.json).

El comando canónico y la revisión complementaria pasan con **cero inferencias**.
18pruebas backend instaladas y8contratos frontend pasan. Esto cierra una de doce
rutas con el alcance descrito, no U08 ni el plan completo. La contención nativa
sigue abierta. [Resultados](../../../modernization/wiki-page-results.json) y
[revisión de entrega](../../../modernization/wiki-page-review.md).
