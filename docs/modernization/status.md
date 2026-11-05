# Estado de la modernización

La implementación del [plan completo](../superpowers/plans/2026-10-31-actualizacion-proyecto.md) sigue en curso. El [tablero](execution-dashboard.md) organiza la siguiente entrega y [coverage.json](coverage.json) conserva requisitos/evidencia. No se ha hecho merge, push ni despliegue.

## Resultados disponibles

- Runtime durable por proyecto/tarea/intento/contexto, controles humanos, recuperación, preguntas y propuestas separadas de aceptación. Codex CLI por suscripción y Ken publicado ensayados; consumidores/loops antiguos y ampliación productiva pendientes.
- Investigación nativa con adjuntos, HTTPS/DOI/arXiv/PDF, CSV/DOCX/JSON/XML, estructura/offsets/citas y recuperación semántica local fijada; hallazgos provisionales e informes draft. Búsqueda web nativa trazable y revisión documental independiente ensayadas. No equivale a validación científica representativa. [Revisión documental](../architecture/finding-reviews.md).
- Wiki local/global con revisiones, recibos, historia y capturas. Migración 33 conserva datos y rechaza downgrade con pérdida. [Contrato](../architecture/wiki-knowledge.md).
- Desarrollo desde Tareas/Conversación con edición privada, captura Git exacta y comprobaciones configuradas por el host. Revisión independiente solicitada desde Tareas; aceptación explícita del propietario. Stop/correcciones conservan evidencia sin aprobar contexto obsoleto. Falta publicación reconciliable. [Entrada pública y límites](public-development.md).
- Seis pilotos web: Tareas, Conversación, Informes, Archivos, Wiki y Hallazgos; 18/36 conceptos de escritorio y 6/12 móviles, con 0/12 páginas completamente aceptadas. [Inventario](../design/inventory.md).
- Inicialización explícita, autoridad/broker/dominio, acceso y wheel comprobados en los recorridos documentados. Instalación integral y backup/restore pendientes.

## Verificación actual

El propietario reactivó el objetivo el 2026-11-05. La suite global del checkpoint
`0c8b8d9` terminó: 2148 casos, 2045 pasan, 100 fallan y tres se omiten;
965 casos del runtime pasan. Mismos identificadores de fallo heredados, sin afirmar
causas idénticas. [Recibo](resumed-baseline-results.json).

La política interna de publicación Git posterior pasa 38 casos dirigidos y 38 del
wheel: candidato exacto, rama/recibo atómicos, respuesta perdida, destino movido,
checkouts y metadatos originales. 39 definiciones documentadas; 701 fuentes del
paquete coinciden. Sigue pendiente su admisión durable, nuevo dominio del host,
API/Tareas y push/PR/merge. No se habilitó publicación del producto ni se atribuye
la suite anterior a este módulo nuevo. [Contrato y siguiente integración](../architecture/code-publication.md),
[resultados](publication-policy-results.json).

La entrega de entrada pública pasa diez pruebas dirigidas, incluido un recorrido
HTTP hasta aceptación con Git/kernel/SQLite reales y generación controlada; 51
pruebas de consumidores también pasan. Frontend: 75 pruebas y build, seis capturas
en tres anchos y recuperación de la misma revisión después de perder la respuesta.
El fixture del navegador retiene al revisor en cola y usa testigos físicos
sintéticos; no sustituye la integración nativa. Las 22 definiciones Python
nuevas/modificadas tienen docstrings. Wheel ampliado: 84 casos pasan; el final
añade sólo un docstring y pasa 11 casos, con equivalencia de AST sin docstrings
verificada y 698 fuentes coincidentes. La suite global interrumpida entonces
conserva su recibo; la ejecución completada al retomar se describe arriba.
[Alcance](public-development.md).

El bloqueo adicional del merge antiguo pasa 35 pruebas dirigidas: rechaza tareas
nativas y alias del mismo origen antes del efecto Git/Forgejo. No resuelve aún
la carrera con una primera admisión simultánea ni implementa el publicador nuevo.
[Evidencia y límites](legacy-publication-results.json). El objetivo está activo
después de la reanudación explícita; el plan completo sigue pendiente.

La siguiente evidencia global corresponde a la entrega anterior:

La [aceptación de código](code-acceptance.md) pasó primero 217 pruebas del wheel
ampliado. La suite global de ese artefacto, anterior al ajuste final del historial, tuvo 2126
casos: 2023 pasan, 100 fallan y tres se omiten; 943 casos del runtime pasan. No hubo
identificadores nuevos de fallo frente a los 100 heredados, sin afirmar causas
idénticas. [Resultados](code-acceptance-results.json),
[paquete](code-acceptance-packaging.json),
[66 definiciones documentadas](code-acceptance-docstrings.json).

El ajuste final impide ocultar una objeción anterior con otra revisión favorable:
30 pruebas dirigidas pasan. El wheel final pasa 97 casos tras 56 de bootstrap;
343 módulos sólo del paquete y 696 fuentes coincidentes. Ese conjunto incluye
los consumidores afectados y dos recorridos nativos del coordinador; no es una
segunda suite global.

El coordinador pasó dos recorridos con Git/broker/cierre reales y generación
controlada: aceptación explícita tras revisión confirmada y rechazo del candidato
alterado. El frontend pasa 72 pruebas y build; once capturas en tres anchos
verifican límites, pérdida de envío/respuesta y recuperación exacta después de
recargar. La inspección visual encontró y corrigió valores pendientes mostrados
vacíos y conserva visibles los desacuerdos anteriores. [Auditoría y límites](../design/audits/2026-11-02-code-acceptance/report.md).
No acredita accesibilidad global ni comprensión real del usuario; siguen 0/12
páginas completamente aceptadas. No hubo inferencia nueva en esta entrega.

La revisión nativa anterior conserva su [ensayo real de suscripción/Ken](native-code-review-live.json):
detectó 100,2 frente a 120, registró needs_revision, confirmó el protocolo y cerró
sus procesos. Autor/fallo controlados; no es calibración de calidad general. Su
corrección previa del índice reservado .ken y sus recibos permanecen históricos,
sin reetiquetarlos como ensayos nuevos.

## Pendiente

Completar capacidades retenidas y retirar roles/flows/CrewAI/RAG anteriores; coordinación y comunicación entre agentes; consumidores de búsqueda, conocimiento y revisión científica; publicación reconciliable del desarrollo y ampliación de políticas de aceptación y sustitución del CI heredado; evaluación de todos los prompts y comprensión humano–agente; historial largo/presupuestos/operación; migración/restauración y CLI/TUI; seis rutas web y aceptación de las doce; auditoría global de docstrings; resolver o reemplazar justificadamente los 100 fallos heredados y revisión independiente final de toda la rama.

Los 43 escenarios amplios continúan abiertos. No hay un porcentaje global defendible: las pruebas verifican límites concretos y no miden producto aceptado. El modelo se configura mediante JSON global con reinicio; no hay selector web ni configuración por agente/proyecto. El [registro](progress.md) conserva checkpoints históricos y sus límites, sin reetiquetarlos como ensayos nuevos.
