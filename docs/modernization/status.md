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
- Revisión de código: admisión interna de un objeto inmutable, con otro actor/intento/hilo y vista de inspección en lectura. Incluye requisitos y todas las comprobaciones, con resultados pendientes explícitos. La sesión nativa, validación Git antes/después y decisión siguen pendientes. [Contrato y límites](code-reviews.md).

## Verificación actual

La admisión e inspección de revisión pasan 20 casos propios, incluida la prohibición de despachar revisión nativa antes de implementarla. El wheel aislado pasa 199 pruebas de sus consumidores afectados, sin fallos ni omisiones; 350 módulos proceden sólo del paquete y 679 fuentes coinciden. Las 55 definiciones nuevas/modificadas están documentadas. No hubo una nueva suite global ni generación de modelo. [Resultados](code-review-state-results.json), [paquete](code-review-state-packaging.json), [docstrings](code-review-state-docstrings.json).

Como referencia histórica, el ejecutor de comprobaciones tuvo una suite completa de 2039 casos: 1933 pasan, 103 fallan y 3 se omiten. Incluye los 100 fallos heredados y tres regresiones de recuperación corregidas después con 36 pruebas dirigidas y un wheel de 393 casos. Se conserva aquel resultado original, sin atribuirlo a los bytes posteriores. Los 100 fallos heredados siguen abiertos. [Resultados y alcance exacto](owned-checks-results.json), [paquete anterior](owned-checks-packaging.json). Los ensayos anteriores con suscripción y Ken conservan su alcance histórico. [Recibo anterior y límites](native-search-live.json).

Frontend sin cambios: se conserva la validación anterior de 55 pruebas/build y Hallazgos: 18 estados funcionales y 3 anchos, sin nueva aceptación completa. [Recorrido previo](../design/audits/2026-11-01-findings/report.md).

## Pendiente

Completar capacidades retenidas y retirar roles/flows/CrewAI/RAG anteriores; coordinación y comunicación entre agentes; migración de consumidores de búsqueda y revisión científica; revisión/aceptación/publicación del desarrollo y sustitución del CI heredado; evaluación de todos los prompts y comprensión humano–agente; historial largo/presupuestos/operación; migración/restauración y CLI/TUI; seis rutas web y aceptación completa de las doce; auditoría global de docstrings; resolver o reemplazar justificadamente los fallos heredados y revisión independiente final de toda la rama.

No hay un porcentaje global defendible: las pruebas técnicas verifican límites concretos, pero no miden cuánto producto está aceptado. Sigue faltando una parte importante del plan, incluida la experiencia completa de desarrollo y la aceptación de la interfaz.

El modelo se configura actualmente mediante JSON global con reinicio. No hay selector web ni configuración por agente/proyecto implementados. Los checkpoints anteriores y sus límites se conservan en el [registro](progress.md) y sus recibos enlazados; no se reetiquetan como ensayos nuevos.
