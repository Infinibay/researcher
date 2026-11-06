# Estado de la modernización

La implementación del [plan completo](../superpowers/plans/2026-10-31-actualizacion-proyecto.md) sigue en curso. El [tablero](execution-dashboard.md) organiza la siguiente entrega y [coverage.json](coverage.json) conserva requisitos/evidencia. No se ha hecho merge ni despliegue. La rama se subió hasta `0c8b8d9` antes de la pausa; los checkpoints posteriores son locales.

## Resultados disponibles

- Reparación explícita de preparaciones Git interrumpidas: conserva archivos, índice/config/HEAD existentes; puede completar primera revisión o archivos faltantes. Incluye cancelación antes de dueño/dominio y testigo de dominio retirado sin concesión. Observar ya no da por listo un checkout parcial.186pruebas instaladas,117frontend y5capturas. [Contrato](../architecture/source-repair.md), [resultados](source-repair-results.json). Historia entre navegadores y aceptación integral siguen abiertas.

- Creación explícita de remoto vacío: servidor, cuenta/organización y visibilidad elegidos; un único POST y recuperación readonly de respuesta perdida. Stop conserva incertidumbre remota.175pruebas instaladas,116frontend,5capturas;49definiciones Python documentadas. [Contrato](../architecture/remote-source-creation.md), [resultados](remote-source-results.json).

- Stop de fuentes retira el dueño físico antes de esperar SQLite, también desde proyecto observado/general y cierre. El reintento de un recibo antiguo no retira un dueño nuevo.164pruebas instaladas y45definiciones Python documentadas; evaluación global aún pendiente. [Contrato](../architecture/source-control.md), [resultados](source-control-results.json).

- Preparación de fuentes con operación administrativa propia: crear Git local, adoptar y clonar HTTPS; controles de fuente/proyecto/cierre y observación de sólo lectura después de perder el registro. La vía antigua de alta/remoto/origin/force push se rechaza. Crear remoto y continuar etapas incompletas tienen operaciones separadas; la aceptación integral sigue abierta. [Contrato](../architecture/source-operations.md), [resultados](source-setup-results.json).

- Runtime durable por proyecto/tarea/intento/contexto, controles humanos, recuperación, preguntas y propuestas separadas de aceptación. Codex CLI por suscripción y Ken publicado ensayados; consumidores/loops antiguos y ampliación productiva pendientes.
- Investigación nativa con adjuntos, HTTPS/DOI/arXiv/PDF, CSV/DOCX/JSON/XML, estructura/offsets/citas y recuperación semántica local fijada; hallazgos provisionales e informes draft. Búsqueda web nativa trazable y revisión documental independiente ensayadas. No equivale a validación científica representativa. [Revisión documental](../architecture/finding-reviews.md).
- Wiki local/global con revisiones, recibos, historia y capturas. Migración 33 conserva datos y rechaza downgrade con pérdida. [Contrato](../architecture/wiki-knowledge.md).
- Desarrollo desde Tareas/Conversación con edición privada, captura Git exacta y comprobaciones configuradas por el host. Revisión independiente solicitada desde Tareas; aceptación explícita del propietario. Stop/correcciones conservan evidencia sin aprobar contexto obsoleto. Publicación en rama local conectada; recuperación local de sólo lectura conectada; transporte remoto configurable conectado; recuperación remota de sólo lectura y controles de Tareas conectados. [Entrada pública y límites](public-development.md).
- Ocho pilotos web: Tareas, Conversación, Informes, Archivos, Wiki, Hallazgos, Proyectos y Repositorios; 24/36 conceptos de escritorio y 8/12 móviles, con 0/12 páginas completamente aceptadas. [Inventario](../design/inventory.md).
- Inicialización explícita, autoridad/broker/dominio, acceso y wheel comprobados en los recorridos documentados. Instalación integral y backup/restore pendientes.

## Verificación actual

Orchestrator/CLI/TUI ya usan la API owner común, con recibos privados y decisiones
explícitas. Las notas no activan agentes. Handoff y revisión conservan la procedencia
del plan. El recorrido de terminal/HTTP/broker/kernel/Git con generación controlada
llega a aceptación con4turnos originales y fuente intacta. TUI real y86frontend
pasan;96wheel seleccionadas pasan con3inversas conocidas excluidas. La selección
amplia de fuente mantiene2fallos de inversa; no hay suite global actual verde.
[Contrato](../architecture/terminal-owner-client.md), [guía](terminal-owner.md),
[resultados](terminal-owner-results.json).

Etapa anterior de planificación y despacho:

La planificación y el despacho aprobado del grafo usan ahora el mismo runtime.
La entrega al siguiente agente conserva resultados aceptados, fuentes y límites;
Stop/reinicio/correcciones conservan la identidad original.8casos nuevos,86frontend,
100del wheel aislado y8estados browser pasan en los alcances registrados. El
recorrido físico usa generación/Ken controlados. Sigue fallando la inversa42 frente
a esquemas posteriores y falta el cutover legacy; no hay suite global actual verde.
[Contrato](../architecture/accepted-plan-execution.md), [resultados](plan-execution-results.json).

Etapa anterior de planificación: La entrada de proyecto ya inicia planificación nativa y la revisión del plan aparece
en Tareas. Propuesta y aceptación son operaciones distintas; aceptar crea un grafo
pendiente y no ejecuta agentes. Premisas cambiadas invalidan la autoridad del plan
y sus hijos. Pasan94 backend,100 del wheel,83 frontend/build y nueve estados del
browser. La integración de kernel/broker/SQLite usa generación y Ken controlados;
no prueba calidad de un modelo real. [Contrato](../architecture/native-project-planning.md),
[resultados](native-planning-results.json), [auditoría](../design/audits/2026-11-05-native-planning/report.md).
Faltan despacho aprobado, handoffs tipados y retirada del resto del engine legacy.


El propietario reactivó el objetivo el 2026-11-05. La suite global del checkpoint
`0c8b8d9` terminó: 2148 casos, 2045 pasan, 100 fallan y tres se omiten;
965 casos del runtime pasan. Mismos identificadores de fallo heredados, sin afirmar
causas idénticas. [Recibo](resumed-baseline-results.json).

Tareas conecta ahora consulta del destino registrado, push, PR, merge separado y
recuperación remota de sólo lectura. La UI conserva los cuerpos originales antes
de enviar y comprueba sus recibos tras respuesta perdida/recarga; no pide IDs
internos o credenciales. Pasan92 backend,92 del wheel,80 frontend/build y nueve
estados de navegador escritorio/móvil sin errores/desbordamiento/Axe en el panel.
Los testigos remotos/físicos del navegador son sintéticos explícitos; la integración
TLS anterior prueba transporte real por separado.23 definiciones Python y31
TypeScript documentadas. [Contrato](../architecture/remote-tasks.md),
[resultados](remote-tasks-results.json), [auditoría](../design/audits/2026-11-05-remote-publications/report.md).

La [recuperación del esquema46](../architecture/remote-recovery.md) prueba cierre
original HTTP/dominio Git antes del observador nuevo, incluso tras corrección o
sin candidato. La ausencia remota sigue incierta. La adopción tras retirada,
etapas no emitidas de merge parcial, compatibilidad real y cutover legacy
permanecen en alcance. Siguiente bloque grande: coordinación y consumidores del
engine, sin otra pasada de detalles de publicación ahora.

El [transporte propio](../architecture/remote-runtime.md) usa configuración opcional
de HTTPS/PAT del host, Git exacto por broker/dominio y HTTP acotado. Sin
configuración se rechaza admisión. Git confiable comparte red del host, restringido
por programa/argv/configuración, sin ACL de destinos del kernel. Sus82 casos y la
integración TLS anterior son [evidencia histórica](remote-transport-results.json).

La publicación local conecta aceptación, admisión durable, nuevo host sin
inferencia, broker/capsule y Tareas. La recuperación ahora prueba cierre original
y usa un intento nuevo con acceso de lectura a rama/recibo; conserva historia tras
corrección y distingue efecto aplicado, no aplicado e incierto.

Pasan 42 pruebas dirigidas y dos integraciones físicas con Git/kernel/SQLite
reales en 128.69 s, con generación controlada. Frontend: 77 pruebas y build; cinco
capturas y recuperación del mismo comando después de perder la respuesta y
recargar. 47 definiciones/módulos documentados en inglés. El wheel tiene
verificación separada, sin atribuirle una instalación integral del host.

No se afirma suite global verde: el baseline es anterior y siguen pendientes
inversas43/44 y adaptación de fixtures de esquemas previos. Compatibilidad remota,
exclusión física legacy y ampliación de carreras/crashes continúan pendientes.
[Contrato](../architecture/code-publication.md), [resultados](publication-recovery-results.json),
[paquete](publication-recovery-packaging.json),
[auditoría UI](../design/audits/2026-11-05-publication-recovery/report.md).

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
