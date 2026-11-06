"""Project CRUD and native planning controls; project start never activates legacy agent-loop threads."""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import asdict

from backend.git.source_operations import SourceOperations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.api.exceptions import ProjectNotFound, ProjectRunning
from backend.api.flow_manager import flow_manager
from backend.api.models.project import (
    ProjectCreate,
    ProjectList,
    ProjectProgressResponse,
    ProjectResponse,
    ProjectUpdate,
)
from backend.flows.helpers import (
    create_project,
    load_project_state,
    update_project_status,
)
from backend.tools.base.db import execute_with_retry

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _workspace(request):
    """Compose owner project observations from the actual runtime root and existing store, without constructing or activating a runtime."""
    from backend.api.routes.runs import read_store
    from backend.planning.project_workspace import ProjectWorkspace

    runtime = request.app.state.runtime_service
    return ProjectWorkspace(read_store(request), workspaces=runtime.workspaces if runtime else None, legacy_active=flow_manager.is_project_running)


class RegisterProjectSource(BaseModel):
    """Explicit existing source selection; Git, remote creation, clone and overwrite options are outside this capability."""

    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}$")
    path: str = Field(min_length=1, max_length=4096)


class StopObservedProject(BaseModel):
    """One exact observed project Stop intent; caller identities/grants and arbitrary target lists are forbidden."""

    model_config = ConfigDict(extra="forbid", strict=True)
    task_id: int | None = Field(ge=1)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    scope_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


@router.get("/{project_id}/workspace")
async def project_workspace(project_id: int, request: Request):
    """Observe actual native activity, source policy and original plan/report links; saved status never proves live work or current semantic completion."""
    data = await asyncio.to_thread(_workspace(request).state, project_id)
    return JSONResponse(data, headers={"Cache-Control":"no-store"})


@router.post("/{project_id}/sources")
async def register_project_source(project_id: int, body: RegisterProjectSource, request: Request):
    """Register an existing managed directory without initializing Git, configuring credentials or contacting/remapping a remote."""
    data = await asyncio.to_thread(_workspace(request).register_source, project_id, **body.model_dump())
    return JSONResponse(data, headers={"Cache-Control":"no-store"})


def _project_to_response(project: dict) -> ProjectResponse:
    return ProjectResponse(
        id=project["id"],
        name=project.get("name", ""),
        description=project.get("description"),
        status=project.get("status", "new"),
        created_at=project.get("created_at"),
        updated_at=project.get("updated_at"),
        completed_at=project.get("completed_at"),
        task_counts=project.get("task_counts", {}),
        total_tasks=project.get("total_tasks", 0),
        total_epics=project.get("total_epics", 0),
    )


@router.get("", response_model=ProjectList)
async def list_projects():
    """List all projects with task counts."""

    def _query(conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            "SELECT id FROM projects ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    project_ids = execute_with_retry(_query)
    projects = []
    for row in project_ids:
        state = load_project_state(row["id"])
        if state:
            projects.append(_project_to_response(state))

    return ProjectList(projects=projects, total=len(projects))


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project_endpoint(body: ProjectCreate, request: Request):
    """Create metadata once for the original exact owner request; no repository or native work is started."""
    creation = None
    if body.operation_key is not None:
        creation = await asyncio.to_thread(_workspace(request).create, **body.model_dump())
        project_id = creation['project_id']
    else:
        project_id = create_project(name=body.name, description=body.description)
    state = load_project_state(project_id)
    if not state:
        raise HTTPException(status_code=500, detail="Failed to create project")
    result = _project_to_response(state)
    if creation is not None:
        from backend.api.models.project import ProjectCreationReceipt

        result.creation = ProjectCreationReceipt(**creation)
    return result


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int):
    """Get project details by ID."""
    state = load_project_state(project_id)
    if not state:
        raise ProjectNotFound(project_id)
    return _project_to_response(state)


@router.get("/{project_id}/progress", response_model=ProjectProgressResponse)
async def get_project_progress(project_id: int):
    """Get project progress metrics including task counts, epic/milestone progress."""
    from backend.state.progress import ProgressService

    state = load_project_state(project_id)
    if not state:
        raise ProjectNotFound(project_id)

    metrics = ProgressService.get_project_metrics(project_id)
    return ProjectProgressResponse(**metrics)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: int, body: ProjectUpdate):
    """Update metadata and operational labels; completion requires a separate exact whole-project report decision."""
    state = load_project_state(project_id)
    if not state:
        raise ProjectNotFound(project_id)

    if body.status == "completed":
        from backend.runtime.contracts import RunConflict

        raise RunConflict("Consulta y acepta el informe completo del proyecto antes de cerrarlo.")

    updates = []
    params = []
    if body.name is not None:
        updates.append("name = ?")
        params.append(body.name)
    if body.description is not None:
        updates.append("description = ?")
        params.append(body.description)
    if body.status is not None:
        updates.append("status = ?")
        params.append(body.status)

    if updates:
        params.append(project_id)
        sql = f"UPDATE projects SET {', '.join(updates)} WHERE id = ?"

        def _update(conn: sqlite3.Connection) -> None:
            """Compare the owner's displayed scope under the write lock before applying metadata; a stale editor cannot replace intervening changes."""
            if body.expected_scope_sha256 is not None:
                from backend.knowledge.reviews import digest
                from backend.runtime.contracts import RunConflict

                if not conn.in_transaction:
                    conn.execute('BEGIN IMMEDIATE')
                current = conn.execute('SELECT name,description,original_description FROM projects WHERE id=?', (project_id,)).fetchone()
                if current is None or digest(dict(current)) != body.expected_scope_sha256:
                    raise RunConflict('El alcance cambió desde que abriste el editor. Consulta la versión actual antes de reemplazarlo.')
            conn.execute(sql, params)
            conn.commit()

        execute_with_retry(_update)

    state = load_project_state(project_id)
    return _project_to_response(state)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: int):
    """Delete an explicitly selected unused project; execution history and registered workers must be preserved and reconciled instead."""
    state = load_project_state(project_id)
    if not state:
        raise ProjectNotFound(project_id)

    if flow_manager.is_project_running(project_id):
        raise ProjectRunning(project_id)

    def _delete(conn: sqlite3.Connection) -> None:
        """Hold the admission write lock while checking history and removing only an unused project's metadata; source files are never deleted here."""
        # Admission and history checks share the same write lock as deletion.
        from backend.runtime.contracts import RunConflict

        if not conn.in_transaction:
            conn.execute('BEGIN IMMEDIATE')
        metadata = conn.execute('SELECT metadata_json FROM projects WHERE id=?', (project_id,)).fetchone()
        if (metadata is not None and SourceOperations.has_history(metadata[0])) or any(conn.execute(f'SELECT 1 FROM {table} WHERE project_id=? LIMIT 1', (project_id,)).fetchone() for table in ('runtime_runs','agent_runs','flow_snapshots','agent_events')):
            raise RunConflict('El proyecto conserva historia de ejecución. No se elimina desde este control; conserva sus informes, intentos y fuentes.')
        # Delete in dependency order — explicit deletes for all referencing
        # tables so the delete succeeds even if the DB lacks ON DELETE CASCADE
        # (e.g. tables created before CASCADE was added to the schema).
        p = (project_id,)

        # Tables referencing tasks (must go before tasks)
        conn.execute(
            "DELETE FROM task_dependencies WHERE task_id IN "
            "(SELECT id FROM tasks WHERE project_id = ?)",
            p,
        )
        conn.execute(
            "DELETE FROM task_comments WHERE task_id IN "
            "(SELECT id FROM tasks WHERE project_id = ?)",
            p,
        )

        # Tables referencing findings (must go before findings)
        conn.execute(
            "DELETE FROM finding_deps WHERE finding_id IN "
            "(SELECT id FROM findings WHERE project_id = ?)",
            p,
        )

        # Global agent performance has no project ownership. Preserve it;
        # the former agent_roster table is not part of the current schema.

        # All tables directly referencing projects
        conn.execute("DELETE FROM agent_events WHERE project_id = ?", p)
        conn.execute(
            "DELETE FROM agent_loop_state WHERE project_id = ?",
            p,
        )
        conn.execute("DELETE FROM autonomy_actions WHERE project_id = ?", p)
        conn.execute("DELETE FROM flow_snapshots WHERE project_id = ?", p)
        conn.execute("DELETE FROM clarification_questions WHERE project_id = ?", p)
        conn.execute("DELETE FROM loop_incidents WHERE project_id = ?", p)
        conn.execute("DELETE FROM message_fingerprints WHERE project_id = ?", p)
        conn.execute("DELETE FROM convergence_log WHERE project_id = ?", p)
        conn.execute("DELETE FROM brainstorm_sessions WHERE project_id = ?", p)
        conn.execute("DELETE FROM notices WHERE project_id = ?", p)
        conn.execute("DELETE FROM user_requests WHERE project_id = ?", p)
        conn.execute("DELETE FROM processes WHERE project_id = ?", p)
        conn.execute("DELETE FROM validation_results WHERE project_id = ?", p)
        conn.execute("DELETE FROM code_quality WHERE project_id = ?", p)
        conn.execute("DELETE FROM artifact_changes WHERE project_id = ?", p)
        conn.execute("DELETE FROM artifacts WHERE project_id = ?", p)
        conn.execute(
            "DELETE FROM developer_session_notes WHERE task_id IN "
            "(SELECT id FROM tasks WHERE project_id = ?)", p,
        )
        conn.execute("DELETE FROM code_reviews WHERE project_id = ?", p)
        conn.execute("DELETE FROM agent_runs WHERE project_id = ?", p)
        conn.execute("DELETE FROM chat_messages WHERE project_id = ?", p)
        conn.execute("DELETE FROM conversation_threads WHERE project_id = ?", p)
        conn.execute("DELETE FROM status_updates WHERE project_id = ?", p)
        conn.execute("DELETE FROM events_log WHERE project_id = ?", p)
        conn.execute("DELETE FROM findings WHERE project_id = ?", p)
        conn.execute("DELETE FROM knowledge WHERE project_id = ?", p)
        conn.execute("DELETE FROM branches WHERE project_id = ?", p)
        conn.execute("DELETE FROM repositories WHERE project_id = ?", p)
        conn.execute("DELETE FROM wiki_pages WHERE project_id = ?", p)
        conn.execute("DELETE FROM reference_files WHERE project_id = ?", p)
        conn.execute("DELETE FROM tasks WHERE project_id = ?", p)
        conn.execute("DELETE FROM milestones WHERE project_id = ?", p)
        conn.execute("DELETE FROM epics WHERE project_id = ?", p)

        conn.execute("DELETE FROM projects WHERE id = ?", p)
        conn.commit()

    execute_with_retry(_delete)


class StartProjectPlanning(BaseModel):
    """Explicit owner planning input; optional key preserves old bodyless starts as one original start per project premise snapshot."""

    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    prompt: str | None = Field(default=None, min_length=1, max_length=50000)
    repository_id: int | None = Field(default=None, ge=1)


@router.post("/{project_id}/start")
async def start_project(
    project_id: int, request: Request, body: StartProjectPlanning | None = None
):
    """Start one durable owned native plan; never launch CrewAI threads, clear events or imply execution permission from a planning response."""
    from backend.api.routes.runs import service
    from backend.runtime.contracts import RunConflict

    if flow_manager.is_project_running(project_id):
        raise RunConflict(
            "Legacy project work is still registered; stop and reconcile its original owner before native planning"
        )
    command = body or StartProjectPlanning()
    run = await service(request).start_project_plan(project_id, **command.model_dump())
    from backend.planning.store import ProjectPlans

    runtime = service(request)
    original = await asyncio.to_thread(
        ProjectPlans(runtime.store).start_receipt, project_id, run.run_id
    )
    return {
        "message": "Planificación nativa guardada; la propuesta requerirá tu aceptación.",
        "status": "planning",
        "planning_task_id": run.task_id,
        "request": original,
        "run": asdict(run),
    }


@router.post("/{project_id}/stop")
async def stop_project(project_id: int, request: Request, body: StopObservedProject | None = None):
    """Withdraw this project's native work and request legacy teardown where present; paused describes owner intent, not unproved physical closure."""
    state = await asyncio.to_thread(load_project_state, project_id)
    if not state:
        raise ProjectNotFound(project_id)
    if body is not None:
        receipt, created = await asyncio.to_thread(_workspace(request).request_stop, project_id, **body.model_dump())
        runtime = request.app.state.runtime_service
        if created and runtime is not None:
            for run_id in receipt['run_ids']:
                await runtime.stop(project_id,run_id)
            for source in receipt.get('source_operations',[]):
                await runtime.sources.stop(project_id,source['operation_key'],operation_id=source['operation_id'],fence=source['fence'])
        return JSONResponse(receipt, headers={"Cache-Control":"no-store"})
    runtime = request.app.state.runtime_service
    runs = await runtime.stop_project(project_id) if runtime is not None else []
    legacy = None
    if flow_manager.is_project_running(project_id):
        legacy = await asyncio.to_thread(flow_manager.stop_project_flow, project_id)
    await asyncio.to_thread(update_project_status, project_id, "paused")
    return {
        "message": "Detención solicitada; el cierre de una ejecución anterior del proyecto sigue sin comprobarse." if legacy is not None and not legacy["registered_workers_closed"] else "Detención solicitada; consulta los intentos para comprobar su cierre.",
        "legacy_control": legacy,
        "status": "paused",
        "runs": [asdict(run) for run in runs],
    }
