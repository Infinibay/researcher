# Estado de la modernización

La implementación del [plan completo](../superpowers/plans/2026-10-31-actualizacion-proyecto.md) sigue en curso. El [tablero](execution-dashboard.md) organiza la siguiente entrega y [coverage.json](coverage.json) conserva requisitos/evidencia. No se ha hecho merge ni despliegue. La rama se subió hasta `0c8b8d9` antes de la pausa; los checkpoints posteriores son locales.

## Resultados disponibles

- **Seis escenarios de evaluación usan instalaciones nativas nuevas:**
  investigación/corrección, Conversación, preguntas, Stop, continuidad y cálculo;
  nueve admisiones por suscripción. Cinco harnesses terminan correctamente. En
  cálculo se conserva el fallo de catálogo del harness y se verifican los
  artefactos y el recibo HTTP originales después de corregirlo, sin otro turno.
  Pasan 38 pruebas dirigidas; 307 archivos productivos coinciden con el paquete
  instalado y 26 definiciones están documentadas. Consumo desconocido en Stop y
  pregunta; todos sus peers y servidores cerrados. Los demás runners y las
  evaluaciones integrales siguen pendientes.
  [Uso](../../evals/runtime/README.md), [evidencia](native-evaluation-runners-results.json).

- **Configuración antigua retirada; runners en migración:** se retiran 75
  opciones y el escritor global sin consumidores, conservando diez ajustes
  activos y los datos históricos. Pasan 195 casos de fuente; dos casos requieren
  assets explícitos. Paquete con 570 archivos coincidentes y 155 casos
  comparables aprobados; dos checks son sólo de checkout. Catálogo MCP de 45
  herramientas y HTTP/WebSocket reales pasan sin modelos. Los otros runners
  siguen pendientes, sin atribuirles sus recibos históricos como aceptación
  actual. [Contrato](../architecture/retained-configuration.md),
  [resultados y límites](configuration-retirement-results.json).

- **Dependencias frontend migradas:** React19.3, Vite8, TypeScript6 y Tailwind4;
  instalación limpia,126contratos y3pruebas DOM pasan, build estricto correcto.
  Resumen/Ejecución pasan15estados controlados de navegador; acceso añade dos
  estados normales sin avisos y un fallo Axe de contraste en colores forzados,
  con foco visible comprobado. Lint conserva12hallazgos previos; audit conserva
  16entradas de tres avisos únicos, sin altos/críticos. No se acepta seguridad,
  todas las páginas ni el despliegue final. [Informe](../architecture/frontend-dependencies.md),
  [resultados](frontend-dependencies-results.json).

- **Contenedor nativo con Ken y reinicio comprobados:** imagen instalada con
  entornos separados y 308 archivos productivos Python/SQL coincidentes. El
  recorrido por HTTP usa la suscripción y Ken, calcula, guarda hallazgo/informe y
  conserva el estado tras reiniciar, cerrando todos sus peers. El controlador
  mantiene el observador de PID del host; los agentes conservan aislamiento
  privado. Alcance Linux/UID1000/Podman rootless; no acepta reboot, re-enrollment
  ni restauración real. [Guía](../architecture/native-container-operation.md),
  [resultados e intentos anteriores](native-container-results.json).

- **Preparación y arranque del host nativo comprobados:** inicialización nueva,
  diagnóstico de recursos y launcher instalado; modelo configurable. Un recorrido
  real por HTTP con la suscripción usa Ken, calcula, guarda hallazgo/informe y
  conserva el estado tras reiniciar, con todos sus peers cerrados. Se corrigió el
  fallo de cierre de descriptores reproducido bajo uvloop, conservando EOF.
  Pasan 23 pruebas de preparación/CLI, 35 de transporte/Git y 55 instaladas; un
  check de `start.sh` es sólo de fuente y pasa allí. 571 archivos coinciden y
  27 definiciones están documentadas. El intento real incierto anterior sigue
  registrado; no fue repetido. Siguen aprovisionamiento portable, admisión desde
  contenedor y restauración real. [Guía](../architecture/native-host-installation.md),
  [resultados](host-installation-results.json).

- **Sandbox y launcher antiguos retirados:** 18 archivos eliminados y una sola fábrica productiva, con perfil `owned-codex-v1` explícito. Se conservan archivos y adjuntos. 164 casos de fuente y 162 del paquete instalado pasan en las selecciones documentadas; dos comprobaciones de manifiestos son sólo de fuente. Wheel limpio: 568 archivos Python/SQL idénticos, sin archivos retirados. 38 funciones de test históricas retiradas, no reparadas; host/admisión integral siguen pendientes. [Migración](../architecture/native-sandbox-retirement.md), [resultados](sandbox-retirement-results.json).

- **Forgejo15.0.11, TLS y restauración ensayados:** manifiesto fijado, puerto local, directorios explícitos y mapeo rootless. Upgrade real9.0.3→15.0.11 con cuenta/token/repositorio/ramas/PR conservados; clone/push TLS y cliente nativo de PR comprobados. Backup restaurado en otra carpeta, copia actualizada conservada. Doctor28checks/exit0 con aviso heredado DD062. No migra la instancia del usuario ni completa el host nativo. [Guía](../architecture/forgejo-upgrade.md), [resultados](forgejo-upgrade-results.json).

- **Imagen instalada de web/API y persistencia comprobadas:** wheel Python3.13 con extensión nativa, web compilada y UID1000; 314 archivos productivos Python/SQL coinciden. 91 pruebas API/configuración y tres de salud pasan. El recorrido real de contenedor conserva proyecto y adjunto tras reiniciar, exige nuevo emparejamiento y observa ambos cierres. Siguen Forgejo, aprovisionamiento/admisión nativa, actualizaciones frontend y aceptación integral. [Contrato](../architecture/container-operation.md), [resultados](operation-image-results.json).

- **Autonomía y plantillas/proveedores históricos retirados:** 54 módulos; parada conservada en el registro de API, con cierre de hilos sin objeto de flow y reporte de timeout real. 169 pruebas de fuente y 169 instaladas pasan; tres fallos de migración coinciden con el recibo anterior. Catálogo nativo intacto, 22 definiciones documentadas; siguen operación, datos/restore, historial/presupuestos y aceptación integral. [Contrato](../architecture/native-autonomy-retirement.md), [resultados](autonomy-retirement-results.json).

- **Flows y helpers antiguos retirados:** 21 módulos; tres operaciones de metadatos separadas; snapshots históricos sin reanudación nativa. 218 pruebas de fuente y 218 instaladas pasan, con tres fallos de fixtures de migración reproducidos en el paquete anterior. Se retiran 68 tests obsoletos sin contarlos como reparaciones. Siguen autonomía/lectores, operación, datos/restore, historial/presupuestos y aceptación integral. [Contrato](../architecture/native-flow-retirement.md), [resultados](flow-retirement-results.json).

- **Doce páginas piloto; 36 conceptos desktop, 12 móviles y doce selecciones comprobadas.** Ejecución incorpora grafo nativo, dependencias, evidencia e intervención con controles originales. Diez capturas controladas, 123 pruebas frontend/build y doce declaraciones JSDoc. Cero páginas con aceptación integral; sigue el engine y la retirada de consumidores antiguos. [Recorrido](../design/audits/2026-11-06-flow/report.md), [auditoría de conceptos](../design/concept-artifact-audit.json).

- Agentes conectado a registros nativos, identidad/intento/modelo/consumo y Stop original.19backend,123frontend/build y8capturas acotadas;6defsPython/10TS-JS documentadas. **Estado acumulado:11pilotos,33/36desktop,11/12mobile,0aceptaciónintegral**. Sigue Ejecución. [Recibo y límites](../design/audits/2026-11-06-agents/report.md).

- Planificación con grupos/hitos, dependencias y propuestas nativas legibles con enlace original de decisión. Tres conceptos y móvil;9capturasconfixtures,123testsfrontend/build,14funcionesdocumentadas.10pilotos,30/36desktop,10/12mobile,0aceptaciónintegral. [Recibo y límites](../design/audits/2026-11-06-planning/report.md).

- Resumen rediseñado con tres conceptos y móvil; preguntas, planes, tareas y contexto original conectados. Cinco capturas con fixtures,123testsfrontend/build,0Axe/JS en región revisada.9pilotos,27/36desktop,9/12mobile,0aceptaciónintegral. [Resultado y límites](../design/audits/2026-11-06-home/report.md).

- Catálogo nativo de promptsv2 y revisión explícita de578candidatos/512archivos; no autoaprobación por familia ni inferencia directa de warmup.12tests acotados y20instaladas pasan. Eficacia de modelos/comprensión humana aún no evaluadas; timeout de checks y fixture de migración siguen abiertos. [Inventario](../prompts/inventory.md), [resultados](prompt-catalog-results.json).

- Configuración web global/proyecto/agente y esfuerzo de razonamiento, con elección congelada por intento y catálogo nativo comprobado antes de enviar.103backend,123frontend/build,11instaladas y4capturas acotadas; cero modelos reales en esta entrega. [Contrato](../architecture/model-configuration.md), [resultados](model-settings-results.json).

- Reserva local cerrada explícitamente sin borrar ni dar Git por completado; nueva adopción independiente y reparación guardada antes de programación recuperables.35pruebas en fuente,122frontend/build y4capturas web; no nueva verificación de wheel/global. [Contrato](../architecture/source-reservation.md), [resultados](source-reservation-results.json).

- Historia original entre navegadores: abrir una preparación sin recrear su POST, conservar otra solicitud local pendiente y rechazar respuestas/controles de otra identidad o intento.121frontend,16pruebas instaladas enfocadas y tres contextos de navegador. [Contrato](../architecture/source-history.md), [resultados](source-history-results.json). Reserva/adopción y restore siguen abiertos.

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

Completar capacidades retenidas y retirar roles/flows/CrewAI/RAG anteriores; coordinación y comunicación entre agentes; consumidores de búsqueda, conocimiento y revisión científica; publicación reconciliable del desarrollo y ampliación de políticas de aceptación y sustitución del CI heredado; evaluación de todos los prompts y comprensión humano–agente; historial largo/presupuestos/operación; migración/restauración y CLI/TUI; cuatro rutas web y aceptación de las doce; auditoría global de docstrings; resolver o reemplazar justificadamente los 100 fallos heredados y revisión independiente final de toda la rama.

Los 43 escenarios amplios continúan abiertos. No hay un porcentaje global defendible: las pruebas verifican límites concretos y no miden producto aceptado. El modelo y esfuerzo se configuran desde la cabecera para global/proyecto/agente; cada intento conserva su elección original y la disponibilidad se comprueba mediante el catálogo nativo. El JSON del host sigue aportando el valor inicial. El [registro](progress.md) conserva checkpoints históricos y sus límites, sin reetiquetarlos como ensayos nuevos.
