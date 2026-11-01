# Informes: estado anterior al rediseño

Fecha:2026-11-01. Base77ca403. Se capturó el API/app real con emparejamiento HTTP
y Chromium156 con sandbox en1440×1024 y390×844. Se usó una copia del ensayo
sintético owned-product-db39481557; no se abrió una base real del usuario ni se
solicitó generación. Scripts y fixture: scratch reports-ui/.

![Escritorio actual](before-desktop.png)

![Móvil actual](before-mobile.png)

1. Abrir el informe guardado desde su URL y proyecto: el contenido existe y se lee
   en escritorio. Su título se repite en el panel y el Markdown.
2. Leer en móvil: lista y documento permanecen en fila; el documento queda recortado.
   No hay vuelta de lista/lector, y scrollWidth global no revela el recorte.
3. Comprobar procedencia: las referencias aparecen en el cuerpo, sin fuentes
   estructuradas ni vínculo desde el informe a la tarea para corregir contexto.
4. Interpretar estado/fecha: draft no explica aceptación; la fecha relativa aparece
   futura. Revisar el tratamiento de la zona antes de atribuir antigüedad.

No se detectaron errores JavaScript en estas dos capturas. Esto no demuestra
accesibilidad, teclado, paginación ni comprensión humana. No se ejecutaron controles
de inicio/Stop, edición, aceptación ni publicación. La implementación seleccionada
y su evaluación posterior están pendientes. [Evidencia](before-evidence.json).
