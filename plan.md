# Plan: Corrección de 6 bugs de diseño en backend/flows

## Fix 1: Eliminar doble invocación de CodeReviewFlow

**Problema:** Dos CodeReviewFlow concurrentes por task — uno directo (DevelopmentFlow) y uno via event listener.

**Cambios:**

### `development_flow.py`
- **Línea 276**: Eliminar `update_task_status(self.state.task_id, "review_ready")` de `implement_code`. El status lo pone `CodeReviewFlow.receive_review_request`.

### `code_review_flow.py`
- **Línea 177**: Eliminar `update_task_status(self.state.task_id, "review_ready")` de `notify_developer_rework`. El loop interno via `return "review_requested"` ya maneja la re-revisión sin necesidad de cambiar el status en DB.
- **Línea 178**: Eliminar `self.state.review_status = ReviewStatus.REVIEWING` (ya se establece al inicio de `perform_review`).

### `event_listeners.py`
- **`_handle_task_review_ready` (línea 590-607)**: Agregar guard — consultar `agent_runs` para verificar si ya existe un code_reviewer activo (`status='running'`) para este task. Si existe, skip. Esto protege contra invocaciones manuales externas que sí deben crear un flow.

### `development_flow.py` — doble "done"
- **`finalize_task` (línea 369)**: Eliminar `update_task_status(self.state.task_id, "done")` porque `CodeReviewFlow.finalize_approval` ya lo hace. Solo dejar el `log_flow_event`.

---

## Fix 2: Límite de intentos en loops de brainstorming

**Problema:** Loop infinito brainstorming ↔ task check sin condición de salida.

**Cambios:**

### `state_models.py`
- Agregar a `ProjectState`:
  ```python
  brainstorm_attempts: int = 0
  max_brainstorm_attempts: int = 3
  ```
- Agregar a `BrainstormState`:
  ```python
  rejection_attempts: int = 0
  max_rejection_attempts: int = 3
  ```

### `main_project_flow.py`
- **`trigger_brainstorming`**: Incrementar `self.state.brainstorm_attempts` antes de lanzar el flow. Si `>= max_brainstorm_attempts`, retornar `"brainstorm_exhausted"` en vez de continuar.
- **Nuevo `@listen("brainstorm_exhausted")`** → `handle_brainstorm_exhausted`: Usar Project Lead para notificar al usuario que el proyecto necesita intervención manual. Marcar proyecto como `"needs_intervention"` (nuevo status) o enviar mensaje al usuario y retornar `"done"`.
- **Reset**: Cuando un task se completa exitosamente (`check_pending_after_task`), resetear `brainstorm_attempts = 0` para permitir futuros brainstorms si se atora de nuevo.

### `brainstorming_flow.py`
- **`ask_why_rejected`**: Incrementar `self.state.rejection_attempts`. Si `>= max_rejection_attempts`, no resetear ni loopear — retornar `"brainstorm_complete"` con un log warning.

---

## Fix 3: Reemplazar polling bloqueante por threading.Event

**Problema:** `wait_for_checkin_approval` usa `time.sleep()` en loop de 30min, bypasea gate en timeout.

**Cambios:**

### `development_flow.py`
- **Reescribir `wait_for_checkin_approval`**:
  1. Crear un `threading.Event()`
  2. Registrar un handler temporal en `event_bus` para `"ticket_checkin_approved"` que filtre por `entity_id == self.state.task_id` y haga `event.set()`
  3. Llamar `event.wait(timeout=max_wait_seconds)`
  4. Después del wait, unsubscribe del event bus (cleanup)
  5. Si el evento fue set → proceder (`return "task_assigned"`)
  6. Si timeout → **NO proceder**. Poner task en backlog (`update_task_status("backlog")`), notificar team lead, retornar `"blocked"`
  7. Eliminar toda la lógica de clarification polling — las clarificaciones se manejan via el event system existente (AgentMessageListener + _dispatch_message_to_agent ya enrutan mensajes al developer)

### `event_listeners.py`
- Verificar que `TicketCheckinListener` (importado de `backend/communication/listeners.py`) emite `"ticket_checkin_approved"` con `entity_id=task_id`. Si no, ajustar.

---

## Fix 4: Ejecución concurrente de tasks

**Problema:** Solo un task a la vez, bloqueando todo el proyecto.

**Cambios:**

### `state_models.py`
- Agregar a `ProjectState`:
  ```python
  max_concurrent_tasks: int = 3
  running_task_ids: list[int] = Field(default_factory=list)
  ```

### `main_project_flow.py`
- **Reescribir `_check_pending_tasks`**:
  - Calcular `available_slots = max_concurrent_tasks - len(running_task_ids)`
  - Si `available_slots <= 0`, retornar `"waiting_for_completion"`
  - Tomar hasta `available_slots` tasks de `get_pending_tasks()`, excluyendo los que ya están en `running_task_ids`
  - Retornar `"has_pending_tasks"` con la lista en un atributo no-persisted (o guardar IDs en state)

- **Reescribir `run_development_flow` y `run_research_flow`**:
  - Lanzar cada sub-flow en un daemon thread
  - Agregar el task_id a `self.state.running_task_ids`
  - **NO** esperar a que termine — retornar inmediatamente

- **Nuevo mecanismo de completion**:
  - Cada thread, al terminar su sub-flow, emite un `FlowEvent("sub_flow_completed", entity_id=task_id)` en el event bus
  - Agregar nuevo paso: `@listen("has_pending_tasks")` → `launch_and_wait`:
    1. Lanzar threads para todos los tasks pendientes (hasta el límite)
    2. Crear un `threading.Event` que se activa cuando cualquier sub-flow termina
    3. Registrar handler en event bus para `"sub_flow_completed"`
    4. `event.wait()` — se desbloquea cuando cualquier task termina
    5. Remover task_id de `running_task_ids`
    6. Retornar `"task_completed"` para re-evaluar pending

- **`check_pending_after_task`**: Ya no incrementar `completed_tasks` manualmente — consultar DB para el conteo real.

### `helpers.py`
- Agregar `get_completed_task_count(project_id: int) -> int` que consulta la DB.

---

## Fix 5: Manejo de errores — @listen("error") + try/except

**Problema:** Flows mueren silenciosamente sin cleanup.

**Cambios:**

### Cada flow (main_project_flow.py, development_flow.py, code_review_flow.py, research_flow.py, brainstorming_flow.py):
- **Agregar `@listen("error")` handler** con patrón común:
  ```python
  @listen("error")
  def handle_error(self):
      logger.error("%Flow: error state reached (task_id=%s)", self.state.task_id)
      if hasattr(self.state, 'task_id') and self.state.task_id:
          update_task_status(self.state.task_id, "failed")
      if hasattr(self.state, 'agent_run_id') and self.state.agent_run_id:
          # complete run as failed
          ...
      log_flow_event(self.state.project_id, "flow_error", ...)
      notify_team_lead(self.state.project_id, "system", "Flow error: ...")
      return "done"
  ```

### Pasos críticos con crew.kickoff():
- Envolver en try/except en los pasos donde una falla debe marcar el run como failed:
  - `DevelopmentFlow.implement_code`
  - `CodeReviewFlow.perform_review`
  - `ResearchFlow.investigate`
  - `ResearchFlow.request_peer_review`
- Patrón:
  ```python
  try:
      result = crew.kickoff()
  except Exception as exc:
      logger.exception("Crew execution failed for task %d", self.state.task_id)
      if run_id:
          agent.complete_agent_run(run_id, status="failed", error_class=type(exc).__name__)
      log_flow_event(...)
      return "error"
  ```

### `helpers.py`
- Agregar `update_task_status_safe(task_id, status)` que no falla si task doesn't exist (wrap en try/except con logging).

---

## Fix 6: Stagnation — análisis y desbloqueo en vez de brainstorming

**Problema:** Crear más tasks no desbloquea los tasks stuck.

**Cambios:**

### `helpers.py`
- Agregar `get_stuck_tasks(project_id: int, threshold_minutes: int = 30) -> list[dict]`:
  ```sql
  SELECT * FROM tasks
  WHERE project_id = ?
    AND status IN ('in_progress', 'rejected')
    AND updated_at <= datetime('now', '-N minutes')
  ORDER BY created_at ASC
  ```

### `main_project_flow.py`
- **Reemplazar `handle_stagnation`**: En vez de ir a `"not_complete"` (que triggerea brainstorming), ir a `"stagnation_analysis"`.
- **Nuevo `@listen("stagnation_analysis")` → `analyze_stagnation`**:
  1. Obtener stuck tasks con `get_stuck_tasks()`
  2. Para cada stuck task: Team Lead analiza la causa y toma acción usando `handle_escalation`
  3. Después de intervenir en todos los stuck tasks, verificar si hay pending tasks → `"structure_created"` (re-check normal)
  4. Esto usa la lógica existente de `tl_tasks.handle_escalation` que ya tiene 6 posibles acciones: clarify, guide, simplify, split, reassign, escalate to project lead

### `event_listeners.py`
- **`_handle_stagnation`**: Cambiar de lanzar `BrainstormingCoordinator` a emitir un `FlowEvent("stagnation_detected")` que el `MainProjectFlow` ya escucha. Agregar data con los stuck task IDs para que el handler pueda actuar directamente.

---

## Orden de implementación

1. **Fix 5** (error handling) — fundacional, los otros fixes lo usan
2. **Fix 1** (doble CodeReviewFlow) — independiente, crítico
3. **Fix 2** (límite brainstorming) — independiente, simple
4. **Fix 3** (polling → event) — requiere verificar TicketCheckinListener
5. **Fix 6** (stagnation) — requiere Fix 5
6. **Fix 4** (concurrencia) — el más complejo, requiere Fix 1 y Fix 5
