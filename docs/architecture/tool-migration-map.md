# Migración de herramientas y consumidores del engine

Revisión independiente de `map_legacy_tool_consumers`, con contexto limpio y sólo
lectura, sobre a644164. Fecha de incorporación: 2026-11-01. El inventario contiene
**71 herramientas en 11 categorías**; “71 familias” en apuntes anteriores era una
abreviatura incorrecta. El contador y las clases se contrastan con
`legacy-tool-schemas.json` y `backend/tools/__init__.py`. El inventario es un snapshot
del catálogo heredado, no el catálogo MCP productivo ni el estado actual del runtime.

## Frontera observada en a644164 y decisión inicial

La cadena heredada es `get_tools_for_role` → `agents/base.py` → contexto global,
thread-local/ContextVar/env → `engine/loop_tools.py` → `_run`. No se portará esa
herencia como autoridad del nuevo intento. Los productores de claim y DONE de
autonomía/flows deben migrar al mismo dueño durable.

El recorrido nuevo es `RuntimeService` → `AttemptPeers` → `CodexRuntime.open`.
Sus herramientas dinámicas se despachan a `ProjectTools`, que une once schemas de
investigación/preguntas en `BusinessTools` y cuatro de análisis en `AnalysisTools`.
El token permanece en el MCP de negocio, con validación en la API. La inferencia usa
filesystem de lectura y shell/unified_exec deshabilitados. La edición nativa de la
matriz describe un destino; no es una capacidad productiva conectada.

`native_commands.py` y `command_jobs.py` entregan comandos durables, ahora conectados
a la sesión de inferencia para análisis con fuente en lectura. El revisor propuso
una fachada del host ligada al lease/workspace admitidos. Se implementó ese destino:
agregar execute_command al MCP síncrono con token de negocio separaría el proceso del
dueño asíncrono que debe pararlo. Tampoco basta un wrapper de InfinibayBaseTool.

La fachada declara schemas estrictos de start/read/cancel/Python, une
catálogos con detección de nombres duplicados, fija hash/versiones antes de thread
y despacha explícitamente al host o a negocio. El host conserva los context managers
dentro del worker y el modelo no recibe lease, fence, control paths o tokens. Si otro runtime
requiere MCP, será un proxy hacia el host; no otro propietario de procesos.

Antes de habilitar escritura productiva hay que cerrar la propiedad global de
workspace y la política por capacidad/tipo de tarea. Un cwd validado no confina
los archivos que abre un programa. El perfil nativo y sus pruebas de FS/red deben
mantenerse; no montar el repo principal completo para resolver Git de un worktree.

## Destino por categoría

| Categoría | Cantidad | Destino y obligación |
| --- | ---: | --- |
| Archivos | 6 | Ken/lectura confinada; edición por capacidad del host, diff completo y candidato durable |
| Git | 7 | Repo/worktree reales, recibos por operación y publicación sujeta a aceptación del SHA exacto |
| Tareas | 14 | Un claim durable; propuesta/revisión/done separados; comentarios y cambios versionados |
| Comunicación | 6 | Chat explicativo durable, comandos tipados para activar/asignar/corregir/preguntar |
| Web | 7 | Captura existente; PDF de adjunto con páginas/citas implementado parcialmente. Parser local ya tiene límites CPU/AS/plazo y cancelación/cierre. PDF por URL conectado; faltan búsqueda/Spider y consumidores; deep_research sin LLM anidado |
| Shell | 2 | Fachada del host sobre OwnedCommandExecutor; intérprete elegido por host, sin instalación implícita |
| Conocimiento | 12 | Findings/reportes nuevos, búsqueda, revisión científica y wiki con identidad por proyecto/global |
| Proyecto | 8 | Planificación tipada, hipótesis versionadas, referencia y repositorios con reconciliación |
| Datos | 1 | Retirar SQL genérico después de sustituir sus consumidores por consultas/analytics tipadas |
| RAG | 6 | Captura canónica y recuperación PDF/CSV/DOCX/JSON/XML implementadas con límites, estructura y citas. Ken no sustituye esa cobertura; pendiente migrar registries/roles/flows y retirar RAG antiguo |
| Context7 | 2 | Adapter opcional con proveedor, credencial y procedencia declarados |

No retirar una categoría tras migrar su primer nombre. Las clases fuera del registro
también necesitan una decisión por consumidores. No preservar confianza declarada
por el modelo ni similitud de embeddings como validación científica.

## Casos que deben conservar las nuevas interfaces

- Repetir clave e intención recupera el job original; cambiar argumentos produce
  conflicto. Un peer nuevo no convierte un resultado desconocido en ejecución nueva.
- Al perder lease, el modelo pierde incluso lectores. Recuperar recibos del dueño
  no reactiva el token del intento obsoleto.
- Stop/corrección retira autoridad viva antes de DB/RPC y exige cerrar todos los
  peers. Al conectar comandos debe revisarse la premisa actual de service.py de
  que la inferencia de investigación no produce efectos de shell.
- Salida ordenada, límites, hijo desacoplado, código cero, cierre y aceptación son
  hechos distintos. Sin recibo se conservan unknown/NULL y los bytes observados.
- Cuenta/env/perfil inválidos producen error. No hay fallback a subprocess directo,
  API key o cuenta del usuario para el peer de comandos. La inferencia conserva
  exclusivamente la suscripción configurada y Ken obligatorio.

## Entradas que todavía compiten con el dueño nuevo

`flows/research_flow.py`, `investigation_flow.py`, `research_review_flow.py`,
`development_flow.py`, `code_review_flow.py`, `ticket_creation_flow.py` y
`main_project_flow.py` siguen usando el engine. También `helpers/reporting.py`,
`helpers/message_dispatcher.py`, handlers de revisión/misc de autonomía y
`orchestrator.py`. Este último todavía convierte retorno sin excepción en DONE.
`TaskFlowHandler` y `take_task.py` contienen claims distintos. Cada entrada debe
admitir trabajo y consumir estados/eventos del mismo servicio; no crear otro loop.

Secuencia propuesta: comandos y evidencia de candidato; investigación completa y
documentos; coordinación/planificación; desarrollo/revisión/Git/CLI/TUI; retirar
motor y dependencias cuando no queden entradas ni inferencia auxiliar. Hay que
comprobar todos los consumidores, no limitar la eliminación a get_engine().execute.

Hay pruebas del recorrido dinámico llamada → executor → SQLite, pérdida de recibo,
scope/catálogo, reapertura sin replay y FS/red/symlinks reales. Faltan ventanas de output
del propietario, escenarios productivos ampliados de Stop/corrección y migrar todos
los consumidores. Véase [contrato de análisis](host-analysis-tools.md). Los tests con
fake_command_server no demuestran por sí solos el sandbox del CLI. Los fallos
heredados sirven para conservar resultados de producto; no obligan a conservar
CrewAI, whitelist, contexto global, pseudoherramientas o rework ilimitado.

## Wiki con identidad preservada

Los adaptadores Wiki antiguos y cinco operaciones nativas comparten namespace explícito,
página/revisión observadas y recibos. Captura individual/colección reutiliza fuentes y
recuperación local; el catálogo de negocio tiene19 tools. Eso no migra los roles/flows
ni retira SearchWiki y su proveedor legado. Pendientes búsqueda web, revisión científica,
coordinación y demás capacidades antes de cortar las entradas antiguas.
[Contrato, límites y migración33](wiki-knowledge.md).

## Registro de hallazgos y próxima migración

El catálogo actual del host contiene22 herramientas de negocio. Listado, consulta,
resumen estructurado y lectura por ventanas sustituyen esas operaciones en el
recorrido nativo; Hallazgos inspecciona afirmaciones/citas con alcance explícito.
Las flags/métodos/confianza antiguos se atribuyen al registro histórico, sin afirmar
review independiente. El conjunto semántico y cada continuación quedan identificados.

ReadFindingsTool, SearchFindingsTool, SummarizeFindingsTool y SearchKnowledgeTool,
además de los escritores/reviewers antiguos y sus roles/flows, conservan consumidores
y proveedores hasta el corte por capacidades. No se declara eliminado ese RAG. La
revisión necesita admisión real, evidencia/versiones y separación del productor; los
labels del lector no implementan ese protocolo. [Contrato](finding-registry.md).


## Lectores de hallazgos migrados — 2026-11-02

El snapshot original de 71 declaraciones queda como referencia histórica; el archivo
de schemas refleja ahora 72 clases registradas, incluida lectura de feedback. No es
el catálogo MCP nativo ni certifica autoridad segura de los writers antiguos.

Se conectaron read/list/summary/semantic y la rama de hallazgos de búsqueda combinada
al registro canónico; se añadió lectura de decisiones/sujetos y se retiró la selección
del source vectorial mutable. La semántica reutiliza el encoder preparado, rechaza
muestreo y comprueba el corpus al terminar. Un fallo parcial de fuente se conserva.
Los cursores, previews, confianza histórica y vigencia no comprobada son explícitos.

Los catálogos por rol/tipo que dan acceso a claims ofrecen también feedback. El
contexto retenido distingue omitir/retirar y no toma un actor ambiental tras retirar
una herramienta. Sigue siendo contexto del host, no el grant nativo con fence/lease.

Los writers `validate_finding`/`reject_finding`, el MCP/HTTP antiguo y los flows que
interpretan `VALIDATED`/`REJECTED` aún requieren un corte de recorrido completo. No
basta borrar el nombre de una herramienta mientras un flow pueda dar la tarea por
terminada por texto del modelo. La aceptación explícita y la invalidación del
conocimiento dependiente siguen dentro del alcance pendiente.
[Contrato y límites](finding-readers.md).


## Planificación nativa conectada — 2026-11-05

El catálogo del plan usa las capacidades de investigación sin `result_propose` y
agrega dos herramientas del host: contexto original por ventanas y propuesta de
grafo. No son herencia de las herramientas antiguas ni permisos de crear/asignar/
ejecutar tareas. El propietario acepta la propuesta exacta después del cierre;
una transacción crea trabajo pendiente y sus dependencias. Un mensaje no activa
agentes. El inicio web usa ese recorrido; ya no inicializa el equipo ni threads.

El mapa anterior sigue siendo histórico para los demás consumidores. Autonomía,
orchestrator, flows específicos y CLI/TUI aún requieren despacho/control sobre el
dueño nuevo. La existencia del plan no demuestra exclusión física de writers
legacy ni cierre científico/visual. [Contrato](native-project-planning.md).


## Despacho aprobado y handoffs conectados — 2026-11-05

La decisión owner separada del plan usa RuntimeService y entregas persistidas,
con causa/destino/contexto y resultados aceptados originales. Los snapshots de
investigación entran en el input del siguiente agente con fuentes y límites.
Correcciones invalidan el grafo autorizado, incluyendo resultados ya entregados;
Stop pausa antes de retirar intentos. Reinicio no reenvía prompts emitidos.

Esto sustituye el recorrido nuevo de coordinación del grafo, sin migrar todavía
los productores antiguos TakeTask/TaskFlowHandler/orchestrator/AgentLoop/listeners,
flows/CLI/TUI ni todos sus resultados de dominio. No se afirma exclusión global.
El siguiente bloque debe cortar esos consumidores con capacidades reales y
recuperación/reautorización; no más pulido de publicación/planificación.
[Contrato y límites](accepted-plan-execution.md).


## Orchestrator, terminal y notas owner migrados — 2026-11-05

ProjectOrchestrator dejó de importar agentes/get_engine/contexto global. CLI/TUI
usan OwnerClient sobre la misma API owner y conservan solicitudes/versiones en
estado privado; no inicializan otra DB ni modelo ni completan/mezclan por texto.
El proyecto/servidor se eligen explícitamente. El servicio declara identidad física
DB y workspaces; cwd y etiquetas no se tratan como contexto compartido probado.

La ruta owner de notas guarda recibo e historial, sin crear agent_events ni el
bus-event antiguo de activación. El input distingue nota owner sin autoridad de
instrucción. Handoffv2 conserva material original del plan/orígenes/supuestos y el
revisor distingue admisión directa de instrucción coordinada del host.

La prueba de CLI/HTTP/broker/kernel/Git llega a revisión independiente/aceptación
con4turnos controlados originales y sin merge. Esto no retira AgentLoop,
MainProjectFlow/demás flows, claims, herramientas ni listeners globales. Tampoco
completa recuperación/sucesores, reautorización ni paridad terminal avanzada.
[Contrato](terminal-owner-client.md), [migración](../modernization/terminal-owner.md).


## Investigación exploratoria y entradas antiguas — 2026-11-05

El resultado `investigation` ya tiene un recorrido nativo propio: alcance,
recopilación, áreas con evidencias, resumen, límites, revisión documental y
aceptación explícita. Reutiliza reportes y el despacho durable; no agrega un loop.
La herramienta tipada sustituye `report_write` en el catálogo de su autor.

`InvestigationFlow` es ahora una entrada de sólo lectura hacia el propietario.
TaskFlowHandler/TakeTask, handlers de revisión/retrabajo, MainProjectFlow y
scavenger dejan de reclamar o reofrecer investigación exploratoria y tareas con
historial nativo. La indicación incluye proyecto/tarea reales y referencias
originales; procesar el evento no completa la tarea ni autoriza otra ejecución.

Este corte no retira todos los demás tipos de Flow/AgentLoop/listeners ni sus
resultados de dominio. La investigación científica antigua conserva consumidores
hasta migrar sus métodos y evaluaciones. El cierre físico global de writers sigue
pendiente. [Contrato y prueba](native-investigation.md).


## Investigación científica y revisión antiguas retiradas del recorrido — 2026-11-05

ResearchFlow/ResearchReviewFlow ahora devuelven indicaciones owner de sólo lectura.
Sus hipótesis, experimentos, síntesis temática, informes, wiki y revisión se
expresan mediante capacidades nativas existentes. La captura nueva de salida real
de comandos completa el puente de evidencia experimental; no se añadió otro
registro de hipótesis ni otro loop de revisión/síntesis.

`research` y `investigation` son owner-only. Los handlers y claims compartidos,
el despacho de MainProjectFlow y el scavenger conservan trabajo para el propietario;
ni `VALIDATED` ni agotar revisiones lo completan. El esquema53 conserva historia y
bloquea claims/finalización antiguos. Los tests del protocolo retirado se cambiaron
por el contrato público y el recorrido nativo con revisión independiente.

Siguen pendientes AgentLoop/MessageHandler/listeners/FlowManager, los tipos restantes
y la exclusión física global; no se deduce cierre de la ausencia en un registro.
[Contrato y evaluación](native-scientific-research.md).


## Activadores antiguos del proyecto acotados — 2026-11-05

El historial real de admisión nativa ahora excluye el arranque/reanudación de
AgentLoop/FlowManager/listeners, mensajes/salud/progreso, el engine antiguo y la
recuperación del proyecto entero, incluidas tareas sin ejecución propia. El
scavenger no reofrece sus tareas ni elimina worktrees. El evento guardado fija el
contexto; su acuse no completa una tarea ni crea autoridad nativa.

La parada conserva referencias a hilos vivos y callbacks conectados. El despacho
nativo consulta los controladores registrados y conserva la solicitud en espera
si su cierre no se pudo observar. No equivale a exclusión global/atómica entre
procesos ni prueba el cierre de productores desconocidos. Desarrollo/revisión,
adopción explícita de candidatos previos, otros tipos y retirada de dependencias
siguen pendientes. [Contrato, evidencia y límites](native-project-owner-cutover.md).


## Candidatos nativos previos como material nuevo — 2026-11-05

El propietario selecciona un intento y huella; el recibo de admisión conserva diff
binario/entrada/origen completos para el autor nuevo. Los cambios no prestan
permisos, prueba ni aceptación. La cadena con kernel y Git aplica el diff en otra
copia, ejecuta checks nuevos y exige revisión/aceptación nuevas. No se añade loop.
El reloj de inactividad reconoce ahora respuestas de host completadas; no texto de
razonamiento ni decisiones pendientes. Se mantienen los demás límites.

Sigue pendiente importar worktrees antiguos sin candidato nativo, conectar ese
material al dispatcher y retirar DevelopmentFlow/CodeReviewFlow/tipos restantes.
No falsear su procedencia para habilitarlos. [Contrato](native-code-carryover.md).


## Archivos de trabajo anterior como datos elegidos — 2026-11-05

Origen y rutas se seleccionan desde registros propios del proyecto: worktree
antiguo o copia privada sin candidato. Se conservan bytes/modo/enlace/ausencia y
contexto desconocido, sin adoptar metadata Git ni fabricar un autor nativo. El
recibo y la entrada existentes llevan ese material a autor/check/revisor/
aceptación nuevos. `.worktrees` no indexada permanece fuera del clone; namespace
comprometido/indexado y código pendiente no se ocultan. No hay otro loop.

Esto permite avanzar al corte real de DevelopmentFlow/CodeReviewFlow. Su retirada,
otros tipos/auxiliares, dispatcher y exclusión global siguen pendientes; no volver
al pulido del importador. [Contrato y límites](selected-old-file-import.md).


## Corte de ejecución por tarea posterior a 189e2e2

DevelopmentFlow/CodeReviewFlow ahora son entradas compatibles de solo lectura.
Se retiraron sus loops/CI/rework/automerge, el despacho/reset/espera de tareas de
MainProjectFlow y la recuperación/limpieza del scavenger. Las doce categorías
persistidas tienen perfil nativo; review es auditoría documental de solo lectura,
separada de la revisión formal de candidato. Catálogo de planificación, admisión,
inputs, aceptación, reutilización de archivos y controles web comparten el mapa.
Esquema54 bloquea claims/done antiguos antes de admisión; después conserva la
aceptación exacta existente, sin reescribir historia. El handoff no es inferencia,
aceptación, finalización del proyecto ni prueba de cierre físico.

[Contrato y límites](native-task-flow-cutover.md). Productores de proyecto,
AgentLoop/listeners/FlowManager e inferencia auxiliar siguen como capacidad
principal pendiente; la retirada de cuerpos privados inalcanzables de handlers
se hará en ese corte. No volver sobre selectores/snapshots/journals para pulirlos.


## Activación de proyectos y contexto histórico posterior a 3d794f7

Main/Brainstorm/Ticket flows, handlers y dispatcher dejaron de inferir/crear
trabajo automáticamente. FlowManager/AgentLoop/listeners aplican política nativa
también antes de la primera admisión, conservando evidencia real de Stop. Requisitos,
planes e ideas antiguos e inventario de tareas entran al planificador nativo como
fuentes históricas atribuidas y limitadas, sin autoridad de sesión/aprobación.
No hay nueva tabla ni loop. [Contrato](native-project-producer-cutover.md).

El corte no retira aún los proveedores auxiliares en prompts/team,
config/model_capabilities, engine/llm_client y DeepResearch ni todo Git/MCP/instalación
antiguo. Sus consumidores, dependencias y pruebas son el siguiente bloque principal;
cierre integral e informe final de proyecto siguen pendientes, sin equiparar una
etiqueta de estado a aceptación comprobada.


## Inferencia auxiliar posterior a 487cdd2

Retiradas las llamadas directas del cliente/configuración/probes antiguos,
exportación de API keys, síntesis DeepResearch y resumen de conversación. Modelos,
autenticación y capacidad real permanecen en el runtime nativo; lectores históricos
usan texto atribuido y capacidades desconocidas. El catálogo anterior se movió a
`backend.tools._legacy_catalog`, con exports lazy para evitar inicialización de
frameworks/ciclos al importar la API/base. La metadata histórica sigue resolviendo.
[Contrato](native-auxiliary-inference-cutover.md).

No se eliminaron aún las dependencias de esos lectores/constructores ni se probó
instalación nativa limpia. Es el siguiente corte junto con MCP/Git/instalación y
pruebas de comportamiento retirado; no sustituirlo por pulido de hooks.


## Instalación predeterminada posterior a b2ad539

El runtime nativo funciona en una instalación independiente sin CrewAI/crewai-tools/
LiteLLM/Ollama/Chroma/los parsers tree-sitter antiguos. Esos once requisitos son un
extra histórico explícito y no otro backend. API/CLI e investigación/planificación/
desarrollo pasan desde el paquete instalado; ningún import backend proviene del
checkout o venv anterior. [Contrato](native-python-installation.md).

No se borraron todos los consumidores legacy ni se provisionó el host completo.
MCP/Git/agentes/conocimiento/instalador y pruebas antiguas son el siguiente corte,
sin volver a pulir el selector de dependencias o el wrapper de metadata.
