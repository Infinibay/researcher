# Estado de la modernización

La implementación del [plan completo](../superpowers/plans/2026-10-31-actualizacion-proyecto.md) sigue en curso. El [tablero](execution-dashboard.md) organiza la siguiente entrega y [coverage.json](coverage.json) conserva requisitos/evidencia. No se ha hecho merge, push ni despliegue.

## Resultados disponibles

- Runtime durable por proyecto/tarea/intento/contexto, controles humanos, recuperación, preguntas y propuestas separadas de aceptación. Codex CLI por suscripción y Ken publicado ensayados; consumidores/loops antiguos y ampliación productiva pendientes.
- Investigación nativa con adjuntos, HTTPS/DOI/arXiv/PDF, CSV/DOCX/JSON/XML, estructura/offsets/citas y recuperación semántica local fijada; hallazgos provisionales e informes draft. Búsqueda web nativa trazable y revisión documental independiente ensayadas. No equivale a validación científica representativa. [Revisión documental](../architecture/finding-reviews.md).
- Wiki local/global con revisiones, recibos, historia y capturas. Migración 33 conserva datos y rechaza downgrade con pérdida. [Contrato](../architecture/wiki-knowledge.md).
- Desarrollo interno con edición privada, captura Git exacta y comprobaciones aisladas durables. Revisión nativa separada con petición/entrada originales, Git antes/después, citas verificadas y confirmación tras cierre. Stop/correcciones conservan evidencia sin aprobar contexto obsoleto. Faltan aceptación, publicación y admisión pública. [Contrato y límites](code-reviews.md).
- Seis pilotos web: Tareas, Conversación, Informes, Archivos, Wiki y Hallazgos; 18/36 conceptos de escritorio y 6/12 móviles, con 0/12 páginas completamente aceptadas. [Inventario](../design/inventory.md).
- Inicialización explícita, autoridad/broker/dominio, acceso y wheel comprobados en los recorridos documentados. Instalación integral y backup/restore pendientes.

## Verificación actual

La revisión nativa pasó seis integraciones con generación controlada y límites físicos/Git/SQLite reales. El primer wheel pasó 336 pruebas sin fallos ni omisiones, con 375 módulos sólo del paquete. La suite global de ese artefacto pasó 1993 casos, falló en los mismos 100 identificadores heredados y omitió tres; no hay identificadores nuevos de fallo, sin afirmar que sus causas sean idénticas.

El ensayo real con suscripción y Ken detectó un fallo que los dobles no ejercitaban: el índice reservado `.ken` impedía confirmar la revisión. La corrección limitada a dos archivos pasó 26 casos de Git/captura y 63 de bootstrap del wheel corregido. El [wheel final corregido](native-code-review-packaging.json) pasó 83 pruebas sin fallos ni omisiones, incluidas las seis integraciones; 339 módulos sólo del paquete y 691 fuentes coincidentes. [Resultados y límites](native-code-review-results.json). No se atribuye la suite global anterior a esos bytes posteriores.

El [ensayo real posterior](native-code-review-live.json) pasó: detectó que la fórmula devolvía 100,2 en vez de 120, registró `needs_revision`, confirmó el protocolo y cerró todos sus procesos. Conserva dos turnos reales de revisor en total, incluido el anterior al ajuste, y el intento inicial del verificador rechazado antes de inferencia. El autor y el fallo son controlados: un caso sencillo no calibra calidad general ni comprensión humana. Las 138 definiciones nuevas/modificadas tienen [docstring](native-code-review-docstrings.json); no es una auditoría documental global.

Frontend sin cambios: se conserva la validación anterior de 55 pruebas/build y Hallazgos con 18 estados funcionales y tres anchos, sin aceptación completa nueva. [Recorrido previo](../design/audits/2026-11-01-findings/report.md).

## Pendiente

Completar capacidades retenidas y retirar roles/flows/CrewAI/RAG anteriores; coordinación y comunicación entre agentes; consumidores de búsqueda, conocimiento y revisión científica; aceptación/publicación/admisión pública del desarrollo y sustitución del CI heredado; evaluación de todos los prompts y comprensión humano–agente; historial largo/presupuestos/operación; migración/restauración y CLI/TUI; seis rutas web y aceptación de las doce; auditoría global de docstrings; resolver o reemplazar justificadamente los 100 fallos heredados y revisión independiente final de toda la rama.

Los 43 escenarios amplios continúan abiertos. No hay un porcentaje global defendible: las pruebas verifican límites concretos y no miden producto aceptado. El modelo se configura mediante JSON global con reinicio; no hay selector web ni configuración por agente/proyecto. El [registro](progress.md) conserva checkpoints históricos y sus límites, sin reetiquetarlos como ensayos nuevos.
