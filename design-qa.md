# QA visual de los pilotos Tareas y Conversación

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
Las demás diez rutas siguen pendientes de rediseño. No se entregan los pilotos
como diseños visualmente verificados.


## Conversación — 2026-11-01

Referencia: [Conversación con evidencia](docs/design/concepts/chat/conversation-with-evidence.png)
y [adaptación móvil](docs/design/concepts/chat/conversation-with-evidence-mobile.png).
Se inspeccionaron directamente las tres alternativas y la adaptación generada.
CUA volvió a informar browser access host unavailable, con inventarios vacíos. No
hay captura del chat anterior ni comparación de la aplicación ejecutada.

Se implementó la selección en el producto existente, con bandeja paginada de
solicitudes, tarea verificada dentro del proyecto, conversación visible y archivo
legible, reutilizando controles de pregunta/solicitud/corrección/recuperación. SSR
y build comprueban sus alcances específicos; no sustituyen la captura requerida
por la skill [image-to-code](/home/andres/.codex/plugins/cache/openai-curated-remote/product-design/0.1.56/skills/image-to-code/SKILL.md):
“Do not substitute HTTP health, build success, preview-service status, or deployment success for browser verification.”

Pendiente: mismas vistas/estados de las referencias, 390×844 y 1440×1024, selección
y vuelta con foco, preguntas de dos tareas y respuestas invertidas, cambio de
proyecto con borrador, errores/paginación/recuperación, textos largos, teclado,
lector de pantalla, zoom 200/400%, controles compartidos y comprensión humana.
No hay un servidor de demo vivo ni una URL declarada lista para inspección.
