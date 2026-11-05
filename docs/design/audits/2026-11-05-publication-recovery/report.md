# Recuperación de publicación desde Tareas

Se comprobó el control «Comprobar qué ocurrió» con el frontend compilado y la API,
RuntimeService, propietario/CSRF y SQLite reales. El fixture usa testigos
explícitamente sintéticos de cierre y referencias Git; no ejecuta Git ni modelos.
Una integración nativa separada demuestra el efecto físico y su recuperación.

Cinco capturas inspeccionadas: escritorio de 1440 px, móvil de 390 px, respuesta
perdida, recarga con consulta original y confirmación del mismo recibo. Dos POST
idénticos recuperan una observación guardada y no crean otro intento de observación.
El ejemplo explica que Git pudo crear la rama antes de perder la respuesta.
La acción ofrece consultar evidencia sin repetir la publicación.

Cero errores de página, desbordamientos o incidencias Axe dentro del panel.
Chromium local por indisponibilidad del navegador integrado. No es aceptación
completa de Tareas, evaluación representativa de comprensión ni accesibilidad global.

[Recibo y capturas](evidence.json).
