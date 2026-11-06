# Corte de activación antigua de proyectos

Las entradas antiguas de proyecto ya no arrancan agentes, listeners o loops,
incluso antes de la primera admisión nativa. `MainProjectFlow`, `BrainstormingFlow`
y `TicketCreationFlow` conservan estados históricos legibles y devuelven la
entrada del propietario para el proyecto real. Un plan recibido por el llamador,
una etiqueta de aprobación o un snapshot no son autorización para reproducir
sesiones, crear tareas o completar el proyecto.

## Funciones y resultados

| Función anterior | Tratamiento actual |
| --- | --- |
| Requisitos, plan y opciones de brainstorming | Material histórico atribuido en la captura original del planificador nativo. El propietario puede corregir la solicitud; la propuesta explica opciones útiles y supuestos. |
| Crear tickets/epics automáticamente desde texto | Propuesta tipada nativa y aceptación explícita de su grafo. Una propuesta no ejecuta sus tareas. |
| Preparación automática de repositorio | Se retira del inicio del proyecto. Se conserva la API explícita de repositorios y el registro/selección del origen nativo; el texto de un plan no crea repositorios ni publica. |
| Mensajes, estancamiento, revisión y rework activan modelos | Handlers y dispatcher devuelven referencias al propietario; se conservan mensajes, feedback y estados. Preguntas/correcciones nuevas usan el protocolo humano nativo. |
| Autorondas con CrewAI y reintentos del helper | Flows y cuerpos de handlers retirados; helpers de Crew/agent task rechazan antes de contexto, tracking o proveedor. |
| “Todas las tareas done” genera informe y completa proyecto | Se retira esa conclusión automática. Informes y aceptación por tarea usan los recorridos nativos; la edición de estado del proyecto por el propietario sigue siendo una etiqueta, no prueba de aceptación integral. Cierre integral del proyecto e informe final siguen como capacidad pendiente explícita. |

## Contexto histórico sin autoridad heredada

`ProjectPlans.capture` usa la transacción de admisión y la tabla existente de
solicitudes de planificación. Añade `project_history`, fuentes originales y sus
orígenes; no hay otra tabla, loop o journal.

- Del snapshot real del proyecto toma `requirements`, `plan`, `ideas`,
  `consolidated_ideas` y `selected_ideas` si son legibles. Conserva ID, tipo de flow,
  paso, fecha observada y hash del JSON leído. No suministra IDs de sesión/hilo,
  estados de herramientas o flags de aprobación como autoridad nativa.
- Cada fuente histórica tiene una clave `legacy_snapshot:<id>:<campo>` y origen
  `legacy_snapshot`. Una cita exacta demuestra el contenido capturado, no que el
  usuario lo haya dicho, aprobado o comprendido.
- El inventario contiene IDs, tipos, títulos y etiquetas de estado de tareas del
  mismo proyecto, excluyendo la tarea de planificación. Sus etiquetas no prueban
  aceptación nativa. Permite comparar trabajo existente antes de proponer tareas
  nuevas; no adopta ni vuelve a ejecutar trabajo antiguo.
- Captura hasta 256 tareas, 128000 bytes por snapshot/inventario y 64000 por campo
  histórico. `total`, `captured`, `complete` y `limits` hacen explícito lo no leído.
  JSON inválido, texto UTF-8 ilegible o exceso de tamaño permanecen en la base;
  no se sustituyen por ausencia ni se truncan silenciosamente. Se mantienen los
  campos pequeños legibles cuando el resto del snapshot cabe en el límite.
- El material se lee mediante las ventanas existentes de `researcher_plan_context`.
  Cambiar o borrar después el snapshot/inventario no modifica el original de esa
  solicitud. Un reintento conserva el recibo; la captura es evidencia histórica,
  no una afirmación de que todo el proyecto siga idéntico al aceptarla.

## Política, evidencia y trabajadores existentes

`native_project_handoff` conserva su significado: evidencia de admisión realmente
registrada, o ausencia de ella. `legacy_project_handoff` aplica la política nativa
a todo proyecto existente y devuelve `native_admission_run_id: null` si todavía no
hay historial. No fabrica identidad, permiso o cierre.

FlowManager no importa/crea flows en Start ni borra eventos. Los guards compartidos
bloquean Start/Resume de AgentLoop/manager y el cableado de listeners; la entrada
directa de BaseEventListener tampoco crea un poller. El viejo engine rechaza el
proyecto antes de configurar o llamar un modelo.

Stop conserva los registros de threads, autonomía y callbacks realmente vivos.
Un join que no confirma la salida mantiene el trabajador registrado; no limpia
asignaciones, eventos, ramas ni checkpoints. La admisión nativa conserva la
solicitud mientras haya actividad registrada viva o desconocida. La prueba de
cierre se limita a esos trabajadores; el handoff no demuestra exclusión física
entre procesos ni terminación de una operación antigua desconocida.

## Pendientes principales

Quedan auxiliares/proveedores y herramientas antiguos que hay que retirar o
migrar junto con sus consumidores y dependencias: por ejemplo resumen en
`prompts/team.py`, detección de capacidades en `config/model_capabilities.py`,
`engine/llm_client.py` y el antiguo `DeepResearchTool`. Quedan pruebas antiguas
que esperan el comportamiento retirado, entradas legacy de Git/MCP/instalación,
cierre integral del proyecto, selección de material para sucesoras, publicaciones
retenidas y el resto del plan. No se declara suite global verde ni retirada de
CrewAI/LiteLLM de la distribución completa.

[Resultados](../modernization/project-producer-results.json) y
[paquete aislado](../modernization/project-producer-packaging.json) delimitan lo
comprobado; la calidad de un modelo real y la comprensión humana siguen abiertas.
