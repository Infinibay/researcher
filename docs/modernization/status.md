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
- Desarrollo interno: edición en copia privada, captura del commit/árbol/diff exactos y comprobaciones aisladas con resultados durables. Stop y correcciones conservan evidencia sin aprobar contexto obsoleto. Faltan revisión de código, aceptación, publicación y admisión pública. [Contrato](code-checks.md).

## Verificación actual

El ejecutor añade 22 casos. La suite completa del primer artefacto tuvo 2039 casos: 1933 pasan, 103 fallan y 3 se omiten. Incluye los 100 fallos heredados y tres regresiones nuevas de importación en recuperación. Las tres se corrigieron y verificaron después con 36 pruebas dirigidas y el wheel final. No se repitió la suite completa tras esa corrección: se conserva su resultado original y el cambio de una importación queda verificado por separado. [Resultados y alcance exacto](owned-checks-results.json).

Wheel final del ejecutor: 393 pruebas pasan, sin fallos ni omisiones; 386 módulos proceden exclusivamente del paquete y 676 fuentes Python/SQL coinciden. [Paquete](owned-checks-packaging.json). Las 98 definiciones nuevas/modificadas están documentadas. [Docstrings](owned-checks-docstrings.json). Los 100 fallos heredados siguen abiertos. El ensayo anterior con suscripción y Ken conserva su alcance histórico; este incremento no hizo nuevas llamadas de modelo. [Recibo anterior y límites](native-search-live.json).

Frontend sin cambios: se conserva la validación anterior de 55 pruebas/build y Hallazgos: 18 estados funcionales y 3 anchos, sin nueva aceptación completa. [Recorrido previo](../design/audits/2026-11-01-findings/report.md).

## Pendiente

Completar capacidades retenidas y retirar roles/flows/CrewAI/RAG anteriores; coordinación y comunicación entre agentes; migración de consumidores de búsqueda y revisión científica; revisión/aceptación/publicación del desarrollo y sustitución del CI heredado; evaluación de todos los prompts y comprensión humano–agente; historial largo/presupuestos/operación; migración/restauración y CLI/TUI; seis rutas web y aceptación completa de las doce; auditoría global de docstrings; resolver o reemplazar justificadamente los fallos heredados y revisión independiente final de toda la rama.

No hay un porcentaje global defendible: las pruebas técnicas verifican límites concretos, pero no miden cuánto producto está aceptado. Sigue faltando una parte importante del plan, incluida la experiencia completa de desarrollo y la aceptación de la interfaz.

El modelo se configura actualmente mediante JSON global con reinicio. No hay selector web ni configuración por agente/proyecto implementados. Los checkpoints anteriores y sus límites se conservan en el [registro](progress.md) y sus recibos enlazados; no se reetiquetan como ensayos nuevos.
