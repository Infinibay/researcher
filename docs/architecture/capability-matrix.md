# Matriz de capacidades y migración

Estado: inventario verificado; migración parcial. Codex está integrado al primer
recorrido de investigación por API autenticada; el resto del catálogo continúa
pendiente. Ver `native-runtime-boundary.md`. Una fila pendiente no es una
capacidad ya disponible.

`legacy-tool-schemas.json` conserva los nombres, clases, archivos y **schemas
Pydantic actuales de las 71 herramientas registradas** en
`backend.tools.ALL_TOOL_CLASSES`. Se obtuvieron sin instanciar herramientas y
con conexión de sockets bloqueada. Las declaraciones adicionales fuera del
registro están separadas: su existencia no demuestra uso ni autoriza retirarlas.
Los schemas antiguos son evidencia de compatibilidad a migrar, no el contrato
que se expondrá sin cambios al modelo.

## Reglas comunes del destino

El host fija proyecto, tarea, actor, intento y versión de contexto. Un argumento
del modelo no puede cambiar esa identidad. Lecturas y escrituras validan el
alcance; una escritura necesita permiso vigente y clave de operación. Resultado
y receipt se guardan atómicamente donde la operación es local. Los efectos
remotos inciertos requieren reconciliación, no replay automático. El runtime
produce una propuesta; aceptar, completar y publicar son decisiones del producto.

En las filas pendientes, los nombres finales y schemas del nuevo MCP deben
quedar capturados y probados antes de migrar consumidores. No se usarán SQL
genérico ni chat libre para cubrir operaciones que falten.

## Destino por capacidad

| Herramientas actuales | Destino | Permisos, efectos y persistencia | Estado y prueba exigida |
| --- | --- | --- | --- |
| `read_file`, `list_directory`, `glob` | Lectura nativa en workspace confinado; adjuntos fuera de ese árbol por MCP propio | Lectura limitada por raíz real; sin credenciales ni montajes de otros proyectos | Parcial en fixtures nativos. Falta probar confinamiento de proceso, symlinks y mounts del despliegue |
| `write_file`, `edit_file` | Edición nativa en worktree propio | Escritura de archivos, sin permiso implícito de commit/push. Evidencia: diff Git completo del candidato | Corrección sintética probada en ambos candidatos; falta integración con aceptación y recuperación |
| `code_search`, `directory_search` | Ken MCP para código y documentos del repo; búsqueda documental del proyecto separada | Ken obligatorio por workspace; cobertura, revisión e índice visibles; consultas vacías no prueban ausencia | Ken real probado en fixtures. Falta preparado completo del repo y confinamiento de rutas. No retirar búsqueda de documentos no soportados por Ken |
| `git_diff`, `git_status` | Lecturas nativas/host sobre repo identificado | Lectura de repo/base/head reales; sin singleton de «último diff» | Pendiente del recorrido de candidato versionado |
| `git_branch`, `git_commit` | Servicio Git del host y MCP tipado | Repo/worktree/intento fijados; locks y receipt; no adoptar ni reparar un repo por accidente | Pendiente. Probar homónimos, carreras, commit incierto y reinicio |
| `git_push`, `create_pr`, `merge_pr` | Host de publicación, detrás de aceptación sobre SHA exacto | Credencial del host; scope de autorización explícito. Persistir identidad remota y reconciliar antes de retry | Pendiente. CI/review de A no autoriza B; un DONE nativo no publica |
| `execute_command`, `code_interpreter` | Jobs confinados con dueño, timeout y cancelación verificable | FS/red/entorno por intento; sin tokens heredados. Conservar estado de job y salida recuperable | El transporte nativo sólo posee su peer RPC. Falta demostrar propiedad de todos los jobs y efectos tras crash |
| `create_task`, `take_task`, `update_task_status`, `set_task_dependencies` | MCP de coordinación del producto | Claim/lease y contexto vigentes; transición+evento atómicos; sin completar por texto del modelo | Pendiente. Doble claim, intento obsoleto, cancelación y corrección concurrentes |
| `get_task`, `read_tasks`, `check_dependencies`, `read_task_history` | Lecturas tipadas por alcance | Identidad del grant, cursores estables, estados y aceptación separados | Pendiente; casos de dos proyectos con ids ajenos y más de una página |
| `add_comment`, `read_comments` | Comentarios persistidos y recuperables por tarea | Append idempotente; autor real, referencias y orden durable | Pendiente. Retry no duplica; comentario no cambia estado por contener una orden |
| `approve_task`, `reject_task` | Decisión de aceptación del host/reviewer independiente | Veredicto asociado a candidato, checks, contexto y evidencia; no autoaprobación del productor | Pendiente. Nuevo SHA invalida aceptación pertinente y bloqueo impide merge |
| `save_session_note`, `load_session_note` | Notas de continuidad del producto | Proyecto/tarea/actor y revisión; notas son contexto asesor, no autorizaciones | Pendiente. Recuperar con vigencia visible, sin replay del prompt original |
| `send_message`, `read_messages`, `ask_team_lead`, `ask_project_lead` | Chat legible más operaciones tipadas de coordinación | Identidad causal, destinatario y propósito; entrega, lectura y aplicación distintas | Pendiente. Dedup, saturación, agentes inactivos y órdenes incompatibles; sin coordinador alternativo por chat |
| `ask_user`, `reply_to_user` | Solicitudes/explicaciones durables y canal vivo del producto | Aclaración y permiso nativo separados; pregunta con propósito/alcance/estado. Respuesta ligada a solicitud vigente | Guía escrita, integración pendiente. No repetir autorizaciones válidas por perder un handle ni inferirlas del silencio |
| `web_search` | Búsqueda web explícita y acotada | Red y proveedor declarados; no key ajena ni fallback de pago implícito. Persistir fuentes capturadas por separado | Pendiente; captura de URL conocida ya funciona. Probar fallo de proveedor y resultados parciales |
| `web_fetch`, `scrape_website` | `researcher_capture_web`, `researcher_source_read/search` | `sources.capture/read`; HTTPS público, DNS/TLS/redirects/tamaño/deadline; snapshot y provenance canónicos | Implementado para HTML/texto y probado por MCP real. No cubre scraping JS ni todas las políticas de robots/rate-limit del producto |
| `read_paper`, `pdf_search` | Captura binaria acotada + parser PDF local + búsqueda con citas de página | Mismo grant; almacenamiento binario reconciliable, parser con límites de CPU/memoria/páginas; hashes y revisión | Parcial: PDF adjunto/URL→texto/páginas/hash→cita→borrador, worker limitado y piloto Archivos implementados. `researcher_capture_paper` añade URL/DOI/arXiv al catálogo nativo con versión/procedencia, sin inferencia anidada; HTML DOI no implica texto completo. La búsqueda actual es literal y NO sustituye la recuperación semántica anterior. Roles/flows/reviewer y consumidores externos sin migrar: no retirar herramientas antiguas. Véase [captura de artículos y límites](paper-capture.md) |
| `csv_search`, `docx_search`, `json_search`, `xml_search` | Parsers locales y recuperación determinista por proyecto; índice local opcional | Límites de archivo/expansión/parser, chunks y fuente recuperables; ninguna inferencia oculta | Pendiente. Mantener búsqueda útil y contraevidencia al final; quitar el proveedor remoto transitivo de CrewAI Tools |
| `code_docs_search` | Ken para código local y documentación externa capturada | Código y documentos conservan fuente y revisión; no confundir embeddings con suscripción | Pendiente del recorrido documental completo |
| `deep_web_research` | Composición en el runtime de búsqueda/captura/findings/reporte | Síntesis dentro del presupuesto de ejecución; no nested LLM oculto en herramienta | Recorrido mínimo ensayado con URL conocida; búsqueda y amplitud de investigación pendientes |
| `spider_scrape` | Integración opcional de scraping avanzado, aislada del camino por defecto | Servicio/credencial propios, red declarada; snapshots consumibles por el resto del producto | Pendiente de decisión de compatibilidad. No afirmar equivalencia del fetch de texto con navegador/servicio avanzado |
| `read_reference_files` | `researcher_reference_list`, `researcher_capture_reference`, lectura/búsqueda de snapshot | `sources.read/capture`; ruta del host no expuesta; lectura por FD, sin traversal/symlinks, cuota de bytes | Implementado para UTF-8 y PDF con texto, vía la misma fachada/API y revalidación al commit. DOCX y otros formatos pendientes; límites en [PDF](pdf-sources.md) |
| `record_finding` | `researcher_finding_record` | `findings.write`, citas exactas, grant/contexto vigente, estado provisional, confianza desconocida; receipt atómico | Implementado y probado. No convierte similitud o redacción convincente en evidencia validada |
| `read_findings`, `search_findings`, `summarize_findings`, `search_knowledge` | Lectura/búsqueda/resumen estructurado del conocimiento por proyecto | `researcher_finding_read` existe; búsqueda deberá preservar estado, revisiones, procedencia y superseded | Lectura individual implementada; listado, búsqueda y resumen amplio pendientes |
| `validate_finding`, `reject_finding` | Revisión explícita del conocimiento con evidencias | Reviewer, método, dependencias y versión; invalidar/revisar consumidores ante corrección | Pendiente. No asignar confianza científica por contrato de formato |
| `write_report`, `read_report` | `researcher_report_write/read` y vista `/reports` | `reports.write/read`; Markdown canónico en `artifacts.content`, finding links, draft y recibo; paginación independiente de citas | Persistencia, recovery/fachada y API probados. Informes ya tiene piloto y20 estados de navegador verificados; aceptación humana/total y exportación pendientes |
| `read_wiki`, `search_wiki`, `write_wiki` | Wiki tipada con identidad local/global explícita | Ruta única por proyecto; reglas separadas para global, parent y precedencia; revisión y autor | Pendiente. Misma ruta en dos proyectos y global no colisiona ni edita otro documento |
| `create_hypothesis` | Hipótesis versionada en el dominio de investigación | Contexto, evidencia y estado experimental; un hallazgo no la valida automáticamente | Pendiente. Conservar el recorrido de revisión científica |
| `create_epic`, `create_milestone`, `update_project`, `read_epics`, `read_milestones` | Operaciones de planificación del producto por MCP | Lectura/escritura por grant; claves de operación, dependencias y eventos atómicos | Pendiente. No usar SQL genérico como sustituto |
| `create_repository` | Bootstrap/adopción/reparación explícitos del host | Reconciliar remoto/local/DB antes de retry; credencial host, no force push por alta parcial | Pendiente. Probar remoto creado+DB fallida y repo preexistente |
| `query_database` | Retirar del catálogo del modelo; reemplazar usos por consultas de negocio/analytics tipadas | El SQL de sólo lectura también puede revelar secretos y otros proyectos; no exponer `env_vars` | Pendiente migrar consumidores y probar alcance. El nuevo MCP no contiene SQL |
| `context7_search_library`, `context7_get_docs` | Herramientas documentales opcionales o adaptador de fuentes | Servicio/credencial propios y procedencia; no activarlo por defecto como inferencia ChatGPT | Pendiente de integración y pruebas de red/fallo; conservar documentación actualizada cuando se habilite |

## Wire contract demostrado

El MCP nuevo anuncia diez herramientas `researcher_*`, con schemas explícitos,
anotaciones y errores MCP reales. No recibe proyecto/tarea/actor en argumentos,
no emite grants y no ejecuta SQL. Referencias: `scripts/researcher_mcp_server.py`,
`backend/api/models/research.py`, `backend/research/models.py` y
`docs/modernization/research-mcp-evidence.json`. Esto demuestra el subconjunto
de investigación, no la migración del catálogo completo.

Ken real y el MCP de negocio se descubrieron en ambos candidatos. El bridge de
Infinidev 0.30.0 rechaza un `null` explícito en ciertos opcionales que el schema
original admite; el diagnóstico directo, sin modelo, se conserva con la
evaluación. Una traducción de schema es parte del contrato a probar, no un
detalle que se pueda atribuir automáticamente a mal prompting.

El cierre requiere destino implementado y prueba por cada capacidad retenida,
consumidores migrados y retiro justificado por capacidad de las que no se
conserven. No borrar una familia porque sus pruebas antiguas fallen ni marcar
una fila aprobada por compartir nombre con una herramienta nativa.
