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
| DD-003 | El esquema 43 instala publicación; faltan las inversas 43/44/45/46/47/48/49/50/51 y adaptar fixtures que revierten directamente40/41/42. Fallo comprobado: `test_code_acceptance_inverse_preserves_reviews_and_refuses_owner_history`; el guard de esquema posterior rechaza el rollback. No debilitar ese guard. | `backend/db/development_migration.py`, tests de migración/aceptación | Pasada de migraciones/restore antes de aceptación integral; no bloquea la publicación local hacia delante. |
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
