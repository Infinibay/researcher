# QA visual del piloto Tareas

final result: blocked

La consulta CUA de esta sesión devolvió `apps=[]`, `browsers=[]` y
`The browser access host is unavailable`. No se han capturado ni comparado la
aplicación anterior ni el piloto ejecutado. No se sustituyó el navegador por
Playwright ni se tocó una base de datos del usuario para producir capturas.

La referencia elegida es [Lista editorial con inspector](docs/design/concepts/tasks/editorial-inspector.png),
con [adaptación móvil](docs/design/concepts/tasks/editorial-inspector-mobile.png).
La [selección](docs/design/selection.md) describe los ajustes de fidelidad que
exigen los contratos del producto. Las pruebas de HTML en servidor y el build
registrados en el manifiesto sólo acreditan sus alcances respectivos.

Pendiente: capturas comparables de escritorio y móvil; selección de tarea y
regreso con foco correcto; menú y selector de proyecto con teclado; solicitud,
respuesta, corrección, error y recuperación reales; diálogos; texto largo;
zoom 200/400%; lector de pantalla; contraste completo y comprensión humana.
Las demás once rutas siguen pendientes de rediseño. No se entrega el piloto
como diseño visualmente verificado.
