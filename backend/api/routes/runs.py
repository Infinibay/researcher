"""Owner-controlled durable execution; tool bearer credentials cannot enter here."""

import asyncio
from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.runtime.contracts import RunConflict, RunNotFound, RunSpec

router = APIRouter(prefix="/api/projects", tags=["runtime"])


def install_run_errors(app: FastAPI):
    async def not_found(request, exc):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    async def conflict(request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    app.add_exception_handler(RunNotFound, not_found)
    app.add_exception_handler(RunConflict, conflict)


def service(request: Request):
    runtime = request.app.state.runtime_service
    if runtime is None:
        raise HTTPException(
            503, "Configure the local subscription runtime before starting work"
        )
    return runtime


class StartRun(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    context_version: int = Field(ge=1)
    request: str = Field(min_length=1, max_length=50000)
    repository_id: int | None = Field(None, ge=1)


class CorrectContext(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    expected_version: int = Field(ge=1)
    statement: str = Field(min_length=1, max_length=12000)
    source_kind: Literal["user_message", "user_example"] = "user_message"

    @field_validator("statement")
    @classmethod
    def nonempty_statement(cls, value):
        if not value.strip():
            raise ValueError("A correction needs a nonempty statement")
        return value


@router.post("/{project_id}/tasks/{task_id}/runs", status_code=202)
async def start_run(project_id: int, task_id: int, body: StartRun, request: Request):
    try:
        spec = RunSpec(
            project_id,
            task_id,
            "researcher",
            body.context_version,
            body.operation_key,
            body.request,
            "codex",
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return asdict(await service(request).submit(spec, repository_id=body.repository_id))


@router.get("/{project_id}/runs/{run_id}")
async def read_run(project_id: int, run_id: str, request: Request):
    return asdict(
        await asyncio.to_thread(service(request).store.get, project_id, run_id)
    )


@router.post("/{project_id}/runs/{run_id}/stop", status_code=202)
async def stop_run(project_id: int, run_id: str, request: Request):
    return asdict(await service(request).stop(project_id, run_id))


@router.post("/{project_id}/tasks/{task_id}/context-corrections")
async def correct_context(
    project_id: int, task_id: int, body: CorrectContext, request: Request
):
    # Deterministic source identity preserves retry intent. This labels origin,
    # not truth, understanding, or application inside an already-running turn.
    version = await service(request).correct(
        project_id=project_id,
        task_id=task_id,
        expected_version=body.expected_version,
        operation_key=body.operation_key,
        statement=body.statement,
        source_kind=body.source_kind,
        source_reference="owner-correction:" + body.operation_key,
    )
    return {
        "context_version": version,
        "application": "recorded_for_next_run",
        "inference_started": False,
    }


@router.get("/{project_id}/runtime-events")
async def history(
    project_id: int,
    request: Request,
    after_id: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    return asdict(
        await asyncio.to_thread(
            service(request).store.events, project_id, after_id=after_id, limit=limit
        )
    )


@router.get("/{project_id}/tasks/{task_id}/runtime-context")
async def current_context(project_id: int, task_id: int, request: Request):
    return await asyncio.to_thread(
        service(request).store.context_snapshot, project_id, task_id
    )
