# Piloto: Tareas

Fecha: 2026-10-31. Base de implementación: 1daf8f6.

Objetivo: elegir y ejecutar una tarea, comprender una propuesta con su evidencia y sus límites, y corregir el contexto sin perder la trazabilidad. Usuario: propietario que investiga y desarrolla con agentes. Superficie: web de escritorio de 1440 × 1024 y adaptación responsive de 390 × 844.

Evidencia: TasksPage.tsx conserva filtros, creación y dependencias; TaskDetailModal.tsx encierra el trabajo en un modal de 672 px con pestañas; TaskRunWorkspace.tsx ya ofrece solicitudes, correcciones, preguntas, fuentes y recuperación. Las descripciones anteriores proceden del código, no de capturas.

La consulta CUA de esta sesión devolvió apps=[], browsers=[] y “The browser access host is unavailable”. La auditoría visual de la aplicación existente queda pendiente. No hay capturas adjuntas ni contexto visual guardado por Product Design. Se continúa con conceptos de una dirección nueva, autorizada por el rediseño completo, sin presentarlos como evidencia de la interfaz actual. Ruling: posponer captura previa para no bloquear imágenes y código; coste: posibles problemas de densidad o comportamiento requieren corregirse cuando haya navegador.

Alternativas: lista editorial con inspector; tablero operativo; cuaderno de investigación. La selección la realiza el implementador por instrucción explícita del usuario. No se añade aprobación por pantalla.

Datos de concepto: proyecto Atlas y tareas sintéticas, sin datos personales ni acceso a proyectos reales. Hallazgo de reintentos provisional, cita de una prueba, hipótesis sin comprobar y corrección literal del usuario. Los datos del concepto nunca se inyectan en la UI de producción.

Conservar: estados veraces; propuesta distinta de aceptación; solicitudes y reintentos con identidad estable; correcciones que no reinician automáticamente; lectura de fuentes; preguntas; Stop y recuperación sin replay. No incluir métricas inventadas.

Aceptación: guardar tres imágenes independientes, prompts íntegros y procedencia; puntuar y elegir; generar adaptación móvil; implementar composición semántica con datos reales; comprobar estados y comportamiento; comparar capturas y teclado/accesibilidad cuando se disponga de navegador. Imágenes y build no prueban estas últimas comprobaciones.
