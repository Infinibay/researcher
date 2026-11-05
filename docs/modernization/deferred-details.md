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
