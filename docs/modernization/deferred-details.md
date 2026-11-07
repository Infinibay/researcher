# Detalles diferidos

Política explícita del usuario, 2026-11-05: resolver primero lo grueso. Cuando el
resultado central de una tarea funcione, registrar los detalles secundarios y
avanzar con la siguiente capacidad. Retomar esta lista en una pasada posterior de
pulido; los pendientes se conservan dentro del alcance completo.

Al reanudar o después de una compactación, leer esta política y el tablero.
Elegir el siguiente resultado principal antes de volver sobre detalles. Un fallo
que impida ese resultado central se resuelve dentro de su tarea.

Registrar cada detalle con una descripción breve, su ubicación y el momento de
retomarlo. No convertir su registro en otra investigación o implementación.

| ID | Detalle observado | Ubicación | Retomar |
| --- | --- | --- | --- |
| DD-001 | Estilo antiguo del parser de sufijo `.git`, aviso Ruff FURB188 ya documentado. | `backend/git/pr_service.py`, `_resolve_owner_repo` | Pulido o retirada del consumidor legacy; no bloquea el nuevo recorrido. |
| DD-002 | Avisos existentes de bundle frontend grande y datos Browserslist antiguos. La compilación y los recorridos comprobados funcionan. | Build de `frontend/package.json` | Pasada de rendimiento y dependencias después de cerrar las capacidades principales de la interfaz. |
| DD-003 | El esquema 43 instala publicación; faltan las inversas 43/44/45/46/47/48/49/50/51/52/53/54 y adaptar fixtures que revierten directamente40/41/42. Fallo comprobado: `test_code_acceptance_inverse_preserves_reviews_and_refuses_owner_history`; el guard de esquema posterior rechaza el rollback. No debilitar ese guard. | `backend/db/development_migration.py`, tests de migración/aceptación | Pasada de migraciones/restore antes de aceptación integral; no bloquea la publicación local hacia delante. |
| DD-004 | Mostrar reintento de arranque cuando una publicación queda en cola por capacidad y presentar el host sin etiqueta de modelo. | `CodePublicationRequest.tsx`, `TaskRunWorkspace` | Pasada de controles/estados de Tareas; conservar recibo original. |
| DD-005 | Si una observación se interrumpe antes de guardar su recibo, el mismo comando no reactiva el observador anterior; hace falta consultar el intento actual y preparar explícitamente otra observación después de su cierre. También ampliar el caso sin ningún comando admitido. | `PublicationRecovery.begin`, `publication_closure.py`, controles de recuperación | Pasada de recuperación/crashes; mantener la prohibición de repetir la escritura original. |
| DD-006 | La admisión remota exige prerrequisito `accepted`; un resultado positivo preservado tras retirada necesita adopción explícita con evidencia fresca antes de la siguiente acción. No reutilizar el lease cerrado ni repetir el efecto. | `RemotePublications.admit_once` | Pasada de recuperación remota después del transporte; conservar dentro del alcance completo. |

| DD-007 | Comando remoto de observación interrumpido antes del recibo, compatibilidad de intentos antiguos sin identidad HTTP y ampliación de prueba de crash del host HTTP. No inferir cierre de un PID vivo ni inventar identidad retrospectiva. | `remote_clients.py`, `remote_recovery.py`, controles de Tareas | Pasada de recuperación/crashes y migración antes de aceptación integral. |

| DD-008 | Paginar historial remoto más allá de100 operaciones y seleccionar cadenas antiguas; hoy el límite es visible y bloquea decisiones nuevas para no inferir ausencia. Pulir también textos secundarios del panel. | `RemoteDestinations.history`, `RemotePublications.tsx` | Pasada integral de historial/UI después de capacidades principales; sin rehacer ahora el transporte. |

| DD-009 | Selector de repositorio en inicio de proyecto con múltiples registros, labels/estado de proyecto y mensaje histórico del agente después de aceptar el plan. Hoy API admite ID explícito y web conserva el inicio original; sin selección única rechaza el arranque. | `projectPlans.ts`, `useProjects.ts`, Header/Projects/Tasks | Rediseño integral de Proyectos/Flujo y pasada de interacción; no rehacer ahora la planificación central. |
| DD-010 | Integración de borrado/archivo/restore con historia nativa de planificación y esquema47; aclarar expansión de planes existentes/anidados antes de ampliar despacho. Conservar receipts y guards; no borrar datos para resolverlo. | `backend/planning/`, migraciones y CRUD de proyecto/tarea | Pasada de lifecycle/migraciones antes de aceptación integral. |

| DD-011 | Localizar impedimentos del coordinador, detalle de evidencia por entrega, prioridad de nodos independientes, paginación/lectura de snapshots grandes y selección por rama. Conserva causalidad y límites; no iniciar otro ciclo de pulido ahora. | `backend/planning/execution.py`, panel PlanExecution | Pasada de coordinación/interacción después del cutover principal. La continuación explícita de entregas cerradas ya está conectada. La reautorización explícita de grafos corregidos ya está conectada. Adopción de drafts/runs manuales no aceptados y archivos de candidatos sigue como capacidad principal pendiente, no mero pulido. |

| DD-012 | Presentación/paginación avanzada de terminal y notas, proyección viva tras registro y flujo de reintento de notas web. El binding persistido de endpoint de clientes web y la paridad de preguntas/revisión científica/publicación/recuperación son capacidades de integración pendientes, no simple pulido. | OwnerClient, TUI, frontend de conversación y owner actions | Integración de comunicación/controles después de consumidores principales; conservar contexto y recibos originales. |
| DD-013 | Ruff amplio incluye19avisos en index/watchers antiguos sin modificar; no se ejecutan al iniciar la terminal nueva. No limpiarlos por estilo antes de decidir su retirada por consumidores. | `backend/cli/file_watcher.py`, `index_queue.py`, `initial_index.py` | Cutover de code intelligence/retirada legacy; los módulos cambiados pasan Ruff. |

| DD-014 | Hipótesis sin ensayo: revisar recuperación del journal privado tras symlink roto, cambio de alias/origen y restauración de estado. No inferir continuidad por etiquetas; comprobar casos antes de habilitar rebind/adopción. | `TerminalJournal.read`, protocolo de endpoint y backup/restore | Fase de recuperación/instalación, con casos reproducibles y preservación de intención original; no nueva pasada de pulido ahora. |

| DD-015 | Localizar estados secundarios del panel de continuación (por ejemplo `cancelled`), sustituir IDs por títulos cuando estén disponibles y facilitar lectura de cadenas largas de sucesoras. El recorrido central ya conserva evidencia, pausa y recibos. | `DeliveryContinuation.tsx`, `PlanExecution.tsx`, `planContinuations.ts` | Pasada de presentación/interacción después de capacidades principales; no otra iteración de pulido ahora. |

| DD-016 | Dos avisos Ruff I001 en imports locales antiguos de `sqlite_runs.py`, comprobados también sobre basea6dcb3a. No cambian por la nueva admisión de grafos corregidos. | Bloques de imports locales de `SQLiteRunStore`, líneas1427/1527 en este checkpoint | Pasada de retirada/refactor del store; no limpiar por estilo ahora. Nuevos módulos pasan Ruff; el store pasa al excluir únicamenteI001. |

| DD-017 | Localizar las cabeceras canónicas del resumen exploratorio, paginar las referencias de runs del handoff antiguo y resolver avisos Ruff de estilo de imports. Comparación con base2c8d64c:28avisos heredados y2I001 nuevos en imports de modelos/rutas; sin correcciones de estilo en esta entrega. | `InvestigationSummary.report`, `legacy_handoff.py`, modelos/rutas HTTP y handlers antiguos; evidencia `investigation-lint.json` | Pulido posterior al corte de consumidores principales; la investigación, su procedencia y la aceptación funcionan. |

| DD-018 | Presentar de forma más cómoda los metadatos de salida de comandos y sus límites, y localizar las cabeceras del documento de captura. Las citas, bytes, cierre, errores y truncamiento ya se conservan. No ampliar ahora la captura a desarrollo ni inventar una normalización binaria. | `command_sources.py`, lectores de fuentes/informes | Pulido de fuentes tras el corte de activadores principales; los demás tipos de ejecución se integran dentro de su entrega principal. |


| DD-019 | Cuatro avisos Ruff nuevos de estilo en consumidores antiguos: tres I001 en imports locales del motor y un TRY004 por rechazo de tipo de evento. Hay50avisos heredados,16resueltos por la sustitución de bloques; conservar comparación `project-owner-lint.json`. | `loop_engine.py`, `agent_loop.py` | Retirada de estos consumidores o pulido posterior; no otra pasada del controlador. La exclusión global atómica y la adopción de trabajo previo siguen siendo capacidades principales, no detalles de estilo. |


| DD-020 | Mostrar el origen seleccionado y su descarga desde el recibo de admisión también antes del primer intento, tras recargar una solicitud en cola. Hoy el servidor conserva la selección exacta y retry_start la reutiliza; la entrada literal completa se muestra una vez reservado el intento. | `CodeCarryovers.input`, `QueuedStart`, `RunInputRecord`, selector de cambios previos | Integración/aceptación de Tareas y comunicación: hacer visible ese contexto al decidir reintentar. No reabrir ahora el protocolo de admisión ni tratarlo como adopción de worktrees antiguos, que sigue siendo capacidad principal. |


| DD-021 | Un I001 nuevo en un import local del test público y falta docstring en el método heredado `TestDevelopmentFlowHelpers.test_check_dependencies_resolved`, cuyo setup pasó a historia insertada. Producción modificada documentada y sin avisos nuevos;12avisos heredados y29resueltos. No reabrir el recorrido físico para estos detalles. | `test_public_development.py`, `test_development_flow.py`; `code-flow-lint.json`, `code-flow-docstrings.json` | Pasada de documentación/estilo posterior a los cortes principales, antes de aceptación integral. |


| DD-022 | Dos tests heredados de Stop modificados para simular trabajadores ya existentes carecen de docstring propio. Seis RUF059 de handles sintéticos no usados y un S102 por compilar exclusivamente la función conocida de la fixture controlada. Producción modificada documentada y sin avisos nuevos;7heredados,34resueltos. | `test_listener_lifecycle.py`, `test_project_producer_retirement.py`; `project-producer-docstrings.json`, `project-producer-lint.json` | Pasada de documentación/estilo después de retirar consumidores principales. No repetir el ensayo nativo por estos detalles. |


| DD-023 | Cuatro RET501 por `return None` explícito en hooks de proveedor ya inertes y un docstring pendiente en `_query` del lector histórico, modificado para ordenar por ID. Son detalles de estilo/documentación; el no-gasto de proveedor y el aislamiento están comprobados.7avisos heredados,22resueltos. | `config/llm.py`, `prompts/team.py`; `auxiliary-lint.json`, `auxiliary-docstrings.json` | Pasada posterior de documentación/estilo. No reabrir el pipeline nativo ni el catálogo para este pulido. |

| DD-024 | Cinco avisos Ruff en la entrada MCP: BLE001 por el límite que oculta texto de excepciones inesperadas, dos SIM117 en contextos del test y dos I001 en launchers compatibles. La excepción amplia devuelve incertidumbre, no éxito ni reintento; su prueba verifica que no filtra el secreto sintético. Las29definiciones nuevas/modificadas tienen docstrings. | `backend/research/stdio_server.py`, `test_native_mcp_entry.py`, ambos scripts MCP; `native-mcp-lint.json`, `native-mcp-docstrings.json` | Pulido posterior, documentar o suprimir justificadamente el límite de excepciones; no repetir turnos nativos ni reabrir el SDK por estilo. |

| DD-025 | Dos PLW1510 de `subprocess.run` sin `check=False` explícito en el test de help/check del script. Los códigos de salida se verifican mediante asserts y la implementación nueva no tiene avisos. Las11definiciones nuevas están documentadas. | `backend/tests/cli/test_native_launcher.py`; `native-startup-lint.json`, `native-startup-docstrings.json` | Pasada de estilo posterior; no reabrir startup ni ensayos reales por estos dos argumentos. |

| DD-026 | Seis F811 por importar la fixture `legacy_publication` y usarla como parámetro pytest, más un I001 del test.42definiciones modificadas/nuevas documentadas;0avisos nuevos en producción. Compatibilidad secundaria: merge de PR inexistente deriva al ValueError del servicio (400), mientras la ruta anterior devolvía404; conservar esa semántica al pulir errores, sin habilitar merges. | `test_native_git_retirement.py`, `backend/api/routes/git.py`; `native-git-lint.json`, `native-git-docstrings.json` | Pasada de estilo/errores posterior. Importar ramas sin archivos retenidos y la cadena de publicación retenida siguen siendo capacidades principales pendientes, no DD026 ni pulido. |

| DD-027 | Once avisos nuevos en la incorporación de ramas: diez I001 de orden de imports y un F401 por `json` no utilizado.57definiciones nuevas/modificadas documentadas;8avisos heredados. No afectan la captura completa ni sus límites, recibos o exclusión antes del modelo. | `branch_inputs.py`, imports de modelos/routes/stores y tests; `prior-branch-lint.json`, `prior-branch-docstrings.json` | Pulido posterior, sin reabrir la cadena física por imports. La selección automática de material para sucesoras, metadata no registrada y evaluaciones integrales son capacidades principales, no DD027. |

| DD-028 | Tres I001 por orden de imports: uno de producción y dos en tests del lector causal. Las55definiciones nuevas/modificadas tienen docstrings. No repetir el recorrido físico para estos avisos. | `owned_runtime.py`, `test_owned_code_dependencies.py`, `test_predecessor_code_material.py`; `predecessor-material-lint.json`, `predecessor-material-docstrings.json` | Pulido posterior a las capacidades principales. Las cuatro inversas heredadas que fallan en la batería ampliada siguen en DD003; no debilitar sus guards. |

| DD-029 | Dos I001 de imports en informe/cierre y su test.26definiciones Python nuevas/modificadas documentadas y28definiciones/módulos TS revisados, sin faltantes;3avisos heredados. No repetir la cadena de cinco turnos por imports. | `backend/planning/completion.py`, `test_project_completion.py`; `project-completion-lint.json`, `project-completion-docstrings.json`, `project-completion-jsdoc.json` | Pulido posterior. Inversas DD003, historial ampliado de efectos/presupuestos, adopciones históricas y paridad terminal son obligaciones de integración, no estos dos avisos. |

| DD-030 | La identidad exacta de creación vive en metadata del recurso: el hard delete de un proyecto sin historia también la elimina. Derivación del código: reenviar después esa creación perdida puede generar otro ID. No se afirma una prueba de idempotencia después de borrado/restore. Es una obligación de ciclo de vida antes de aceptación integral, no mero pulido; decidir retención/tombstones sin cambiar silenciosamente el contrato de borrado. | `ProjectWorkspace.create`, `delete_project`; `project-workspace.md` | Integración del ciclo de vida: crear perdiendo respuesta → otro propietario elimina → recuperar la intención original; conservar la decisión de borrado y no resucitar recursos ni cambiar alcance. |

| DD-031 | Cuando sólo queda un grafo autorizado activo sin proceso, el control dice «Solicitar detención del trabajo observado». Su alcance y recibo son correctos, pero «Pausar despacho autorizado» explicaría mejor esa situación. | `ProjectsPage.tsx`, `_stop_scope`; captura desktop01 | Pulido de comunicación posterior; no repetir broker/kernel ni rediseñar Stop por esta etiqueta. |

| DD-032 | Pulido del explorador: rutas largas ocupan demasiado alto en el registro; números de línea/resaltado y una pista más visible del scroll horizontal del código mejorarían lectura. El contenido, commit/blob, foco y desplazamiento del archivo ya están verificados. | `RepositoriesPage.tsx`, `RepositoryFile.tsx`, `repositories.css`; comparación y capturas13–15 | Pulido posterior. No reabrir Git/recibos por estética; crear/clonar/reparar, presupuesto/concurrencia de lectores y submódulos siguen siendo trabajo funcional principal antes de aceptación integral. |


| DD-033 | Pulido de preparación de fuentes:25avisos Ruff en archivos tocados, incluidos heredados (imports/estilo y catches deliberados); ninguno de sintaxis o nombres indefinidos.150definiciones Python y54módulos/definiciones TS documentados. En móvil, reducir densidad de rutas, recuperar foco al cambiar formulario y traducir algún detalle técnico final. | `source-setup-lint.json`, `source-setup-docstrings.json`, `source-setup-jsdoc.json`; `SourceSetup.tsx` | Pasada posterior de pulido. No repetir Git/kernel por estos detalles. Crear remoto, reparar etapas incompletas y recuperar historia entre navegadores son trabajo principal, no DD033. |


| DD-034 | Once avisos estáticos en archivos del control físico, incluidos heredados: siete I001, un F401, SIM117, TRY004 y BLE001; ninguno de sintaxis o nombres indefinidos.45definiciones nuevas/modificadas documentadas. El servidor TLS de prueba puede registrar el EOF esperado al responder a un cliente ya retirado. | `source-control-lint.json`, `source-control-docstrings.json`; fixture TLS | Pulido posterior. No repetir kernel/native por imports, comentarios o ese log de desconexión. Remoto separado, reparación parcial, restore y evaluación de admisiones tardías siguen siendo trabajo principal. |


| DD-035 | Siete avisos Ruff en archivos de creación remota, incluidos heredados: TRY004, dos I001, F401, BLE001 y dos PLC0414 de fixtures; ninguno de sintaxis/nombres indefinidos.49definiciones Python y57módulos/definiciones TS documentados. Afinar la entrada lateral «Preparar fuente Git» y su explicación para descubrir también la creación remota; conservar los controles y recibos actuales. | `remote-source-lint.json`, `remote-source-docstrings.json`, `remote-source-jsdoc.json`; `RepositoriesPage.tsx` | Pasada de estilo/navegación posterior. No repetir TLS/kernel por esto. Tiempo total/red, Forgejo completo, reparación Git parcial, historia entre navegadores y restore siguen siendo trabajo principal antes de aceptación integral. |


| DD-036 |25avisos estáticos/de estilo en archivos de reparación, incluidos heredados, sin sintaxis/nombres indefinidos.47definiciones Python y63módulos/nombres TS documentados. Tras respuesta perdida, la lista lateral puede quedar vieja hasta abrir/actualizar fuentes aunque el recibo ya indique registro completo; también afinar densidad de rutas/foco móvil y explicación de la versión remota cuando no quedó HEAD. Los tests heredados barren el padre cgroup global: ejecutar QA con actores y esas comprobaciones en serie hasta delimitar sus propias identidades. | `source-repair-lint.json`, `SourceSetup.tsx`, `RepositoriesPage.tsx`; tests de source/kernel | Pulido/verificación posterior; no repetir kernel por copia/imports. Historia entre navegadores, reservas/adopción, reparación guardada sin programación, SHA256/submódulos/límites y restore siguen siendo capacidades principales. |


| DD-037 |5avisos estáticos en los archivos backend de historia, incluidos heredados, sin sintaxis/nombres indefinidos.4defsPython y75módulos/nombresTS documentados. La caché general es30s: reseleccionar puede reutilizar datos; «Consultar operación» fuerza lectura y los controles de otro fence se rechazan. Mostrar fecha de consulta y forzar nueva lectura al reseleccionar; afinar densidad de listas/rutas y foco. | `source-history-lint.json`, `SourceSetup.tsx`, `sourceOperations.ts`; capturas de historia | Pasada de pulido posterior; no otro ciclo Git/kernel por texto/caché. Reservas/adopción, reparación guardada sin programación, DD030/restore y aceptación global siguen siendo capacidades principales. |


| DD-038 | Afinar densidad de rutas, encuadre/foco y actualización de la lista lateral tras adoptar; heredado del piloto. No reabrir ahora imports/estilo ni otra ronda de capturas por esos detalles. | `SourceSetup.tsx`, capturas `2026-11-06-source-reservation`, DD036/DD037 | Resolver después de **todas las capacidades principales**, según reiteración del usuario del6nov. Configuración/modelos, prompts/comunicación, cuatro rutas y los demás bloques gruesos tienen prioridad. |


| DD-039 | Unificar los tokens visuales del diálogo oscuro con las páginas claras; afinar densidad, elección de agentes conocidos e historial de ediciones de configuración. La identificación exacta ya se explica y se muestra en Tareas; no se infiere de un rol. La validación de catálogo real/elección congelada/revisión optimista ya está implementada. | `ModelSettingsDialog.tsx`, `model-settings-results.json`, capturas `2026-11-06-model-settings` | Pulido **después de todas las capacidades principales**. No repetir actores/kernel por estos ajustes de interfaz; continuar ahora con el catálogo completo de prompts. |


| DD-040 | Compactar la representación repetida del inventario/ledger, uniformar estilo/imports y corregir detalles tipográficos de instrucciones después de todos los bloques principales. La revisión/frescura/versionado ya funciona; no repetir kernel por redacción. | `docs/prompts/`, `scripts/audit_prompt_inventory.py`, `backend/prompts/native.py` | Pulido final. La eficacia con modelos/personas, el timeout de checks, migración/restore y retirada del engine siguen siendo tareas principales, nunca detalles diferidos. |

## DD041 — densidad de Resumen y coherencia de cabecera

Después de todas las capacidades principales: compactar el espaciado de preguntas
sin perder contexto/paginación; unificar el fondo/margen móvil y peso del CTA.
La cabecera compartida ocupa varias filas y aún muestra etiquetas legacy en inglés;
retirar su interpretación de actividad basada en metadatos pertenece al bloque
principal de engine/estados; el ajuste visual de altura sí pertenece al pulido.
No se certifica aceptación integral de Resumen por el pase de fixtures/Axe.

## DD042 — densidad y vocabulario secundario de Planificación

Tras todas las capacidades principales: compactar espacios entre hitos/tareas,
armonizar contador singular/plural y etiquetas de relaciones, integrar ajuste de
cabecera/margen móvil conDD041. No retirar contexto ni hacer que estados parezcan
casillas de aceptación. La recuperación de CRUD sin operation_key y preservación
de historia pertenecen a engine/operación principal; no están diferidas como pulido.

## DD043 — densidad del registro de Agentes

Después de todas las capacidades principales: compactar cabecera/espaciado y
ajustar jerarquía de filas, singular/plural y agrupación visual por agente sin
perder ejecuciones anteriores. Integrar el ajuste móvil compartido deDD041.
La identidad, consulta nativa, consumo desconocido, paginación y Stop ya funcionan.
Historial completo de intentos/presupuestos, cierre físico global y retirada de
consumidores legacy siguen como capacidades principales, no como pulido diferido.

## DD044 — densidad e inspector de Ejecución

Después de todas las capacidades principales: compactar etiquetas/espacios del
inspector y controles reutilizados, armonizar singular/plural e integrar la
cabecera móvil compartida. Mantener el título accesible y la distinción entre
relación causal e historia. La navegación, evidencia y pausa original ya funcionan.
Recuperación física global, presupuestos completos, retiradas legacy y evaluación
humana siguen como capacidades principales; no se difieren como pulido.

## DD045 — presentación compacta de los controles generales

Después de todas las capacidades principales: reducir la altura móvil de la
cabecera y armonizar hover/espaciado de sus botones con el shell seleccionado,
conservando errores y diferencia entre solicitud registrada y cierre físico.
La consulta nativa, detención original y navegación ante respuesta tardía están
comprobadas. La retirada del resto del engine, los estados físicos y la validación
global siguen como trabajo principal; no se difieren aquí.

## DD046 — estilo después de retirar el engine

Después de todas las capacidades principales: ordenar el import local señalado
por I001 en `test_legacy_engine_removal.py` y quitar la línea vacía final de
`backend/tests/flows/conftest.py`. Los restantes once avisos de esos archivos son
anteriores; no reabrir los ensayos de ejecución por estilo.
La prueba de migración54 que instala55 al preparar53 sigue como fallo principal
del bloque migraciones/restore, no como detalle diferido.

## DD047 — estilo del ensayo Context7

Después de todas las capacidades principales: simplificar los context managers
anidados de `test_mcp_context7_search_docs_saved_citation_and_receipt_reuse`
señalados por SIM117. Es una cuestión de estilo del ensayo; no cambia el recorrido
MCP/HTTP/SQLite ni sus garantías de alcance y recibo. La integración Spider y la
retirada de herramientas/dependencias restantes siguen como trabajo principal.

## DD048 — estilo del transporte opcional y sus ensayos

Después de todas las capacidades principales: resolver los ocho avisos del
[informe Spider](spider-lint.json): orden de imports/exports, anotación de los
diccionarios de constantes de clase como ClassVar y context managers anidados
del ensayo MCP. No se modifican esos diccionarios durante la ejecución.
No reabrir la integración por estos avisos. Las herramientas/índices restantes,
presupuestos agregados y validación de proveedores reales siguen como trabajo
principal, no como detalles diferidos.

## DD049 — estilo de la consolidación de código

Después de todas las capacidades principales: revisar los 10 avisos del
[informe de código](code-operations-lint.json): orden de imports/exports, aliases
de fixtures pytest y concatenación implícita de la receta de comprobación;
también avisos previos de las rutas Git sobre subprocesos y excepciones.
Los aliases registran fixtures por nombre y deben conservar esa semántica.
No reabrir la migración por estilo; el cierre global de herramientas y los
checkpoint/capacidad operativos del historial siguen como tareas principales.


Seguimiento deDD048 (adaptadores nativos): los avisos I001/RUF022 del export web
persisten en[native-adapters-lint.json](native-adapters-lint.json). No se reabre
la migración por ellos. El fallo54/55, la recuperación de Chroma sin fuente original
y la política web robots/frecuencia son tareas principales de sus bloques.

| DD-050 | Un aviso Ruff I001 por orden de imports en el nuevo test de política web; no impide la captura ni su verificación. | `backend/tests/research/test_web_policy.py`, evidencia `web-policy-lint.json` | Pulido después de todas las tareas principales. Spider y retirada web siguen como tareas principales, no detalles. |

| DD-051 | Cuatro avisos Ruff de estilo/tipado en composición HTTP, adaptador Spider y sus tests (I001, RUF012, SIM117). | `web-retirement-lint.json` | Pulido después de todas las capacidades principales; no repetir la retirada web por ellos. Los avisos de exports web de DD048 desaparecen al retirar ese paquete. |

| DD-052 | Tres avisos Ruff de orden de imports/context managers en el registro de rutas y las pruebas de contexto de tareas (I001, SIM117). | `task-workspace-lint.json` | Después de todas las capacidades principales. No reabrir las lecturas/notas por estilo; el historial completo, la migración de datos y la retirada de wrappers siguen como tareas principales. |

| DD-053 | Un import `pytest` sin usar, ya presente en el test de comunicación heredado que recibe el diálogo trasladado (F401). | `task-retirement-lint.json` | Ya no aplica: el archivo completo se retiró en el corte de herramientas de comunicación, sin una tarea de pulido separada. Los fallos de migración/inversa y conocimiento siguen en sus bloques principales. |

| DD-054 | Trece avisos Ruff en archivos del recorrido de comunicación: orden de imports, import histórico sin usar, import de fixture compartido con nombre de parámetro y context managers combinables (I001/F401/F811/SIM117). El corte posterior vuelve a observar nueve en sus archivos tocados; ese alcance menor no prueba que los otros desaparecieran. | `agent-messages-lint.json`, `communication-retirement-lint.json` | Después de todas las capacidades principales. No reabrir el recorrido verificado por estilo; retirar servicios/rutas restantes, evaluar comunicación humana y completar migraciones/restore siguen siendo trabajo principal. |

Seguimiento de proyecto: `project-retirement-lint.json` observa tres avisos
I001/SIM117 en archivos compartidos con DD052/DD054. Se conservan para la pasada
final; el alcance menor no demuestra que desaparecieran los demás. DD042 incluye
el singular/plural de `ProposedWork` y DD002 el aviso de bundle grande de este
build. No volver a probar toda la planificación por estos detalles de presentación.

En el mismo corte, `git diff --check` señala una línea vacía al final de
`test_repository_manager.py` tras retirar su test obsoleto. Queda junto con el
estilo; no afecta al contrato verificado ni justifica reconstruir el paquete.


## DD055 — estilo tras retirar herramientas de conocimiento

Después de todas las capacidades principales: los dos avisos I001 de
`knowledge-retirement-lint.json` y la línea vacía al final del test de revisión
tras retirar un caso de wrapper. No reabrir el recorrido por estos detalles.
Los dos fallos de migración/inversa reproducidos y la recuperación de informes
con bytes sólo en archivos son trabajo principal de datos/restore, no DD055.

## DD056 — estilo tras retirar bibliotecas antiguas

Después de todas las capacidades principales: tres imports sin uso en
`backend/tests/flows/conftest.py` (F401) y el orden de `__all__` en
`backend/tools/base/__init__.py` (RUF022), registrados en
`legacy-dependencies-lint.json`. El marcador pytest `integration` sin registrar
también queda para la pasada final. Los siete fallos de flows reproducidos y
la ejecución pendiente de los tres casos de pod son trabajo principal de
servicios/operación, no detalles de estilo.

## DD057 — orden de imports tras retirar la API interna

El aviso I001 de `backend/api/main.py` queda para después de todas las capacidades
principales; véase `internal-retirement-lint.json`. La diferencia 404/405 de rutas
inexistentes con el fallback GET de la SPA no afecta la retirada: ambas rechazan
la operación. No abrir un rediseño del router para uniformarla en este corte.
Los fallos de migración y la aceptación de imágenes siguen siendo trabajo principal.

## DD058 — estilo en consumidores de comunicación

Los 16 avisos de `communication-services-lint.json` en consumidores tocados
(S110/BLE001/UP017/I001/F811/SIM117/RUF059/S102) quedan para la pasada posterior
a todas las capacidades principales. `git diff --check` también señala una línea
vacía al final de `test_project_owner_cutover.py` tras retirar un caso obsoleto.
No repetir las pruebas de comunicación por ese espacio en blanco. Los cinco
fallos reproducidos de helpers/routers de flows siguen como trabajo principal.

## DD059 — estilo tras retirar flows y helpers

Los 17 avisos de `flow-retirement-lint.json` (I001, F401, S110, BLE001, RUF059
y S102), incluidos imports de tests ahora sin uso, quedan para después de todas
las capacidades principales. También las líneas vacías finales de
`test_main_project_flow.py`, `test_project_producer_retirement.py` y
`test_result_acceptance.py`. No repetir esta verificación por esos espacios.
Los tres fallos de fixtures de migración y el fixture compartido API que parchea
`cleanup_service.schedule_periodic_cleanup` eliminado son trabajo principal de
migraciones/integración, no detalles de estilo ni aceptación lograda.

## DD060 — estilo tras retirar autonomía y plantillas antiguas

Los 15 avisos de `autonomy-retirement-lint.json` (imports I001/F401, variables
de fixture RUF059 y el uso controlado de exec S102) quedan para después de todas
las capacidades principales. También la línea vacía final de
`backend/runtime/legacy_handoff.py`. No reconstruir el paquete ni repetir los
recorridos por este pulido. Los fallos de fixtures de migración, el fixture API
histórico y la configuración/operación integral siguen como trabajo principal.

## DD061 — detalles tras empaquetar web/API y probar persistencia

Nueve avisos de lint en health, el test API histórico y el nuevo smoke quedan
para después de todas las capacidades principales: S110/BLE001, UP017, I001/F401
y PLW1510. También quedan para esa fase el aviso de Vite por bundle superior a
500kB y la deprecación de Starlette TestClient/httpx. No repetir el recorrido del
contenedor sólo por estos detalles. La instalación de herramientas de build aún
resuelve rangos/repositorios: no se afirma reproducibilidad byte a byte.

La actualización de dependencias frontend, Forgejo, el aprovisionamiento/admisión
nativa y los fallos de migración/restore son trabajo principal, no pulido diferido.
El fixture API histórico de DD059/DD060 ya se recuperó; 91 casos API/configuración
y tres de salud pasan en el alcance de este corte.

## DD062 — detalles tras el ensayo Forgejo

Un aviso I001 de orden de imports en `evals/operation/forgejo_upgrade.py` queda
para después de todas las capacidades principales. Doctor completó28checks y
salió0, pero registró la opción antigua EMAIL_DOMAIN_WHITELIST; no se afirma una
salida libre de avisos. Revisar su migración a EMAIL_DOMAIN_ALLOWLIST conservando
valores efectivos en la pasada de configuración fina. No repetir backup/upgrade/
restore por esos detalles. La caducidad/renovación de TLS se documenta como acción
operativa explícita; no hay generación ni rotación automática al arrancar.

## DD063 — estilo tras retirar sandbox y launcher

Tres avisos en los archivos afectados: TRY004 por el ValueError de configuración
JSON y dos F401 heredados del conftest de herramientas; queda también una línea
vacía final en ese conftest. Resolver durante la pasada final de estilo, sin
repetir pruebas de procesos o builds por estos detalles. Los fallos iniciales
de la aserción de fixture fueron corregidos y comprobados de nuevo; el artefacto con caché
antigua fue descartado y reconstruido desde sdist. No son pendientes de estilo.

## DD064 — detalles tras preparar el host nativo

Nueve avisos de lint en CLI, preparación del host y fixtures/runner quedan para
después de todas las capacidades principales: I001, TRY004, RUF059 y F401.
También quedan el aviso benigno de Codex `--version` al usar un HOME inexistente
para evitar leer la cuenta y la deprecación heredada de TestClient/httpx. No
reconstruir ni repetir admisiones reales sólo por este pulido.

El fallo de descriptores al cerrar comandos y la entrega de EOF eran bloqueos
funcionales; se corrigieron y comprobaron con ambos loops. La admisión desde
contenedor, recursos portables y restauración real siguen como trabajo principal.

## DD065 — detalles tras el recorrido del contenedor nativo

El runner conserva un aviso PLW1510 por el retorno inspeccionado explícitamente
de subprocess.run; host_smoke conserva el F401 ya anotado en DD064. Resolver al
final de todas las capacidades principales. No repetir el build, los recorridos
ni las admisiones por esos avisos. El problema de /proc y la identidad del
observador eran requisitos funcionales; están resueltos en la configuración
comprobada. Reboot/re-enrollment, restauración real y otros entornos continúan
como límites principales, no como detalles de estilo.

## DD066 — detalles tras actualizar el frontend

El lint incorporado informa12incidencias idénticas antes y después de la
migración, conservadas en `frontend-dependencies-lint.json`: cinco `any`, dos
bloques vacíos, dos regex con controles, dos imports/variables sin uso y un
`prefer-const`. Revisar la intención de las regex; no eliminarlas para silenciar
el linter. Conservar el chequeo estricto y resolver al final de todas las
capacidades principales.

También quedan el bundle mayor de500kB, las opciones `esbuild` de fixtures SSR
que Vite8 convierte por compatibilidad, y el artefacto de build TypeScript
versionado. No rehacer builds o recorridos sólo por pulido de estos detalles.

En `tests/access.browser.mjs` los estados normales y las aserciones de foco en
colores forzados pasan. Axe informa contraste insuficiente en este último estado
usando colores de autor, mientras la captura muestra texto negro; se conserva
la discrepancia y el exit1 sin desactivar reglas. Comprobar emulación/cálculo y
accesibilidad real en la pasada final. Evidencia completa en
`docs/design/audits/frontend-dependencies/access/`.

Los16avisos del audit, correspondientes a3problemas únicos en dependencias,
se registran aparte como **aceptación de seguridad pendiente**, no como cosmética.
No usar versiones incompatibles ni `audit fix --force` para ocultarlos. Tampoco
quedan aceptadas las12páginas, otros navegadores o la nueva imagen de despliegue.

## DD067 — detalles tras retirar configuración sin consumidores

Cuatro avisos de lint en el alcance: tres imports sin uso heredados de la
fixture de flows y uno de orden de imports en el runner de catálogo. Véase
`configuration-retirement-lint.json`. Conservar para después de todas las
capacidades principales; no repetir catálogos, HTTP o builds por este estilo.

Se conserva la deprecación de TestClient/httpx y el aviso de scope asyncio en
la ejecución instalada con configuración pytest aislada. Dos tests de manifiestos
requieren el checkout y no deben presentarse como comprobaciones del wheel.
Los fallos por credenciales bajo el cwd del ensayo y la carga accidental de
pytest.ini_options del checkout se diagnosticaron y corrigieron en el harness,
sin cambiar la frontera de credenciales. La ejecución final comprueba el origen
de todos los imports backend.

Migrar los demás runners al perfil nativo y comprobar sus escenarios es trabajo
principal aún abierto, no pulido. Lo mismo vale para restauración y evaluaciones
integrales. Retirar diez funciones de tests del escritor global no repara fallos
de esas capacidades ni demuestra una suite global verde.

## DD068 — estilo después de migrar seis evaluaciones nativas

Cinco avisos: dos de orden de imports y tres variables locales sin uso en los
runners migrados. Se conservan en `native-evaluation-runners-lint.json` para
después de todas las capacidades principales. El aviso del chequeo de versión
de Codex sobre `/nonexistent` sigue siendo el ya registrado para el host.
No repetir turnos por esos detalles ni reconstruir el paquete productivo sin
cambios en sus fuentes.

La confusión entre las 45 herramientas de negocio y las 54 del catálogo nativo
se corrigió como parte del escenario, no se difiere. El fallo original permanece
visible, con verificación de sus artefactos y recuperación HTTP del mismo recibo
sin nueva generación. Siguen siendo trabajo principal los demás runners, la
evaluación humana/científica/global y la aceptación integral de las páginas.

## DD069 — estilo de las evaluaciones de procesos

Cuatro avisos de lint: tres de orden de imports y uno de construcción de dict.
Se conservan en `kernel-evaluation-runners-lint.json` para después de todas las
capacidades principales. Considerar también que el probe de entorno informe
presencia/ausencia sin imprimir valores si detectase una regresión; en el ensayo
actual no se expuso ninguna credencial. No repetir escenarios por estos detalles.

Se resolvieron los problemas que impedían validar el escenario: wrapper pidfd
ausente en Python portable, reutilización de un intento invalidado y observación
prematura de cgroup vacío. Sus recibos fallidos se conservan. El directorio
CODEX_HOME privado forma parte del perfil actual y no equivale a heredar cuenta.



## DD070 — detalles tras migrar Ken e inspección

Cuatro avisos de lint: dos imports sin uso, uno de orden y una llamada breve a
`git init` dentro del runner async. Conservar `remaining-evaluation-runners-lint.json`
para el final de las capacidades principales. No repetir Ken por estos avisos.

Las capturas móviles muestran una cabecera de unos 215 px a 844 px de alto,
con los controles visibles y sin recorte. Revisar su densidad y la de los
metadatos durante el pulido final, sin atribuir una aceptación completa de páginas
al recorrido de lectura. El hash de captura comprueba el índice compilado; ampliar
la huella a todos los assets pertenece al endurecimiento posterior del evaluador.

Se corrigieron los bloqueos funcionales del evaluador: contexto vigente después
de cambiar la tarea sintética, lectura que incluya el docstring y valor, y nombre
accesible actual del selector. Se conserva la preparación fallida con 512 MiB:
no se capturó su código/counters, por lo que OOM es una hipótesis, no un hecho.
Con los 2 GiB configurados para el host, Ken termina y registra un pico cercano
a 1,39 GB sin OOM. No se aumenta ningún límite de la instalación del operador.


## DD071 — estilo tras verificar la cadena de migraciones

Veintidós avisos de lint en los archivos afectados: imports sin uso/de orden y
un retorno explícito de `None` y un `subprocess.run` que comprueba el código
manual sin `check` explícito.
Se conservan en `migration-chain-lint.json`. Hay además una línea en blanco de
más al final de `test_development_migration.py` y el aviso deprecado heredado de
Starlette/httpx en tests. Resolver después de todas las capacidades principales;
no reconstruir el paquete ni repetir los39 ensayos físicos por estos detalles.

Los preparadores históricos incoherentes sí impedían comprobar migraciones y
se corrigieron: prefijos completos y registros SQL correspondientes a su época.
Las inversas con historial siguen rechazándose; no se rebajaron sus guardas.
Restauración completa, datos reales e inversas/recuperación posteriores siguen
siendo trabajo principal, no detalles diferidos.


## DD072 — estilo tras la copia y restauración de datos

Quince avisos de lint conservados en `installation-backup-lint.json`: orden de
imports, dos imports sin uso, estilo de un contexto/comprensión, tipo de excepción
y la captura de `BaseException` que preserva el error del consumidor fuera del
bloque de autoridad. Revisar su intención antes de aplicar cambios automáticos.
Se mantiene también el aviso heredado de Starlette/httpx. El pulido del módulo
compartido de rutas administrativas Git puede esperar a todas las capacidades
principales; el comportamiento de paths, límites y conservación sí está probado.

Se corrigieron los fallos funcionales observados: el error de copia no se presenta
como corrupción de autoridad; los enlaces Git relativos se resuelven desde la
ubicación original; los destinos con alias no pueden entrar en los originales.
La reinscripción, conciliación, reboot y migración de datos reales son trabajo
principal pendiente, no detalles diferidos.

## DD073 — pulido tras reinscripción y aviso de instalación

Se conservan19 avisos Python en `restored-enrollment-lint.json`: orden de imports,
fixtures importadas que Ruff considera sin uso/redefinidas y `check` implícito en
el subprocess de prueba. Son convenciones a resolver después de las capacidades
principales; las fixtures se ejecutan y el retorno del hijo se comprueba.
Continúan el aviso heredado Starlette/httpx y el aviso de tamaño del bundle.
ESLint conserva un aviso heredado `no-control-regex` en la expresión que rechaza
caracteres de control de las rutas; no se elimina esa protección por estilo.
Un explorador de archivos locales de solicitudes anteriores y el ajuste fino del
texto/espaciado del aviso pueden esperar; ya existe descarga y conservación exacta.

El reboot real, la aceptación de un turno de modelo en el host restaurado, datos
históricos y el soporte necesario para sus tamaños/layouts son trabajo principal.
No se presentan como pequeños detalles resueltos por este tramo.

## DD074 — pulido del ensayo restaurado y extensión del informe

Tres avisos de lint en `restored-host-evaluation-lint.json`: orden de imports y
un import sin uso ya presente en `host_smoke.py`. No requieren reconstruir el
runtime ni repetir el turno de modelo. El informe real separa correctamente
inspección/ejecución, cita evidencia y usa el ejemplo137fichas+63fichas; aun así,
su lenguaje metodológico resulta largo para una suma. Ajustar esa proporcionalidad
en la pasada de comunicación/prompts, con evaluación apropiada, sin convertir
este hallazgo en otra ejecución de la misma prueba ya aprobada.

## DD075 — pulido tras recuperación de autoridad y ensayo de reboot

Se conservan45 avisos en `reboot-recovery-lint.json`: orden de imports, fixtures
reutilizadas, contextos/comprensiones, captura deliberada de excepciones y modo
del archivo auxiliar. El initramfs asigna explícitamente el modo ejecutable a su
entrada; el auxiliar Python no se ejecuta directamente. Revisar estas convenciones
al terminar las capacidades principales, sin repetir el ensayo por estilo.

Continúan los avisos de Starlette/httpx y del diagnóstico `codex --version` sobre
su HOME deliberadamente inexistente. El aprovisionador de VM está limitado a
Linux/KVM, UID1000 y Python3.12 portable; generalizar esa herramienta de evaluación
puede esperar. Datos reales, importadores, soporte de metadatos necesario y
aceptación integral siguen siendo trabajo principal, no detalles diferidos.


## DD076 — pulido tras importación histórica

Se conservan48 avisos en `legacy-import-lint.json`: orden de imports, imports
sin uso, fixtures reutilizadas, contextos combinables, tipo de excepción y
`check` implícito en subprocess de pruebas cuyo retorno ya se comprueba.
Resolver después de todas las capacidades principales. Persisten los avisos
heredados Starlette/httpx y HOME inexistente al inspeccionar la versión de Codex.

La compatibilidad de versiones de Chroma reales, inventario/migración de los
datos del propietario e inversas/recuperación posteriores siguen siendo tareas
principales. No se convierten en detalles diferidos por pasar un ensayo sintético.


## DD077 — pulido tras recuperación y pruebas históricas

Treinta avisos de lint en `recovery-policy-lint.json`: orden/imports sin uso,
fixtures reutilizadas y tipo de excepción. Hay dos líneas en blanco de más al
final de `test_check_state.py` y `test_code_review_records.py`. Conservarlas hasta
la pasada final de estilo; los bytes actuales coinciden con el paquete probado.
Continúa el aviso heredado Starlette/httpx. No repetir160casos por este pulido.

Los fallos de preparación histórica sí impedían comprobar las inversas: diez
casos ahora usan esquemas y registros de su época, con relaciones/bytes exactos,
sin que una versión futura o una API moderna enmascare el comportamiento.
Datos reales, aceptación de recuperación más amplia e integración global siguen
siendo trabajo principal. El soporte de downgrade genérico no se promete.

## DD078 — pulido tras historial y presupuesto

Un aviso RUF059 en el test nuevo de presupuesto: variable `run` sin uso.
Resolver con el resto del estilo. Se conserva el aviso de tamaño del bundle.
En la interfaz, revisar singular/plural de contadores, repetición de explicaciones
y altura del presupuesto en móvil; las lecturas, paginación y controles funcionan.
No repetir los ensayos por estos detalles.

Eventos/reconexión/retención, recuperación más amplia, datos reales y aceptación
integral siguen siendo tareas principales. No se convierten en pulido diferido.

## DD079 — interfaz de Actividad y pulido del bloque de eventos

La recuperación de eventos está comprobada. El panel de Actividad aún conserva
estilos anteriores: integrarlo al rediseño durante la aceptación de interfaz.
En móvil, el panel abierto tapa el desplegable de proyectos; cerrar el panel
permite cambiar y comprobar aislamiento. Corregir la superposición en esa etapa.
Axe detectó contraste en tres capturas y región desplazable sin foco en dos;
revisar también después de estabilizar animaciones. Son pendientes de aceptación
de interfaz, no una aprobación de accesibilidad ni una renuncia al requisito.

`durable-events-lint.json` conserva3 avisos: imports, captura amplia deliberada
y `check` implícito de subprocess cuyo código se comprueba. Mantener el aviso
de tamaño del bundle y Starlette/httpx para la pasada final. No repetir los
ensayos de488 eventos por ese estilo. Revisar también etiquetas técnicas,
localización y contadores de actividad en la aceptación del panel.

## DD080 — pasada global de estilo tras el retiro del motor anterior

Sobre `9fb873c`, Ruff informa347 hallazgos y ESLint9 errores. Se conservan las
ubicaciones/reglas en [current-global-lint.json](current-global-lint.json).
Predominan imports, fixtures importadas con nombres de parámetros, variables
sin uso, tipos y forma explícita de excepciones/subprocess. ESLint incluye
regex de controles, `any` y declaraciones sin uso. Revisar estas guardas antes
de modificar una expresión para satisfacer el linter; no debilitar contratos.

Resolver durante la pasada final de detalles, después de todas las capacidades
principales. El lint no está aprobado. Estos hallazgos por sí solos no prueban
un fallo funcional; la suite global se examina por separado y sus fallos no se
reclasifican automáticamente como detalles. No repetir la suite global completa
por cambios puramente de formato/imports que no afecten comportamiento.


## DD081 — contratos y preparación de pruebas tras la corrida global

La [clasificación completa](current-global-review.md) conserva30 casos fallidos
y1 error de fixture que el arreglo del backup no resuelve. Antes de aceptar la
suite común:

- Alinear el contrato administrativo de estados y24 pruebas heredadas; conservar
  las guardas independientes de aceptación/control nativo.
- Preparar esquemas históricos reales en5 casos de migración: prefijos55/56/57/58,
  sin quitar un marcador bajo versiones futuras ni añadir una inversa59 ficticia.
- Exponer `schema_target` al fixture del test de terminal y probar su recorrido.
- Dar un presupuesto acotado suficiente al test compuesto de dos checks nativos:
  pasó en23,614s bajo60s, excediendo el límite común20s. No tocar plazos de producto.

No llamar verde a la suite por pasar los ensayos dirigidos. Estos pendientes
siguen siendo controles obligatorios de la entrega, programados después de las
capacidades principales. Si al resolverlos aparece un fallo funcional, tratarlo
como tal. El backup sí tenía un defecto funcional y se corrigió en este tramo.
Los12 avisos de lint del arreglo están en `backup-sidecar-results.json`; aplicar
el pulido junto con DD080 sin repetir automáticamente una suite de24min.

## DD082 — estilo del evaluador de contexto

El bloque conserva12 avisos:8 de orden de imports,1 import sin uso y3 de
concatenación implícita de texto en una colección del exportador. Las cadenas
exportadas se inspeccionaron; ajustar su forma después de las capacidades
principales. [Ubicaciones](context-alignment-lint.json). No repetir modelos ni
la suite global por este pulido.

Las preguntas sólo en prosa y la continuidad del pedido entre admisiones son
pendientes funcionales en [la evaluación](context-alignment-review.md), no DD082.

## DD083 · Estilo tras revisar dependencias y seguridad

Ruff conserva3 avisos (orden de imports y alias de regex/UTC) en el
auditor; ESLint conserva9 errores en el frontend. Pruebas dirigidas, build, árbol
y comportamiento central comprobados. Retomar después de todas las capacidades
principales. Ken/ONNX, Chroma, licencias y activación de la automatización **no**
se relegan aquí: siguen como trabajo principal en la
[revisión de seguridad](dependency-security-review.md).

## DD084 · Estilo tras continuidad y preguntas respondibles

Diez avisos Ruff en los archivos inspeccionados:8 de imports,1 de reexportación
y1 variable sin uso. El comportamiento central y el paquete se comprobaron.
Retomar después de todas las capacidades principales. Las60 revisiones estáticas
de prompts desactualizadas y la evaluación humana siguen en el trabajo principal,
no se reclasifican como pulido. [Evidencia](communication-flow-review.md).

## DD085 · Estilo tras recuperación de servicio activo

Seis avisos Ruff en los archivos inspeccionados:4 de imports y2 de variables sin
uso. Resolver después de todas las capacidades principales; no repetir modelos
ni la suite global por ese pulido. [Ubicaciones](service-crash-lint.json).
La VM con proceso activo y demás recuperación siguen como trabajo principal.


## DD086 · Estilo tras VM activa y jobs restaurados

Dieciocho avisos Ruff: imports, registros de fixtures que requieren alias,
context managers, forma de dict, shebang del helper invocado mediante Python y
captura deliberada de fallos del init. El ensayo real comprueba el recorrido
central; retomar ese pulido después de todas las capacidades principales.
[Ubicaciones](active-reboot-lint.json). Los3 fallos de preparación histórica de
reboot ya están documentados en DD081 y en la suite global previa; no constituyen
una suite actual verde ni se solucionan ahora por cambios cosméticos.


## DD087 · Imports del evaluador de perfiles

Tres avisos Ruff I001: dos en `evals/context_alignment/run.py` y uno en
`evals/context_alignment/worker.py`. Reordenar imports después de todas las capacidades principales;
no repetir los8turnos por estilo. Los fallos de entrega por presupuesto y el
salto desde promedios a individuos **no** son pulido: siguen como siguiente
trabajo funcional. [Resultados y ubicaciones](profile-communication-results.json).

## DD088 — Estilo del bloque de presupuesto y entrega

Quedan once avisos Ruff en los archivos revisados: siete I001, dos PLC0414,
un F841 y un RUF059. Incluyen imports/reexports de fixtures y variables sin uso;
no se corrigen antes de terminar las capacidades principales. Ubicaciones en
[delivery-budget-lint.json](delivery-budget-lint.json). No volver a ejecutar los
tres turnos reales por estilo. El fallo de entrega de planificación bajo su
límite anterior es funcional y sigue pendiente, separado de estos detalles.

## DD089 — Estilo del exportador histórico

Once avisos Ruff en el exportador y sus evaluadores; conservar sus ubicaciones en
[chroma-isolation-lint.json](chroma-isolation-lint.json) y corregirlos después de
todas las capacidades principales. El fallo histórico del fixture de inversión
del esquema sigue registrado en la suite global. Los límites agregados de recursos,
Ken/ONNX, licencias y datos históricos pendientes pertenecen a trabajo funcional,
no a esta lista de estilo. No repetir ensayos reales sólo por ordenar imports.


## DD090 — Estilo del auditor de licencias

Cuatro avisos Ruff: dos I001, un FURB167 y un UP017. Posponer hasta terminar
las capacidades principales. [Ubicaciones](license-lint.json). La advertencia
Starlette/httpx del verificador ASGI es preexistente; no actualizar dependencias
ni repetir recorridos reales por ella.

## DD091 — Dos textos de licencia ausentes de los paquetes npm

Vite genera93 entradas, pero `rehype-katex7.0.1` y `remark-math6.0.0` traen sólo
la declaración MIT, sin archivo de licencia. Incorporar los textos oficiales
correspondientes y verificar su entrega antes de distribuir. Es un pendiente
concreto de avisos, no una declaración de que los paquetes carecen de licencia.
La metadata npm señala el repositorio `remarkjs/remark-math` y los commits
`88a9497e1ede93b958237c85edbf5651faeca7af` y
`d5d0660b150810a535bbb07eac6cc96a4510aa24`, respectivamente. Revalidar esos vínculos
y el texto al resolverlo. No crear ahora otro sistema general de licencias.


## DD092 — Estilo del margen de entrega

Nueve avisos Ruff en los archivos del bloque. Conservar ubicaciones en
[planning-delivery-lint.json](planning-delivery-lint.json) y resolver después de
las capacidades principales. No repetir el ensayo real por estilo. La entrega
fallida a137720/120000tokens es un problema funcional del contrato de entrega,
no un detalle que pueda ocultarse en esta lista.


## DD093 — Estilo del bloque de entrega atómica

Ocho avisos Ruff en los archivos examinados (I001, PLC0414 y RUF059), incluidas
fixtures heredadas; ubicaciones en [atomic-planning-lint.json](atomic-planning-lint.json).
Resolver después de todas las capacidades principales, sin repetir inferencia real
por estilo. La advertencia de tamaño del bundle web sigue presente. El límite
configurado de bytes de explicación era funcional y sí quedó protegido en este
bloque; no se difiere como detalle.
