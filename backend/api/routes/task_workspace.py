"""Authenticated task context and advisory writes, sharing the business grant boundary."""

from typing import Literal

from fastapi import APIRouter, Query

from backend.api.models.task_workspace import AddTaskComment, SaveContinuity
from backend.api.research_dependencies import Context
from backend.task_workspace import TaskWorkspace

router = APIRouter(prefix="/api/research-tools/task-workspace", tags=["research-tools"])


@router.get("/structure/{kind}")
def project_structure(kind: Literal["epics", "milestones"], ctx: Context,
                      after_id: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                      status: str | None = None, epic_id: int | None = Query(None, gt=0)):
    """List project-scoped hierarchy metadata with explicit label counts and bounded pagination."""
    return TaskWorkspace(ctx.store).structure(ctx.scope, kind, after_id=after_id, limit=limit, status=status, epic_id=epic_id)


@router.get("/structure/{kind}/{record_id}")
def project_structure_read(kind: Literal["epics", "milestones"], record_id: int, ctx: Context,
                           field: Literal["title", "description"] = "description",
                           offset: int = Query(0, ge=0), max_chars: int = Query(12000, ge=1, le=16000)):
    """Read exact current title/description windows without elevating historical labels to instructions."""
    return TaskWorkspace(ctx.store).structure_record(ctx.scope, kind, record_id, field=field, offset=offset, max_chars=max_chars)


@router.get("/tasks")
def task_list(ctx: Context, after_id: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
              status: str | None = None, task_type: str | None = None, assignee: str | None = None,
              epic_id: int | None = Query(None, gt=0), milestone_id: int | None = Query(None, gt=0)):
    """List only the bound project's current task metadata with stable ID pagination."""
    return TaskWorkspace(ctx.store).tasks(
        ctx.scope, after_id=after_id, limit=limit, status=status, task_type=task_type,
        assignee=assignee, epic_id=epic_id, milestone_id=milestone_id,
    )


@router.get("/tasks/{target_task_id}")
def task_read(target_task_id: int, ctx: Context,
              field: Literal["title", "description", "acceptance_criteria"] = "description",
              offset: int = Query(0, ge=0), max_chars: int = Query(12000, ge=1, le=16000)):
    """Read an explicit text window without relabeling task metadata as an owner instruction."""
    return TaskWorkspace(ctx.store).read(ctx.scope, target_task_id, field=field, offset=offset, max_chars=max_chars)


@router.get("/tasks/{target_task_id}/dependencies")
def task_dependencies(target_task_id: int, ctx: Context,
                      direction: Literal["requires", "required_by"] = "requires",
                      after_id: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    """Expose declared dependencies, not an independent scheduler or can-start verdict."""
    return TaskWorkspace(ctx.store).dependencies(ctx.scope, target_task_id, direction=direction, after_id=after_id, limit=limit)


@router.get("/tasks/{target_task_id}/history")
def task_history(target_task_id: int, ctx: Context, kind: Literal["comments", "events"] = "comments",
                 after_id: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                 entry_id: int | None = Query(None, gt=0), offset: int = Query(0, ge=0),
                 max_chars: int = Query(12000, ge=1, le=16000)):
    """Read one history stream or recover the full text of a selected entry."""
    return TaskWorkspace(ctx.store).history(ctx.scope, target_task_id, kind=kind,
        after_id=after_id, limit=limit, entry_id=entry_id, offset=offset, max_chars=max_chars)


@router.post("/comments", status_code=201)
def task_comment(command: AddTaskComment, ctx: Context):
    """Persist one advisory comment and its receipt under the actual author grant."""
    return TaskWorkspace(ctx.store).comment(ctx.scope, command.operation_key, command.content,
                                             comment_type=command.comment_type)


@router.get("/continuity")
def continuity_read(ctx: Context, offset: int = Query(0, ge=0), max_chars: int = Query(12000, ge=1, le=16000)):
    """Recover this actor's latest note in windows; old prose does not authorize resumption."""
    return TaskWorkspace(ctx.store).note(ctx.scope, offset=offset, max_chars=max_chars)


@router.post("/continuity", status_code=201)
def continuity_save(command: SaveContinuity, ctx: Context):
    """Apply an optimistic advisory-note update without dispatching or changing task status."""
    return TaskWorkspace(ctx.store).save_note(ctx.scope, command.operation_key, phase=command.phase,
        note=command.note.model_dump(), expected_sha256=command.expected_sha256, last_file=command.last_file)
