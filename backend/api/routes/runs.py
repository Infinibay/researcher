"""Owner-controlled durable execution; tool bearer credentials cannot enter here."""

import asyncio
from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import APIRouter, FastAPI, HTTPException, Path, Query, Request
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


class StartFindingReview(BaseModel):
    """Owner-observed version and task scope for a separately admitted reviewer."""

    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    context_version: int = Field(ge=1)
    finding_id: int = Field(ge=1)
    subject_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    repository_id: int | None = Field(None, ge=1)
    request: str = Field(
        default="Revisa el hallazgo y sus fuentes guardadas. Explica qué comprobaste, qué decisión registraste y qué sigue sin conocerse.",
        min_length=1,
        max_length=12000,
    )


class StartCodeReview(BaseModel):
    """Owner-observed exact author candidate; the host chooses the separate reviewer and readonly capabilities."""

    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    context_version: int = Field(gt=0)
    attempt_id: str = Field(min_length=1, max_length=128)
    subject_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request: str = Field(min_length=1, max_length=12000)


@router.post("/{project_id}/tasks/{task_id}/code-reviews", status_code=202)
async def start_code_review(
    project_id: int, task_id: int, body: StartCodeReview, request: Request
):
    """Admit one independent review through the existing owner/CSRF boundary and original receipt; never accept or publish."""
    from backend.runtime.code_reviews import CodeReviewTarget

    try:
        spec = RunSpec(
            project_id,
            task_id,
            "code-reviewer",
            body.context_version,
            body.operation_key,
            body.request,
            "codex",
        )
        target = CodeReviewTarget(body.attempt_id, body.subject_sha256)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return asdict(await service(request).review_code(spec, target))


class AcceptResult(BaseModel):
    """Bind an owner action to exactly the displayed candidate, context and review state."""

    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$"
    )
    candidate_id: int = Field(gt=0)
    candidate_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    context_version: int = Field(gt=0)
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    acknowledge_limits: bool
    note: str | None = Field(default=None, min_length=1, max_length=4000)


class AcceptCodeResult(BaseModel):
    """Owner-only exact candidate/review observation; agent identity and publication authority cannot be supplied."""

    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    attempt_id: str = Field(min_length=1, max_length=128)
    context_version: int = Field(gt=0)
    subject_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    acknowledge_limits: bool
    note: str | None = Field(default=None, min_length=1, max_length=4000)


class StartCodePublication(BaseModel):
    """Owner-observed acceptance and destination; execution authority, paths and credentials remain host-owned."""

    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    acceptance_operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    author_attempt_id: str = Field(min_length=1, max_length=128)
    context_version: int = Field(gt=0)
    subject_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_ref: str = Field(min_length=1, max_length=240)
    expected_target_sha: str | None = Field(
        default=None, pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$"
    )


@router.post("/{project_id}/runs/{author_run_id}/code-publications", status_code=202)
async def start_code_publication(
    project_id: int, author_run_id: str, body: StartCodePublication, request: Request
):
    """Admit one paired-owner publication; replay returns its original request/result without another effect or model turn."""
    from backend.runtime.code_publications import (
        CodePublicationIntent,
        CodePublications,
    )

    try:
        intent = CodePublicationIntent(**body.model_dump())
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    runtime = service(request)
    run = await runtime.publish_code(project_id, author_run_id, intent)
    saved = await asyncio.to_thread(
        CodePublications(runtime.store).request, project_id, run.run_id
    )
    return {"run": asdict(run), "request": saved}


@router.get("/{project_id}/code-publications/{run_id}")
async def code_publication_detail(project_id: int, run_id: str, request: Request):
    """Read original host publication intent and receipt without starting Git or inference."""
    from backend.runtime.code_publications import CodePublications

    data = await asyncio.to_thread(
        CodePublications(read_store(request)).request, project_id, run_id
    )
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.get("/{project_id}/runs/{run_id}/code-result")
async def code_result_state(project_id: int, run_id: str, request: Request):
    """Show scoped code/check/review evidence and historical acceptance without starting inference."""
    data = await asyncio.to_thread(
        read_store(request).code_result_state, project_id, run_id
    )
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.get("/{project_id}/runs/{run_id}/code-result/diff")
async def code_result_diff(
    project_id: int,
    run_id: str,
    request: Request,
    offset: int = Query(0, ge=0),
    max_chars: int = Query(12000, ge=1, le=24000),
):
    """Read an explicit window of the exact captured diff, including its identity and unread tail."""
    try:
        data = await asyncio.to_thread(
            read_store(request).code_result_diff,
            project_id,
            run_id,
            offset=offset,
            max_chars=max_chars,
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.post("/{project_id}/runs/{run_id}/code-result/accept")
async def accept_code_result(
    project_id: int, run_id: str, body: AcceptCodeResult, request: Request
):
    """Record an explicit paired-owner/CSRF decision; this endpoint neither dispatches inference nor publishes code."""
    try:
        data = await asyncio.to_thread(
            read_store(request).accept_code, project_id, run_id, **body.model_dump()
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.get("/{project_id}/runs/{run_id}/result")
async def result_state(project_id: int, run_id: str, request: Request):
    """Inspect explicit delivery, actual review limits and distinct original owner acceptance."""
    data = await asyncio.to_thread(read_store(request).result_state, project_id, run_id)
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.get(
    "/{project_id}/runs/{run_id}/result/candidates/{candidate_id}/reports/{report_id}"
)
async def result_report(
    project_id: int,
    run_id: str,
    candidate_id: int,
    report_id: int,
    request: Request,
    offset: int = Query(0, ge=0),
    max_chars: int = Query(12000, ge=1, le=20000),
):
    """Page the selected frozen report instead of silently substituting its present-day artifact."""
    data = await asyncio.to_thread(
        read_store(request).result_report,
        project_id,
        run_id,
        candidate_id,
        report_id,
        offset=offset,
        max_chars=max_chars,
    )
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.post("/{project_id}/runs/{run_id}/result/accept")
async def accept_result(
    project_id: int, run_id: str, body: AcceptResult, request: Request
):
    """Require the paired owner and CSRF through local-access middleware; never a tool bearer."""
    data = await asyncio.to_thread(
        read_store(request).accept_result, project_id, run_id, **body.model_dump()
    )
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.get("/{project_id}/findings/{finding_id}/review-state")
async def finding_review_state(
    project_id: int,
    finding_id: int,
    request: Request,
    after_id: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
):
    """Inspect an explicit current subject before requesting independently admitted work."""
    data = await asyncio.to_thread(
        read_store(request).finding_review_state,
        project_id,
        finding_id,
        after_id=after_id,
        limit=limit,
    )
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.get("/{project_id}/finding-reviews/{request_id}")
async def finding_review_detail(project_id: int, request_id: int, request: Request):
    """Show the actual decision and its old/current subject identity without accepting it."""
    data = await asyncio.to_thread(
        read_store(request).finding_review_detail, project_id, request_id
    )
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.post("/{project_id}/tasks/{task_id}/finding-reviews", status_code=202)
async def start_finding_review(
    project_id: int, task_id: int, body: StartFindingReview, request: Request
):
    """Only an owner request can admit this host-selected independent reviewer role."""
    from backend.research.models import ReviewTarget

    spec = RunSpec(
        project_id,
        task_id,
        "research-reviewer",
        body.context_version,
        body.operation_key,
        body.request,
        "codex",
    )
    return asdict(
        await service(request).submit(
            spec,
            repository_id=body.repository_id,
            review=ReviewTarget(body.finding_id, body.subject_sha256),
        )
    )


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


@router.post("/{project_id}/code-publications/{run_id}/recovery")
async def recover_code_publication(
    project_id: int, run_id: str, body: RecoverRun, request: Request
):
    """Observe a closed original local publication under fresh readonly host authority; never replay its transaction."""
    return await service(request).reconcile_publication(
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
    """Record an explicit owner correction for the next context, reopening accepted work without starting inference."""
    command = {
        "project_id": project_id,
        "task_id": task_id,
        "expected_version": body.expected_version,
        "operation_key": body.operation_key,
        "statement": body.statement,
        "source_kind": body.source_kind,
        "source_reference": "owner-correction:" + body.operation_key,
    }
    runtime = request.app.state.runtime_service
    version = (
        (await runtime.correct(**command))
        if runtime is not None
        else await asyncio.to_thread(read_store(request).correct_context, **command)
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


@router.get("/{project_id}/runs/{run_id}/input")
async def run_input(project_id: int, run_id: str, request: Request):
    data = await asyncio.to_thread(read_store(request).input_record, project_id, run_id)
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.get("/{project_id}/runs/{run_id}/jobs")
async def command_list(
    project_id: Annotated[int, Path(ge=1)],
    run_id: Annotated[str, Path(min_length=1, max_length=128, pattern=r"\S")],
    request: Request,
    after_seq: int = Query(0, ge=0, le=9223372036854775807),
    limit: int = Query(25, ge=1, le=100),
):
    data = await asyncio.to_thread(
        owner_view(request).command_list,
        project_id,
        run_id,
        after_seq=after_seq,
        limit=limit,
    )
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.get("/{project_id}/runs/{run_id}/jobs/{job_id}")
async def command_output(
    project_id: Annotated[int, Path(ge=1)],
    run_id: Annotated[str, Path(min_length=1, max_length=128, pattern=r"\S")],
    job_id: Annotated[str, Path(min_length=1, max_length=128, pattern=r"\S")],
    request: Request,
    stdout_offset: int = Query(0, ge=0, le=2147483647),
    stderr_offset: int = Query(0, ge=0, le=2147483647),
    max_bytes: int = Query(8192, ge=1, le=16384),
):
    data = await asyncio.to_thread(
        owner_view(request).command_output,
        project_id,
        run_id,
        job_id,
        stdout_offset=stdout_offset,
        stderr_offset=stderr_offset,
        max_bytes=max_bytes,
    )
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


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
    """Expose scoped owner history and only the configured adapter's actual task capabilities without opening inference."""
    data = await asyncio.to_thread(owner_view(request).workspace, project_id, task_id)
    data["runtime"] = {
        "configured": request.app.state.runtime_service is not None,
        "supported_task_types": list(
            request.app.state.runtime_service.supported_task_types
        )
        if request.app.state.runtime_service is not None
        else [],
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
    expected_sha256: str | None = Query(None, pattern=r"^[0-9a-f]{64}$"),
):
    """Read an owner-scoped saved source window, verifying actual and optional reviewed hashes."""
    data = await asyncio.to_thread(
        owner_view(request).source,
        project_id,
        source_id,
        offset=offset,
        max_chars=max_chars,
        expected_sha256=expected_sha256,
    )
    return JSONResponse(data, headers={"Cache-Control": "no-store"})
