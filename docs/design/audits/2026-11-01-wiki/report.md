# Wiki: cuaderno con alcance explícito

Se eligió el cuaderno entre tres imágenes independientes de escritorio y una
adaptación móvil, según la selección delegada por el usuario. El índice persistente
facilita cambiar de documento sin repetir cabeceras ni convertir la lectura en una
tabla. [Conceptos y procedencia](../../concepts/wiki/manifest.json).

El estado anterior tenía cinco infracciones de contraste detectadas en escritorio y
un lector móvil visiblemente recortado, aunque el ancho total no indicaba overflow.
Además, el árbol añadía una barra a rutas que podían estar almacenadas sin ella.
La nueva interfaz respeta la ruta exacta, muestra proyecto/biblioteca global y separa
índice/lector en móvil. Se corrigieron también landmarks anidados y etiquetas del editor.

La [verificación funcional](interaction-evidence.json) pasó 16 estados de escritorio y
móvil sobre API/SQLite reales con datos sintéticos. Incluye conflicto concurrente,
comparación, sobrescritura preparada explícitamente, respuesta perdida tras commit,
reintento sin duplicar revisión, respuesta tardía sin cambiar el documento seleccionado,
borrador recuperado tras cambiar de proyecto y cancelación de cierre de sesión.
También edición global sin cambiar la página local homónima, creación con puntuación
en ruta, HTML literal, borrado con teclado/foco, historia tras borrado y enlace ajeno
bloqueado. No se ejecutaron turnos de modelo.

La [comprobación de lectura](smoke-evidence.json) pasó 1440, 390 y 320 px: lector dentro
del viewport y cero infracciones axe observadas. Los 16 estados funcionales tampoco
registraron infracciones axe ni errores de página. Se inspeccionaron capturas reales,
incluidas lectura de escritorio y global móvil. No demuestra comprensión humana,
compatibilidad exhaustiva con lectores de pantalla ni aceptación de toda la página.

El primer test de recibo tardío consultaba la interfaz antes de terminar la respuesta.
Un probe separado y la espera del cuerpo completo corrigieron el verificador, sin
atribuir ese fallo de sincronización a la aplicación. Las etiquetas se hicieron
explícitas tras observar ambigüedad de localización; no se afirmó haber demostrado
un fallo de comprensión con lector de pantalla.

Pendiente: comprensión con personas, zoom/lector de pantalla, estados integrales de
sesión/conectividad, retención/paginación en carga representativa y aceptación de la
ruta completa. Wiki suma un piloto; siguen 0/12 páginas completamente aceptadas.
