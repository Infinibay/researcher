"""Owner-controlled durable execution; tool bearer credentials cannot enter here."""

import asyncio
from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.api.models.questions import AnswerQuestions
from backend.runtime.contracts import RunConflict, RunNotFound, RunSpec
from backend.runtime.peer_process import PeerUncertain

router = APIRouter(prefix="/api/projects", tags=["runtime"])


def install_run_errors(app: FastAPI):
    async def not_found(request, exc):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    async def conflict(request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    app.add_exception_handler(RunNotFound, not_found)
    app.add_exception_handler(RunConflict, conflict)

    async def uncertain(request, exc):
        return JSONResponse(
            status_code=503,
            content={
                "detail": "No se pudo comprobar el cierre local. La ejecución conserva su estado incierto; no se repetirá automáticamente."
            },
        )

    app.add_exception_handler(PeerUncertain, uncertain)


def service(request: Request):
    runtime = request.app.state.runtime_service
    if runtime is None:
        raise HTTPException(
            503, "Configure the local subscription runtime before starting work"
        )
    return runtime


def read_store(request):
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.tools.base.db import get_db_path

    runtime = request.app.state.runtime_service
    return runtime.store if runtime is not None else SQLiteRunStore(get_db_path())


def owner_view(request):
    from backend.runtime.views import OwnerRuntimeView

    return OwnerRuntimeView(read_store(request).database)


@router.post("/{project_id}/tasks/{task_id}/questions/{request_id}/answers")
async def answer_questions(
    project_id: int,
    task_id: int,
    request_id: int,
    body: AnswerQuestions,
    request: Request,
):
    from backend.runtime.sqlite_questions import SQLiteQuestionStore

    runtime = request.app.state.runtime_service
    questions = (
        runtime.questions
        if runtime is not None
        else SQLiteQuestionStore(read_store(request), None)
    )
    try:
        version = await asyncio.to_thread(
            questions.answer,
            project_id=project_id,
            task_id=task_id,
            request_id=request_id,
            expected_version=body.expected_version,
            operation_key=body.operation_key,
            answers=body.answers,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        "context_version": version,
        "application": "recorded_for_next_run",
        "inference_started": False,
    }


class StartRun(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    context_version: int = Field(ge=1)
    request: str = Field(min_length=1, max_length=50000)
    repository_id: int | None = Field(None, ge=1)


class RetryStart(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    context_version: int = Field(ge=1)
    expected_fence: int = Field(ge=0)


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


class RecoverRun(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    attempt_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    expected_fence: int = Field(ge=1)


@router.get("/{project_id}/runs/{run_id}/recovery")
async def inspect_recovery(project_id: int, run_id: str, request: Request):
    from backend.runtime.recovery import RunRecovery

    data = await asyncio.to_thread(
        RunRecovery(read_store(request)).inspection, project_id, run_id
    )
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.post("/{project_id}/runs/{run_id}/recovery")
async def reconcile_run(
    project_id: int, run_id: str, body: RecoverRun, request: Request
):
    return await service(request).reconcile(
        project_id=project_id, run_id=run_id, **body.model_dump()
    )


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
    return asdict(await asyncio.to_thread(read_store(request).get, project_id, run_id))


@router.post("/{project_id}/runs/{run_id}/retry-start", status_code=202)
async def retry_start(project_id: int, run_id: str, body: RetryStart, request: Request):
    return asdict(
        await service(request).retry_start(
            project_id=project_id, run_id=run_id, **body.model_dump()
        )
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
            read_store(request).events, project_id, after_id=after_id, limit=limit
        )
    )


@router.get("/{project_id}/tasks/{task_id}/runtime-context")
async def current_context(project_id: int, task_id: int, request: Request):
    return await asyncio.to_thread(
        read_store(request).context_snapshot, project_id, task_id
    )


@router.get("/{project_id}/questions")
async def question_inbox(
    project_id: int,
    request: Request,
    after_id: int = Query(default=0, ge=0, le=9223372036854775807),
    limit: int = Query(default=100, ge=1, le=100),
):
    data = await asyncio.to_thread(
        owner_view(request).question_inbox, project_id, after_id=after_id, limit=limit
    )
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.get("/{project_id}/tasks/{task_id}/workspace")
async def workspace(project_id: int, task_id: int, request: Request):
    data = await asyncio.to_thread(owner_view(request).workspace, project_id, task_id)
    data["runtime"] = {
        "configured": request.app.state.runtime_service is not None,
        "supported_task_types": ["research"],
        "model": getattr(
            getattr(request.app.state.runtime_service, "runtime", None), "model", None
        ),
    }
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.get("/{project_id}/research-sources/{source_id}")
async def owner_source(
    project_id: int,
    source_id: int,
    request: Request,
    offset: int = Query(0, ge=0),
    max_chars: int = Query(12000, ge=1, le=20000),
):
    data = await asyncio.to_thread(
        owner_view(request).source,
        project_id,
        source_id,
        offset=offset,
        max_chars=max_chars,
    )
    return JSONResponse(data, headers={"Cache-Control": "no-store"})
