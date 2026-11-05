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
| DD-003 | El esquema 43 instala publicación; faltan las inversas 43/44/45/46/47 y adaptar fixtures que revierten directamente el 42. Fallo comprobado: `test_code_acceptance_inverse_preserves_reviews_and_refuses_owner_history`; el guard de esquema posterior rechaza el rollback. No debilitar ese guard. | `backend/db/development_migration.py`, tests de migración/aceptación | Pasada de migraciones/restore antes de aceptación integral; no bloquea la publicación local hacia delante. |
| DD-004 | Mostrar reintento de arranque cuando una publicación queda en cola por capacidad y presentar el host sin etiqueta de modelo. | `CodePublicationRequest.tsx`, `TaskRunWorkspace` | Pasada de controles/estados de Tareas; conservar recibo original. |
| DD-005 | Si una observación se interrumpe antes de guardar su recibo, el mismo comando no reactiva el observador anterior; hace falta consultar el intento actual y preparar explícitamente otra observación después de su cierre. También ampliar el caso sin ningún comando admitido. | `PublicationRecovery.begin`, `publication_closure.py`, controles de recuperación | Pasada de recuperación/crashes; mantener la prohibición de repetir la escritura original. |
| DD-006 | La admisión remota exige prerrequisito `accepted`; un resultado positivo preservado tras retirada necesita adopción explícita con evidencia fresca antes de la siguiente acción. No reutilizar el lease cerrado ni repetir el efecto. | `RemotePublications.admit_once` | Pasada de recuperación remota después del transporte; conservar dentro del alcance completo. |

| DD-007 | Comando remoto de observación interrumpido antes del recibo, compatibilidad de intentos antiguos sin identidad HTTP y ampliación de prueba de crash del host HTTP. No inferir cierre de un PID vivo ni inventar identidad retrospectiva. | `remote_clients.py`, `remote_recovery.py`, controles de Tareas | Pasada de recuperación/crashes y migración antes de aceptación integral. |

| DD-008 | Paginar historial remoto más allá de100 operaciones y seleccionar cadenas antiguas; hoy el límite es visible y bloquea decisiones nuevas para no inferir ausencia. Pulir también textos secundarios del panel. | `RemoteDestinations.history`, `RemotePublications.tsx` | Pasada integral de historial/UI después de capacidades principales; sin rehacer ahora el transporte. |

| DD-009 | Selector de repositorio en inicio de proyecto con múltiples registros, labels/estado de proyecto y mensaje histórico del agente después de aceptar el plan. Hoy API admite ID explícito y web conserva el inicio original; sin selección única rechaza el arranque. | `projectPlans.ts`, `useProjects.ts`, Header/Projects/Tasks | Rediseño integral de Proyectos/Flujo y pasada de interacción; no rehacer ahora la planificación central. |
| DD-010 | Integración de borrado/archivo/restore con historia nativa de planificación y esquema47; aclarar expansión de planes existentes/anidados antes de ampliar despacho. Conservar receipts y guards; no borrar datos para resolverlo. | `backend/planning/`, migraciones y CRUD de proyecto/tarea | Pasada de lifecycle/migraciones antes de aceptación integral. |
