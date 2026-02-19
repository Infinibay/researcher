"""Project CRUD endpoints and flow control."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException

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
async def create_project_endpoint(body: ProjectCreate):
    """Create a new project."""
    project_id = create_project(name=body.name, description=body.description)
    state = load_project_state(project_id)
    if not state:
        raise HTTPException(status_code=500, detail="Failed to create project")
    return _project_to_response(state)


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
    """Update project name or description."""
    state = load_project_state(project_id)
    if not state:
        raise ProjectNotFound(project_id)

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
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(project_id)
        sql = f"UPDATE projects SET {', '.join(updates)} WHERE id = ?"

        def _update(conn: sqlite3.Connection) -> None:
            conn.execute(sql, params)
            conn.commit()

        execute_with_retry(_update)

    state = load_project_state(project_id)
    return _project_to_response(state)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: int):
    """Delete a project and all related resources."""
    state = load_project_state(project_id)
    if not state:
        raise ProjectNotFound(project_id)

    if flow_manager.is_project_running(project_id):
        raise ProjectRunning(project_id)

    def _delete(conn: sqlite3.Connection) -> None:
        # Delete in dependency order
        conn.execute("DELETE FROM chat_messages WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM conversation_threads WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM status_updates WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM events_log WHERE project_id = ?", (project_id,))
        conn.execute(
            """DELETE FROM task_dependencies WHERE task_id IN
               (SELECT id FROM tasks WHERE project_id = ?)""",
            (project_id,),
        )
        conn.execute(
            """DELETE FROM task_comments WHERE task_id IN
               (SELECT id FROM tasks WHERE project_id = ?)""",
            (project_id,),
        )
        conn.execute("DELETE FROM tasks WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM milestones WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM epics WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM wiki_pages WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM reference_files WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM agent_runs WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM code_reviews WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()

    execute_with_retry(_delete)


@router.post("/{project_id}/start")
async def start_project(project_id: int):
    """Start the project flow and event listeners."""
    from backend.agents.registry import initialize_project_team

    state = load_project_state(project_id)
    if not state:
        raise ProjectNotFound(project_id)

    if flow_manager.is_project_running(project_id):
        return {"message": f"Project {project_id} is already running"}

    # Initialize the agent team immediately so they show up in the UI
    initialize_project_team(project_id)

    flow_manager.start_project_flow(project_id)
    return {"message": f"Project {project_id} started", "status": "executing"}


@router.post("/{project_id}/stop")
async def stop_project(project_id: int):
    """Stop the project flow and event listeners."""
    state = load_project_state(project_id)
    if not state:
        raise ProjectNotFound(project_id)

    flow_manager.stop_project_flow(project_id)
    return {"message": f"Project {project_id} stopped", "status": "paused"}
