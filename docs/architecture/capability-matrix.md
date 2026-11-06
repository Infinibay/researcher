# Matriz de capacidades y migración

Estado: migración parcial. Los cierres recientes están en el tablero de ejecución
y en los contratos enlazados. Varias filas conservan requisitos del inventario
inicial: no constituyen por sí solas un diagnóstico del código actual. El cierre
integral sigue pendiente. Ver `native-runtime-boundary.md`.

`legacy-tool-schemas.json` conserva los nombres, clases, archivos y **schemas
Pydantic históricos de las 71 herramientas entonces registradas** en
el ya retirado `backend.tools.ALL_TOOL_CLASSES`. Se obtuvieron sin instanciar herramientas y
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
| `read_file`, `list_directory`, `glob`, lectura parcial y búsqueda literal | Lectura Ken y comandos/Python acotados en el workspace admitido | Vista y autoridad del intento; archivos externos por captura explícita | Wrappers antiguos retirados; usar los límites del comando y leer sus ventanas. Aislamiento cubierto por las pruebas de workspace/comandos. [Contrato](native-code-operations.md) |
| `write_file`, `edit_file`, inserción/reemplazo, edición múltiple y patches | Comandos/Python en la copia privada | Cierre físico de escritores; diff/candidato/checks con SHA; aceptación/publicación separadas | Wrappers retirados, recorrido nativo comprobado. [Contrato y alcance](native-code-operations.md) |
| `code_search`, descubrimiento de símbolos/referencias/estructura y diagnósticos | Ken y comprobadores del lenguaje disponibles; recuperación documental separada | Un solo índice de código; cobertura e incertidumbre explícitas | Índice y dos indexadores CLI antiguos retirados. No equiparar una consulta vacía con ausencia ni un toolchain ausente con diagnóstico limpio. [Contrato](native-code-operations.md) |
| `add_symbol`, `edit_symbol`, `remove_symbol`, `rename_symbol`, `move_symbol` | Lectura Ken → transformación local explícita → actualización de callers/imports → candidato/check | Escrituras exclusivamente en copia privada; no API semántica universal ni aceptación por texto | Recorrido real de efectos con generación/Ken controlados; implementación antigua retirada. Evaluación de calidad real/multilenguaje pendiente. [Contrato](native-code-operations.md) |
| `git_diff`, `git_status` | Lecturas nativas del workspace/candidato identificado | Base/HEAD y scope reales, sin singleton del último diff | Wrappers antiguos retirados; vistas/comandos del recorrido nativo conservados. [Contrato](native-adapter-retirement.md) |
| `git_branch`, `git_commit` | Copia privada, captura de candidato y publicación explícita del host | Repositorio/intento fijados; aceptación sobre SHA y recibo original | Wrappers retirados; publicación después de revisión/aceptación ensayada con Git/kernel/SQLite reales. Migraciones integrales pendientes. [Contrato](native-adapter-retirement.md) |
| `git_push`, `create_pr`, `merge_pr` | Host de publicación local/remota y reconciliación | Credencial del host; permiso de propietario sobre SHA exacto, identidad remota, respuesta perdida sin replay ciego | Wrappers retirados; pruebas nativas de CAS, publicación y protocolos de PR/merge. Servicios remotos controlados donde se indica. [Contrato](remote-publication.md) |
| `execute_command`, `code_interpreter` | Jobs nativos con dueño, timeout, salida recuperable y cancelación verificable | FS/red/entorno por intento; Python estándar aislado, escritura sólo en copia de desarrollo | Wrappers retirados; se conserva la ejecución nativa y se elimina el fallback directo sin sandbox. Extensiones de toolchain y aceptación global siguen explícitas. [Contrato](host-analysis-tools.md) |
| `create_task`, `take_task`, `update_task_status`, `set_task_dependencies` | MCP de coordinación del producto | Claim/lease y contexto vigentes; transición+evento atómicos; sin completar por texto del modelo | Pendiente. Doble claim, intento obsoleto, cancelación y corrección concurrentes |
| `get_task`, `read_tasks`, `check_dependencies`, `read_task_history` | Lecturas tipadas por alcance | Identidad del grant, cursores estables, estados y aceptación separados | Pendiente; casos de dos proyectos con ids ajenos y más de una página |
| `add_comment`, `read_comments` | Comentarios persistidos y recuperables por tarea | Append idempotente; autor real, referencias y orden durable | Pendiente. Retry no duplica; comentario no cambia estado por contener una orden |
| `approve_task`, `reject_task` | Decisión de aceptación del host/reviewer independiente | Veredicto asociado a candidato, checks, contexto y evidencia; no autoaprobación del productor | Pendiente. Nuevo SHA invalida aceptación pertinente y bloqueo impide merge |
| `save_session_note`, `load_session_note` | Notas de continuidad del producto | Proyecto/tarea/actor y revisión; notas son contexto asesor, no autorizaciones | Pendiente. Recuperar con vigencia visible, sin replay del prompt original |
| `send_message`, `read_messages`, `ask_team_lead`, `ask_project_lead` | Chat legible más operaciones tipadas de coordinación | Identidad causal, destinatario y propósito; entrega, lectura y aplicación distintas | Pendiente. Dedup, saturación, agentes inactivos y órdenes incompatibles; sin coordinador alternativo por chat |
| `ask_user`, `reply_to_user` | Solicitudes/explicaciones durables y canal vivo del producto | Aclaración y permiso nativo separados; pregunta con propósito/alcance/estado. Respuesta ligada a solicitud vigente | Guía escrita, integración pendiente. No repetir autorizaciones válidas por perder un handle ni inferirlas del silencio |
| `web_search` | Búsqueda del Codex admitido con modo congelado | Suscripción, eventos atribuidos, URL candidata separada de fuente/cita | Implementado y ensayado; wrapper antiguo y políticas de captura web siguen por retirar/migrar. [Contrato y ensayo real](native-web-search.md) |
| `web_fetch`, `scrape_website` | `researcher_capture_web`, `researcher_source_read/search` | `sources.capture/read`; HTTPS público, DNS/TLS/redirects/tamaño/deadline; snapshot y provenance canónicos | HTML/texto/PDF directos con robots y frecuencia compartida por instancia HTTP; Stop y citas comprobados. Política de Spider y retirada de wrappers pendientes. [Contrato](direct-web-policy.md) |
| `read_paper`, `pdf_search` | Captura binaria acotada + parser PDF local + búsqueda con citas de página | Mismo grant; almacenamiento binario reconciliable, parser con límites de CPU/memoria/páginas; hashes y revisión | Parcial: PDF/URL/DOI/arXiv capturados con páginas/hash y piloto Archivos. `researcher_source_query` añade recuperación semántica multilingüe local, assets fijados, offsets/cobertura completos y cierre del worker; búsqueda literal separada. Ensayo nativo de cola→cita→draft retenido. No retira roles/flows/reviewer ni consumidores externos; evaluación representativa y presupuesto agregado pendientes. Véanse [artículos](paper-capture.md) y [recuperación semántica](semantic-source-retrieval.md) |
| `csv_search`, `docx_search`, `json_search`, `xml_search` | Captura canónica, estructura y recuperación local por fuente | Límites de parser/expansión, hashes, offsets y citas; sin inferencia oculta | Wrappers RAG retirados. Parsers/semántica/MCP comprobados; migración de colecciones antiguas y evaluación representativa siguen pendientes. [Contrato](structured-sources.md) |
| `code_docs_search` | Ken local, Context7 opcional y documentación externa capturada | Fuente/revisión y cuota externa explícitas; búsqueda del snapshot local | Wrapper y configuración CrewAI retirados; se conserva el recorrido nativo documentado. No crawling implícito de toda una biblioteca ni embedding API oculto. [Contrato](native-adapter-retirement.md) |
| `deep_web_research` | Composición en el runtime de búsqueda/captura/findings/reporte | Síntesis dentro del presupuesto de ejecución; no nested LLM oculto en herramienta | Recorrido mínimo ensayado con URL conocida; búsqueda y amplitud de investigación pendientes |
| `spider_scrape` | `researcher_capture_spider` → fuentes canónicas → cita/hallazgo explícito | Clave y límite de créditos del host; una URL, modo smart/browser/http; captura markdown/texto con procedencia y costes atribuidos | Implementado por MCP/API/SQLite, límites y fallos probados con proveedor controlado. Módulo CrewAI y extra/SDK retirados; no se equipara fetch ordinario con renderizado. Calidad/disponibilidad externas y presupuesto agregado pendientes. [Contrato](spider-sources.md) |
| `read_reference_files` | `researcher_reference_list`, `researcher_capture_reference`, lectura/búsqueda de snapshot | `sources.read/capture`; ruta del host no expuesta; lectura por FD, sin traversal/symlinks, cuota de bytes | Implementado para UTF-8, PDF con texto y CSV/DOCX/JSON/XML, vía la misma fachada/API y revalidación al commit. Estructura paginada, citas sobre snapshot normalizado; límites en [formatos estructurados](structured-sources.md) y [PDF](pdf-sources.md) |
| `record_finding` | `researcher_finding_record` | `findings.write`, citas exactas, grant/contexto vigente, estado provisional, confianza desconocida; receipt atómico | Implementado y probado. No convierte similitud o redacción convincente en evidencia validada |
| `read_findings`, `search_findings`, `summarize_findings` | Registro tipado: `researcher_finding_list/read/query/summary` | Proyecto del grant, filtro de lectura por tarea, cursores/ventanas independientes, declaración histórica separada de revisión acreditada | Implementado en fachada/API y piloto Hallazgos: búsqueda FTS combina filtros; semántica local cubre un corpus completo acotado y exige huellas en continuaciones. Citas/JSON heredado paginados, captura citada verificada por hash para el propietario. Falta migrar roles/adaptadores/proveedores antiguos y revisión independiente. [Contrato](finding-registry.md) |
| `search_knowledge` | Composición tipada entre hallazgos, Wiki, fuentes y reportes | Cada componente conserva proyecto, procedencia, cobertura y límites | Operaciones individuales implementadas parcialmente; falta migrar búsqueda unificada y consumidores heredados sin prometer cobertura inexistente |
| `validate_finding`, `reject_finding` | Revisión explícita del conocimiento con evidencias | Reviewer, método, dependencias y versión; invalidar/revisar consumidores ante corrección | Pendiente. No asignar confianza científica por contrato de formato |
| `write_report`, `read_report` | `researcher_report_write/read` y vista `/reports` | `reports.write/read`; Markdown canónico en `artifacts.content`, finding links, draft y recibo; paginación independiente de citas | Persistencia, recovery/fachada y API probados. Informes ya tiene piloto y20 estados de navegador verificados; aceptación humana/total y exportación pendientes |
| `read_wiki`, `search_wiki`, `write_wiki` | Wiki tipada local/global, revisiones y capturas para citas | Permisos separados; página+revisión observadas; recibos atómicos, historial retenido, parent del mismo alcance | Implementación parcial: cinco tools nativas y adaptadores heredados comparten identidad protegida; misma ruta en dos proyectos/global, carreras, respuesta perdida y borrado/recreación probados. SearchWiki aún usa su proveedor legado. Faltan consumidores/invalidación dependiente/evaluación representativa. Ver [contrato](wiki-knowledge.md) |
| `create_hypothesis` | Hipótesis versionada en el dominio de investigación | Contexto, evidencia y estado experimental; un hallazgo no la valida automáticamente | Pendiente. Conservar el recorrido de revisión científica |
| `create_epic`, `create_milestone`, `update_project`, `read_epics`, `read_milestones` | Operaciones de planificación del producto por MCP | Lectura/escritura por grant; claves de operación, dependencias y eventos atómicos | Pendiente. No usar SQL genérico como sustituto |
| `create_repository` | Bootstrap/adopción/reparación explícitos del host | Reconciliar remoto/local/DB antes de retry; credencial host, no force push por alta parcial | Pendiente. Probar remoto creado+DB fallida y repo preexistente |
| `query_database` | Interfaz SQL genérica del modelo retirada | Lecturas tipadas y por alcance; no exponer env_vars ni base global | Módulos retirados. Operaciones administrativas del propietario fuera del catálogo del modelo; no sustituir capacidades de dominio pendientes por SQL. [Contrato](native-adapter-retirement.md) |
| `context7_search_library`, `context7_get_docs` | `researcher_context7_search`, `researcher_context7_docs` → fuentes canónicas | Clave opcional del host, cuota propia, scope del grant, hash/procedencia/versiones; no inferencia ChatGPT | Implementado por MCP/API/SQLite, con transporte acotado y fallos/recibos/revocación probados. Tres módulos CrewAI retirados. Proveedor controlado en pruebas; disponibilidad/eficacia externas no evaluadas. [Contrato](context7-sources.md) |

## Wire contract demostrado

El MCP nuevo anuncia veintidós herramientas `researcher_*`, con schemas explícitos,
anotaciones y errores MCP reales. No recibe proyecto/tarea/actor en argumentos,
no emite grants y no ejecuta SQL. Referencias: `scripts/researcher_mcp_server.py`,
`backend/api/models/research.py`, `backend/research/models.py` y
`docs/modernization/research-mcp-evidence.json` como ensayo histórico; catálogo actual en
`docs/modernization/findings-tool-schema.json` y firmas canónicas. Esto demuestra el subconjunto
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
