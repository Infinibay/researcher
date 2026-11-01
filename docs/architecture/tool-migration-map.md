# Migración de herramientas y consumidores del engine

Revisión independiente de `map_legacy_tool_consumers`, con contexto limpio y sólo
lectura, sobre a644164. Fecha de incorporación: 2026-11-01. El inventario contiene
**71 herramientas en 11 categorías**; “71 familias” en apuntes anteriores era una
abreviatura incorrecta. El contador y las clases se contrastan con
`legacy-tool-schemas.json` y `backend/tools/__init__.py`. El inventario es un snapshot
del catálogo heredado, no el catálogo MCP productivo ni el estado actual del runtime.

## Frontera actual y decisión

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
| Web | 7 | Captura existente más búsqueda/PDF/Spider explícitos; deep_research sin LLM anidado |
| Shell | 2 | Fachada del host sobre OwnedCommandExecutor; intérprete elegido por host, sin instalación implícita |
| Conocimiento | 12 | Findings/reportes nuevos, búsqueda, revisión científica y wiki con identidad por proyecto/global |
| Proyecto | 8 | Planificación tipada, hipótesis versionadas, referencia y repositorios con reconciliación |
| Datos | 1 | Retirar SQL genérico después de sustituir sus consumidores por consultas/analytics tipadas |
| RAG | 6 | Parsers acotados y recuperación PDF/CSV/DOCX/JSON/XML; Ken no sustituye esa cobertura |
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
