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
| DD-003 | El esquema 43 instala publicación; faltan las inversas 43/44/45 y adaptar fixtures que revierten directamente el 42. Fallo comprobado: `test_code_acceptance_inverse_preserves_reviews_and_refuses_owner_history`; el guard de esquema posterior rechaza el rollback. No debilitar ese guard. | `backend/db/development_migration.py`, tests de migración/aceptación | Pasada de migraciones/restore antes de aceptación integral; no bloquea la publicación local hacia delante. |
| DD-004 | Mostrar reintento de arranque cuando una publicación queda en cola por capacidad y presentar el host sin etiqueta de modelo. | `CodePublicationRequest.tsx`, `TaskRunWorkspace` | Pasada de controles/estados de Tareas; conservar recibo original. |
| DD-005 | Si una observación se interrumpe antes de guardar su recibo, el mismo comando no reactiva el observador anterior; hace falta consultar el intento actual y preparar explícitamente otra observación después de su cierre. También ampliar el caso sin ningún comando admitido. | `PublicationRecovery.begin`, `publication_closure.py`, controles de recuperación | Pasada de recuperación/crashes; mantener la prohibición de repetir la escritura original. |
| DD-006 | La admisión remota exige prerrequisito `accepted`; un resultado positivo preservado tras retirada necesita adopción explícita con evidencia fresca antes de la siguiente acción. No reutilizar el lease cerrado ni repetir el efecto. | `RemotePublications.admit_once` | Pasada de recuperación remota después del transporte; conservar dentro del alcance completo. |
