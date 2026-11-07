# D13 — entrega de eventos y recuperación de instalación

Preparado durante la validación D10–D12; **bloque todavía no iniciado**.
Registrar hora/base reales al comenzar. No repetir cambios ya implementados.

## Contrato

Un cliente lento no retrasa clientes sanos ni acumula una cola ilimitada de
eventos. Reconectar recupera desde identidad durable, y un cursor que perdió
historia obliga a resincronizar explícitamente. Restaurar en otra ruta conserva
hashes, relaciones y lectura de datos/artefactos sin heredar permisos de ejecución.

## Evidencia actual por contrastar

- `ConnectionManager` tiene un emisor y una página por cliente, deadline de envío
  y cierre/drenaje propios. `EventHistory` pagina por ID durable y expresa gaps.
  Pruebas: `test_durable_events.py`, `test_event_stream.py` y
  `test_websocket_lifecycle.py`.
- Backup/restauración incluye SQLite, uploads, repositorios y linked worktrees;
  protege fuentes cambiantes y destinos existentes. Las lecturas del dueño tras
  mover la instalación conservan alcance. Pruebas: `test_installation_backup.py`.
- La inscripción restaurada crea autoridad nueva y conserva intención previa
  sin replay. D08 añadió recuperación del archivo de retención y rechazo de una
  decisión copiada que pretendiera borrar en el host anterior. Pruebas:
  `test_restored_enrollment.py` y `test_workspace_retention.py`.

## Criterio de salida

- [ ] Leer los contratos y contrastar cada efecto con sus pruebas actuales;
  corregir cualquier brecha funcional demostrada, conservando datos ambiguos.
- [ ] Comprobar backpressure, cursor/gaps y restauración a otra raíz en la
  instalación actual. Usar el artefacto existente si sus fuentes coinciden;
  no recompilar ni repetir inferencia por cambios documentales.
- [ ] Registrar matriz, límites y resultados, actualizar tablero y commit.
  La aceptación de datos históricos reales, UI completa y desastre general
  sigue en sus entregas: un ensayo sintético no demuestra esa aceptación.

La lista y los tiempos medidos se publican al cambiar de bloque. Los detalles
secundarios permanecen al final de todas las capacidades principales.
