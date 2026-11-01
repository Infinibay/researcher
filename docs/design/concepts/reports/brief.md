# Informes: lectura, procedencia y corrección

Fecha:2026-11-01. Base:77ca403. Público: propietario del proyecto, que necesita
entender el informe y sus límites, comprobar fuentes y volver a la tarea para
corregir una premisa. La selección visual está delegada por el usuario.

Referencias inspeccionadas: capturas actuales antes-desktop/móvil del audit de
informes y concepto seleccionado editorial-inspector de Tareas. Mantener su papel
cálido, tinta oscura, tipografía editorial, acento verde y listas planas. No
reinicializar el proyecto ni reemplazar el shell existente. Tres imágenes
independientes y adaptación móvil de la elegida antes de implementar.

Problemas observados en las capturas actuales:
- El móvil390×844 recorta el lector; la lista fija288px y el panel siguen en fila.
  El scrollWidth global no lo detecta: un ancestro recorta el contenido.
- Título duplicado (encabezado del panel y Markdown h1), estado draft sin explicación.
- Referencias en el cuerpo, sin recorrido directo a la tarea que debe corregirse.
- Reportes conserva estilos oscuros anteriores, fuera del sistema de los pilotos.
- Fecha relativa aparece futura en la captura; no usar una interpretación ambigua
  de timestamps SQLite sin zona para comunicar antigüedad.

Variantes: lectura con trazabilidad; biblioteca con vista previa; cuaderno de
evidencia. Variar jerarquía/composición, conservando identidad. Viewport1440×1024;
móvil390×844. Fecha exacta2026-11-01. Ejemplos de contenido son ficción de diseño
basada en el ensayo sintético: no se importan como hechos nuevos del producto.

Criterio de selección: claridad de resultado y estado30%, lectura25%, coherencia20%,
accesibilidad prevista15%, adaptación móvil10%. Probar luego datos, estados,
selección/proyecto, enlaces, teclado, responsive y lectura corregible. Los conceptos
no demuestran accesibilidad ni comprensión humana.

Salida: informe persistido visible, fuentes y límites claros, vínculo seguro a la
tarea para corregir contexto sin alterar/aceptar el borrador anterior; carga,
error, vacío y móvil. Inventario y aceptación global de las12páginas permanecen
pendientes. No añadir controles de publicación ni edición no soportados.
