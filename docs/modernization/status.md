# Estado de la modernización

La implementación del [plan completo](../superpowers/plans/2026-10-31-actualizacion-proyecto.md) sigue en curso. El [tablero](execution-dashboard.md) contiene la siguiente entrega; [coverage.json](coverage.json) conserva requisitos y evidencia por escenario. No se ha hecho merge, push ni despliegue.

## Resultados disponibles

- Runtime durable con alcance de proyecto/tarea/intento/contexto, controles humanos, recuperación, preguntas y propuestas separadas de aceptación. Codex CLI por suscripción y Ken publicado se probaron juntos; continúan pendientes consumidores/loops antiguos y ampliación productiva.
- Investigación nativa con adjuntos, HTTPS/DOI/arXiv/PDF, CSV/DOCX/JSON/XML, estructura/offsets/citas y recuperación semántica local fijada. Hallazgos provisionales e informes draft persistidos. No equivale a síntesis científicamente validada.
- Búsqueda web nativa configurada y trazable por suscripción: URL observada → captura → hallazgo provisional → borrador. [Contrato](../architecture/native-web-search.md).
- Hallazgos con listado/búsqueda/resumen nativos, texto/citas paginados y procedencia histórica explícita. La revisión independiente sigue pendiente. [Contrato](../architecture/finding-registry.md).
- Wiki local/global con identidad, revisiones, recibos, historia y capturas individuales/colección. Migración 33 conserva datos y rechaza downgrade con pérdida. [Contrato](../architecture/wiki-knowledge.md).
- Pilotos de Tareas, Conversación, Informes, Archivos, Wiki y Hallazgos. 18/36 conceptos de escritorio, 6/12 móviles; 0/12 páginas completamente aceptadas. [Inventario](../design/inventory.md).
- Inicialización explícita, autoridad/broker/dominio, control de acceso y comprobaciones de wheel en sus recorridos documentados; instalación integral y backup/restore siguen pendientes.

## Verificación actual

1805 casos: 1702 pasan, 100 fallos heredados y 3 omitidos. Ningún fallo nuevo respecto de las identidades de la línea base; la suite sigue roja. [Resultados](web-search-results.json).

Wheel aislado: 452 pasan y 1 fallo heredado explícito; 623 fuentes Python/SQL coinciden. [Paquete](web-search-packaging.json). Un turno real con suscripción y Ken verificó búsqueda/captura/cita/borrador y cierre. Consumo nativo acumulado informado: 257498; no es una estimación de facturación. [Recibo y límites](native-search-live.json).

Frontend sin cambios: se conserva la validación anterior de 55 pruebas/build y Hallazgos: 18 estados funcionales y 3 anchos, sin nueva aceptación completa. [Recorrido previo](../design/audits/2026-11-01-findings/report.md).

## Pendiente

Completar capacidades retenidas y retirar roles/flows/CrewAI/RAG anteriores; coordinación y comunicación entre agentes; migración de consumidores de búsqueda y revisión científica; desarrollo/candidato/review/Git/CI; evaluación de todos los prompts y comprensión humano–agente; historial largo/presupuestos/operación; migración/restauración y CLI/TUI; seis rutas web y aceptación completa de las doce; auditoría global de docstrings; resolver o reemplazar justificadamente los fallos heredados y revisión independiente final de toda la rama.

El modelo se configura actualmente mediante JSON global con reinicio. No hay selector web ni configuración por agente/proyecto implementados. Los checkpoints anteriores y sus límites se conservan en el [registro](progress.md) y sus recibos enlazados; no se reetiquetan como ensayos nuevos.
