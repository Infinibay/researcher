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

## Entrada MCP posterior a4bcdc92

`researcher-mcp` y los dos nombres de script comparten las definiciones nativas
de investigación y el SDK MCP del runtime, sin FastMCP duplicado. Token y contexto
pertenecen al host/API; SQL de sólo lectura, aprobaciones, PRs y mensajes por rol
del script viejo dejan de ser herramientas de esa entrada. Planificación,
desarrollo, revisión y aceptación/publicación mantienen sus destinos nativos
explícitos. El [contrato y mapa de resultados](native-mcp-entry.md) distingue
esa migración de los consumidores Git/material retenido/arranque aún abiertos.
Ken es el MCP obligatorio separado del host; esta entrada no lo instala ni
declara que está disponible.

## Arranque posterior a4a7d4d6

`start.sh` delega al comando instalado `researcher-start`: API y Vite locales,
con preflight de estado existente y procesos propios. La instalación/bootstrap
queda explícita; no hay proveedor/model pull/Forgejo/contraseña por defecto ni
lectura de `.pids`. Sin configuración nativa se informa modo de inspección, sin
generación. Ken/modelo/suscripción siguen en el host nativo. [Contrato](native-startup.md).
Git/material retenido/publicación, consumidores de agentes/conocimiento y pruebas
antiguas siguen pendientes; no confundir un arranque correcto con su migración.

## Efectos Git antiguos posteriores a05b1628

PR merge/creación de ramas, helpers local/Forgejo y cleanup local/remoto/stale/
periódico rechazan antes de efectos, incluso sin admisión previa/tarea/registro
nativo del repositorio. Historia y ramas se conservan. PR expandido muestra la
procedencia y lleva a Tareas; `owner-entry` correlaciona proyecto/repositorio/rama,
no adivina contexto, archivos disponibles, aceptación ni autoría. La publicación
nativa exacta mantiene su API original. [Contrato](native-git-retirement.md).

La importación exacta de ramas sin copia de archivos, la cadena retenida completa,
selección automática de material para sucesoras y otros consumidores Git de
lectura siguen siendo obligaciones principales. No están resueltas por rechazar
la ruta antigua. Anotaciones de metadata/comentarios no dan autoridad nativa.

## Material exacto de ramas posterior a8e23a5d

La selección de una rama registrada y commit completo ya se transforma en datos
exactos durante la preparación Git propia del intento nuevo, antes de congelar
su entrada. No requiere worktree anterior, otro controller ni nueva tabla;
no cambia la aceptación ni importa la autoridad del PR viejo. Tasks/Conversación
comparten el contrato y la UI distingue selección histórica de bytes capturados.
[Contrato y límites](prior-branch-input.md). La selección de material para
sucesoras del grafo, metadata de ramas no registradas, otros consumidores antiguos
y cierre integral/revisión final siguen dentro del alcance pendiente.


## Material causal de código aceptado — 2026-11-06

El host agrega `researcher_prerequisite_code` sólo cuando existe una dependencia
real de código aceptado. Autor sucesor y revisor del autor exacto leen paquete,
entrada original y diff en ventanas con hash/cobertura, sin permisos de escribir,
aceptar o publicar. `ProjectTools`, lease y validadores existentes son el dueño;
no se crea otro MCP/controller ni se infiere contexto compartido por una etiqueta.
Entregas3 agregan descriptores; las2 ya preparadas conservan su hash. La selección
de resultados excluye revisiones aceptadas que no son el producto del autor.

Prueba instalada:115casos pasan con cuatro inversas antiguas excluidas y listadas;
plan→dos autores/comprobaciones/revisiones/aceptaciones,5turnos controlados y
fuente137conservada.0modelos reales/publicaciones. No demuestra calidad semántica,
restore, suite global ni cierre integral de proyecto; ese cierre/informe es el
siguiente bloque. [Contrato](predecessor-code-material.md),
[resultados](../modernization/predecessor-material-results.json).


## Informe y cierre de proyecto — 2026-11-06

El informe actual se compone de evidencia atribuida con versiones, no del prompt
antiguo que declaraba completo el proyecto antes de revisarlo. El endpoint de
consulta no necesita inferencia; el cierre usa una decisión owner/CSRF exacta con
informe/hash/declaración/reconocimiento de candidatos sin publicar. Reutiliza la
transacción/recibo/evento existente; ninguna tarea, revisión o publicación se
acepta por derivación de contadores. CRUD/helper de status completed rechazan.
La web conserva solicitudes tras perder respuesta y diferencia cierre histórico
de vigencia actual. La API de edición ya usa el schema real de proyectos, que
no tiene updated_at. [Contrato](project-completion.md),
[resultados](../modernization/project-completion-results.json). Historial ampliado,
adopciones, paridad terminal y aceptación global siguen pendientes.

## Proyectos y observaciones originales — 2026-11-06

La ruta Proyectos usa `ProjectWorkspace` para metadata/fuentes/actividad y enlaces
exactos de planes/informes; la etiqueta executing no controla la inferencia de
actividad. Start conserva el paquete original y la fuente. Stop reutiliza la
cancelación transaccional y dueño nativo originales sobre IDs capturados, sin
nuevo loop ni reorientar reenvíos a trabajo posterior. Registrar carpeta existente
no llama `RepositoryManager.init_repo` ni Git/remotos. El borrado sin historia
usa el esquema actual y conserva estadísticas globales. [Contrato](project-workspace.md)
y [evidencia](../modernization/projects-results.json). La integración posterior
de [preparación explícita](source-operations.md) conecta crear/adoptar/clonar y
retira la vieja alta de efectos implícitos. Remoto separado y reparación ampliada
siguen pendientes.

## Explorador de fuentes — 2026-11-06

Repositorios deja de pedir alta mediante un rol retirado y permite registro explícito
de carpeta existente, consulta de revisión completa y origen de PR. Reusa el paquete
de registro de Proyectos. El lector local comprueba raíz exacta para no descubrir
el Git padre, distingue fallo de lista vacía y conserva path/objeto. Lectura no
inicia trabajo ni deriva aceptación de approved. [Contrato](repository-explorer.md),
[resultados](../modernization/repositories-results.json). La sustitución posterior añade operaciones administrativas reales para crear/adoptar/clonar, Stop de fuente/proyecto/lifespan y recuperación readonly de Git terminado antes del registro. El alta antigua ahora rechaza antes de efectos; crear remoto ya tiene una operación separada; reparar etapas incompletas sigue pendiente. No se inventa un intento nativo. [Contrato actual](source-operations.md), [resultados](../modernization/source-setup-results.json).


## Retirada física antes de SQLite — después de c9f8cee

El broker asíncrono expone su retirada inmediata y futuro original. Fuentes captura
su lease/broker real antes de G; Stop valida el fence sin esperar escrituras. El
Stop observado de Proyectos primero recupera recibos o valida una lectura completa,
retira los handles originales y persiste el alcance congelado. Aplicación y Stop
general drenan admisión bajo una barrera; los paquetes antiguos no retiran dueños
nuevos. No cambia el catálogo de modelos ni crea tareas ficticias. [Contrato](source-control.md),
[resultados](../modernization/source-control-results.json).


## Creación remota explícita — después de2687ebc

Fuentes añade una elección separada de servidor/cuenta u organización/visibilidad.
El dueño HTTP administrativo conserva su propio lease y transporte real; no
fabrica una tarea nativa ni reutiliza la creación antigua con fallback. La API
owner y web guardan el servidor elegido; emisión única y marcador original
permiten recuperación readonly tras perder la respuesta. Stop cierra el cliente
antes de SQL y mantiene incertidumbre si el servidor aún puede crear.
[Contrato](remote-source-creation.md), [resultados](../modernization/remote-source-results.json).


## Continuación Git explícita — después de a548554

La reparación se autoriza por operation/fence observado y clave propia. Reutiliza
asignación y broker reales, con programa fijo de hash comprobado; no habilita shell,
reset, clone sobre destino ni force checkout. Una revisión inicial ausente se
publica por compare-and-set; una copia parcial preserva archivos e hidrata faltantes.
Un checkout incompleto no se registra como borrados del usuario por observarlo.
Cierre distingue nunca admitido, previo al dominio y dominio real retirado sin
concesión, conservando evidencia y sin tareas ficticias.
[Contrato](source-repair.md), [resultados](../modernization/source-repair-results.json).


## Historia owner entre navegadores — después de3218eb8

El GET original y el resumen de ProjectWorkspace permiten abrir otra operación sin
recrear una intención. El navegador conserva un localizador de lectura separado
para no reemplazar su packet pendiente. Validación de identidad/elecciones/fence
mínimo y caches por proyecto/operación evitan respuestas cruzadas. La observación
owner comprueba ahora el ID/fence recibido antes de programar; las llamadas
bodyless anteriores siguen compatibles. No se concede autoridad de ejecución
desde un localizador ni se expone creación automática desde la historia.
[Contrato](source-history.md), [resultados](../modernization/source-history-results.json).

## Cierre explícito de reservas locales

El control del propietario `POST source-operations/{key}/release` no es una
herramienta de inferencia. Exige intento/fence/clave originales y cierre real;
conserva archivos e historia y retira la reserva. Una adopción posterior tiene
su propia solicitud. Las autorizaciones viejas no pueden actuar sobre ella.
[Contrato](source-reservation.md),
[resultados](../modernization/source-reservation-results.json).

## Configuración de modelos del propietario

`GET/PUT /api/model-settings` usa sesión/CSRF del propietario y revisión optimista;
no forma parte del catálogo MCP del modelo. Configura futuros intentos, sin dar
herramientas/credenciales/permisos. El runtime conserva una elección por intento y
comprueba `model/list` en su conexión real antes de thread/turn.
[Contrato](model-configuration.md), [resultados](../modernization/model-settings-results.json).

## Motor antiguo eliminado — 2026-11-06

Los doce módulos de `backend.engine` ya no forman parte del código ni del wheel.
Los consumidores de su excepción de Stop pasan a `runtime.legacy_scope`; se
conservan controladores registrados e historia. El reemplazo de inferencia,
herramientas y aceptación es el runtime nativo existente. Se retiran las pruebas
de ese algoritmo sin contarlas como fallos reparados. El catálogo de herramientas
legacy y sus dependencias permanecen como siguiente trabajo principal.
[Contrato y verificación](legacy-engine-removal.md).

## Constructores, catálogo por rol y memoria retirados — 2026-11-06

La retirada del último consumidor productivo permite eliminar el catálogo que
instanciaba herramientas y los constructores/registro de agentes antiguos.
También se retiran KnowledgeService/sources y el puente de eventos CrewAI;
los lectores nativos y la historia almacenada permanecen. Trece módulos,
47 pruebas en fuente y30instaladas; no se cuentan pruebas obsoletas como fallos
reparados. [Contrato y límites](legacy-catalog-removal.md).

Las herramientas individuales antiguas, sus dependencias y los adaptadores
Context7/Spider siguen pendientes. El snapshot de71schemas es histórico y no
requiere importar clases; no representa el catálogo MCP actual ni demuestra
equivalencia de capacidades externas.

## Context7 migrado — 2026-11-06

`researcher_context7_search` y `researcher_context7_docs` sustituyen las dos
herramientas CrewAI y sus tres módulos. Guardan respuestas del proveedor como
fuentes canónicas, con recibo, hash, alcance, versión atribuida y parada del host.
JSON/texto, MCP/HTTP/SQLite y cita probados; configuración opcional y cuota propia.
87 pruebas relacionadas y36instaladas pasan; proveedor simulado, sin petición de
pago ni evaluación de disponibilidad/eficacia externas. [Contrato](context7-sources.md).
Spider y el resto de herramientas/índices/dependencias siguen pendientes.

## Spider migrado — 2026-11-06

researcher_capture_spider conserva scraping de una página con elección explícita
smart/browser/http y markdown/texto. El campo content se captura como fuente;
store_as_finding/topic se reemplazan por lectura y hallazgo con cita verificable.
Clave y límite de créditos del host, transporte compartido con Context7, cierre
físico registrado; costes/renderizado/URL remotos son afirmaciones del proveedor.
Un módulo, tres tests específicos y el extra/SDK retirados; no se cuentan como
fallos históricos reparados. Lock sin cambios de versiones restantes.
122pruebas relacionadas y71instaladas pasan, con proveedor controlado.
[Contrato y límites](spider-sources.md). Siguen las otras herramientas, índices,
dependencias legacy y aceptación global; los detallesDD048 esperan al final.

## Corte actual: operaciones de código consolidadas (6 de noviembre)

Ken y comandos poseídos sustituyen el índice duplicado y los wrappers de archivo/
edición estructural. Se retiran 44 módulos, seis requisitos tree-sitter y 17 tests
de wrappers; los datos ci_* permanecen. El ensayo de efectos y sus límites están
en [native-code-operations.md](native-code-operations.md). Restan otras herramientas
y cinco dependencias del extra legacy; no se declara cerrada toda la migración.

## Corte actual: ejecución y documentos (6 de noviembre)

Se retiran23módulos de wrappers shell/Git/RAG/SQL y documentación CrewAI, junto
con46funciones de prueba específicas. Los reemplazos y cambios de contrato están
en [native-adapter-retirement.md](native-adapter-retirement.md). Permanecen las
políticas web robots/frecuencia, las otras familias y las cinco bibliotecas legacy.
El fallo de versión54/55 del test de publicación se conserva para migraciones.
