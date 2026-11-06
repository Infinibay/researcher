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
