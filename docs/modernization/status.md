# Estado de la modernización

La implementación del [plan completo](../superpowers/plans/2026-10-31-actualizacion-proyecto.md) sigue en curso. El [tablero](execution-dashboard.md) contiene la siguiente entrega; [coverage.json](coverage.json) conserva requisitos y evidencia por escenario. No se ha hecho merge, push ni despliegue.

## Resultados disponibles

- Runtime durable con alcance de proyecto/tarea/intento/contexto, controles humanos, recuperación, preguntas y propuestas separadas de aceptación. Codex CLI por suscripción y Ken publicado se probaron juntos; continúan pendientes consumidores/loops antiguos y ampliación productiva.
- Investigación nativa con adjuntos, HTTPS/DOI/arXiv/PDF, CSV/DOCX/JSON/XML, estructura/offsets/citas y recuperación semántica local fijada. Hallazgos provisionales e informes draft persistidos. No equivale a síntesis científicamente validada.
- Hallazgos con listado/búsqueda/resumen nativos, texto/citas paginados y procedencia histórica explícita. La revisión independiente sigue pendiente. [Contrato](../architecture/finding-registry.md).
- Wiki local/global con identidad, revisiones, recibos, historia y capturas individuales/colección. Migración33 conserva datos y rechaza downgrade con pérdida. [Contrato](../architecture/wiki-knowledge.md).
- Pilotos de Tareas, Conversación, Informes, Archivos, Wiki y Hallazgos.18/36 conceptos de escritorio,6/12 móviles; 0/12 páginas completamente aceptadas. [Inventario](../design/inventory.md).
- Inicialización explícita, autoridad/broker/dominio, control de acceso y comprobaciones de wheel en sus recorridos documentados; instalación integral y backup/restore siguen pendientes.

## Verificación actual

1792 casos: 1689 pasan, 100 fallos heredados y 3 omitidos. No hay fallos nuevos frente a las identidades de la línea base; la suite sigue roja.

Wheel aislado: 371 pasan y 1 fallo heredado explícito; 621 fuentes Python/SQL coinciden.55 pruebas frontend y build. Hallazgos: 18 estados interactivos y lectura a 1440/390/320 px, sin infracciones axe detectadas. Hubo recuperación local real; no turnos de investigación adicionales. [Resultados](findings-results.json), [paquete](findings-packaging.json), [recorrido y límites](../design/audits/2026-11-01-findings/report.md).

## Pendiente

Completar capacidades retenidas y retirar roles/flows/CrewAI/RAG anteriores; coordinación y comunicación entre agentes; búsqueda y revisión científica; desarrollo/candidato/review/Git/CI; evaluación de todos los prompts y comprensión humano–agente; historial largo/presupuestos/operación; migración/restauración y CLI/TUI; seis rutas web y aceptación completa de las doce; auditoría global de docstrings; resolver o reemplazar justificadamente los fallos heredados y revisión independiente final de toda la rama.

El modelo se configura actualmente mediante JSON global con reinicio. No hay selector web ni configuración por agente/proyecto implementados. Los checkpoints anteriores y sus límites se conservan en el [registro](progress.md) y sus recibos enlazados; no se reetiquetan como ensayos nuevos.
