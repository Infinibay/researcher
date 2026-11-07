"""Owner-controlled durable execution; tool bearer credentials cannot enter here."""

import asyncio
from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import APIRouter, FastAPI, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.api.models.code_carryover import (
    PreviewFileImport,
    PriorCodeSelection,
    PriorFilesSelection,
    PriorBranchSelection,
)
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
    """Original owner request with optional observed prior code as attributed data."""

    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    context_version: int = Field(ge=1)
    request: str = Field(min_length=1, max_length=50000)
    repository_id: int | None = Field(None, ge=1)
    prior_code: PriorCodeSelection | PriorFilesSelection | PriorBranchSelection | None = None


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
    check_policy_revision: int | None = Field(default=None, gt=0, le=9007199254740991)


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


class RemoteRepositoryObservation(BaseModel):
    """Owner-observed remote identity; no credential or filesystem/process capability can be supplied."""

    model_config = ConfigDict(extra="forbid", strict=True)
    api_base: str = Field(min_length=1, max_length=2048)
    repository_id: int = Field(gt=0)
    full_name: str = Field(min_length=1, max_length=240)
    clone_url: str = Field(min_length=1, max_length=4096)


class StartRemotePush(BaseModel):
    """Explicit push request distinct from local acceptance and later PR/merge decisions."""

    model_config = ConfigDict(extra="forbid", strict=True)
    stage: Literal["push"]
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    remote: RemoteRepositoryObservation
    target_ref: str = Field(min_length=1, max_length=240)
    expected_target_sha: str | None = Field(pattern=r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")


class StartRemotePull(BaseModel):
    """Original PR description and base observation over one exact completed remote push."""

    model_config = ConfigDict(extra="forbid", strict=True)
    stage: Literal["pull"]
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    base_ref: str = Field(min_length=1, max_length=240)
    base_sha: str = Field(pattern=r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")
    title: str = Field(min_length=1, max_length=256)
    body: str = Field(min_length=1, max_length=12000)


class StartRemoteMerge(BaseModel):
    """Separate owner decision to merge the exact completed original PR."""

    model_config = ConfigDict(extra="forbid", strict=True)
    stage: Literal["merge"]
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")


RemotePublicationBody = Annotated[
    StartRemotePush | StartRemotePull | StartRemoteMerge, Field(discriminator="stage")
]


@router.post("/{project_id}/runs/{origin_run_id}/remote-publications", status_code=202)
async def start_remote_publication(
    project_id: int, origin_run_id: str, body: RemotePublicationBody, request: Request
):
    """Admit a strict owner action only when its runtime has owned remote transport; replay returns the original action, never another effect."""
    from backend.runtime.remote_publication import RemoteRepository
    from backend.runtime.remote_runtime import (
        RemoteMergeRequest,
        RemotePublications,
        RemotePullRequest,
        RemotePushRequest,
    )

    try:
        if isinstance(body, StartRemotePush):
            command = RemotePushRequest(
                body.operation_key,
                origin_run_id,
                RemoteRepository(**body.remote.model_dump()),
                body.target_ref,
                body.expected_target_sha,
            )
        elif isinstance(body, StartRemotePull):
            command = RemotePullRequest(
                body.operation_key,
                origin_run_id,
                body.base_ref,
                body.base_sha,
                body.title,
                body.body,
            )
        else:
            command = RemoteMergeRequest(body.operation_key, origin_run_id)
        run = await service(request).publish_remote(project_id, command)
    except ValueError as error:
        raise HTTPException(
            status_code=422, detail="Invalid original remote publication intent"
        ) from error
    packet = await asyncio.to_thread(
        RemotePublications(read_store(request)).request, project_id, run.run_id
    )
    return {"run": asdict(run), "request": packet}


class AcceptProjectPlan(BaseModel):
    """Owner decision over one exact proposal/version; task IDs and execution permission are not client supplied."""

    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    proposal_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    context_version: int = Field(ge=1)


@router.get("/{project_id}/runs/{run_id}/project-plan")
async def project_plan_state(project_id: int, run_id: str, request: Request):
    """Inspect original structured planning material, proposal and distinct owner acceptance without dispatching work."""
    from backend.planning.store import ProjectPlans

    data = await asyncio.to_thread(
        ProjectPlans(read_store(request)).state, project_id, run_id
    )
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.post("/{project_id}/runs/{run_id}/project-plan/accept")
async def accept_project_plan(
    project_id: int, run_id: str, body: AcceptProjectPlan, request: Request
):
    """Atomically create pending graph nodes from an exact closed proposal under paired-owner/CSRF control; no model or child task is started."""
    from backend.planning.store import ProjectPlans

    data = await asyncio.to_thread(
        ProjectPlans(read_store(request)).accept,
        project_id,
        run_id,
        **body.model_dump(),
    )
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


class ExecuteProjectPlan(BaseModel):
    """Exact observed graph context; the owner cannot supply agents, prompts, grants or arbitrary task identities."""

    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ControlPlanExecution(ExecuteProjectPlan):
    """Pause or resume the same original execution; resume is not an instruction to replay stopped attempts."""

    status: Literal["active", "paused"]
    authorization_revision: int = Field(default=0, ge=0)


class ReauthorizePlanExecution(BaseModel):
    """Owner-observed corrected graph and history; the host derives all task identities, delivery scope and permissions."""

    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


@router.get("/{project_id}/plan-executions/{execution_id}/reauthorization")
async def plan_graph_reauthorization(project_id: int, execution_id: str, request: Request):
    """Offer exact current premises, changes, retained acceptances and original closed effects without starting work."""
    from backend.planning.execution import PlanExecutions

    data = await asyncio.to_thread(PlanExecutions(read_store(request)).reauthorization_state, project_id, execution_id)
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.post("/{project_id}/plan-executions/{execution_id}/reauthorization")
async def reauthorize_plan_graph(project_id: int, execution_id: str, body: ReauthorizePlanExecution, request: Request):
    """Record a separate paired-owner revision; original intent stays immutable and corrected dispatch remains paused."""
    data = await service(request).reauthorize_plan(project_id, execution_id, **body.model_dump())
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


class ContinuePlanDelivery(BaseModel):
    """Exact owner-observed closed predecessor; arbitrary prompts, actors or task substitutions cannot enter a continuation."""

    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


@router.get("/{project_id}/plan-executions/{execution_id}/deliveries/{delivery_id}/continuation")
async def plan_delivery_continuation(project_id: int, execution_id: str, delivery_id: str, request: Request):
    """Inspect original closure, partial effects and consumption without starting work; available when the native runtime is offline."""
    from backend.planning.execution import PlanExecutions

    data = await asyncio.to_thread(PlanExecutions(read_store(request)).continuation_state, project_id, execution_id, delivery_id)
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.post("/{project_id}/plan-executions/{execution_id}/deliveries/{delivery_id}/continuation")
async def continue_plan_delivery(project_id: int, execution_id: str, delivery_id: str, body: ContinuePlanDelivery, request: Request):
    """Authorize one causal successor under paired-owner/CSRF control; paused dispatch stays paused and the old run remains historical."""
    data = await service(request).continue_plan_delivery(project_id, execution_id, delivery_id, **body.model_dump())
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.get("/{project_id}/runs/{run_id}/project-plan/execution")
async def project_plan_execution(project_id: int, run_id: str, request: Request):
    """Read exact execution preview and causal deliveries without starting an agent or requiring a live runtime."""
    from backend.planning.execution import PlanExecutions

    data = await asyncio.to_thread(PlanExecutions(read_store(request)).state, project_id, run_id)
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


class CompleteProject(BaseModel):
    """A paired owner's explicit scope review and acknowledgement of every observed unpublished candidate; no caller-supplied proof or authority."""

    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    report_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    acknowledged_unpublished_attempts: list[str] = Field(max_length=256)
    statement: str = Field(min_length=1, max_length=4000)


@router.get("/{project_id}/runs/{run_id}/project-plan/completion")
async def project_completion_report(project_id: int, run_id: str, request: Request):
    """Read the complete attributed project report offline; no inference, publication, task acceptance or completion effect occurs."""
    from backend.api.flow_manager import flow_manager
    from backend.planning.completion import ProjectCompletion

    records = ProjectCompletion(read_store(request), legacy_active=flow_manager.is_project_running)
    data = await asyncio.to_thread(records.state, project_id, run_id)
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.post("/{project_id}/runs/{run_id}/project-plan/completion/accept")
async def accept_project_completion(project_id: int, run_id: str, body: CompleteProject, request: Request):
    """Commit only an exact paired-owner whole-project decision; retries recover the historical receipt without repeating any project effect."""
    from backend.api.flow_manager import flow_manager
    from backend.planning.completion import ProjectCompletion

    records = ProjectCompletion(read_store(request), legacy_active=flow_manager.is_project_running)
    data = await asyncio.to_thread(records.accept, project_id, run_id, **body.model_dump())
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.post("/{project_id}/runs/{run_id}/project-plan/execution")
async def execute_project_plan(project_id: int, run_id: str, body: ExecuteProjectPlan, request: Request):
    """Record a distinct paired-owner execution decision; the existing runtime dispatcher owns readiness and physical attempts."""
    from backend.api.flow_manager import flow_manager

    if flow_manager.is_project_running(project_id):
        raise RunConflict("Stop and reconcile the registered legacy project owner before native execution")
    data = await service(request).execute_plan(project_id, run_id, **body.model_dump())
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.post("/{project_id}/plan-executions/{execution_id}/control")
async def control_project_plan_execution(project_id: int, execution_id: str, body: ControlPlanExecution, request: Request):
    """Persist owner pause/resume first; returned pause acknowledges intent and never claims that native peers have physically closed."""
    data = await service(request).control_plan_execution(project_id, execution_id, **body.model_dump())
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


class RemotePreviewBody(BaseModel):
    """Owner branch choices only; server identity, registered URL and credential are derived by the host."""

    model_config = ConfigDict(extra="forbid", strict=True)
    target_ref: str = Field(min_length=1, max_length=240)
    base_ref: str = Field(min_length=1, max_length=240)


@router.post("/{project_id}/code-publications/{run_id}/remote-preview")
async def preview_remote_destination(
    project_id: int, run_id: str, body: RemotePreviewBody, request: Request
):
    """Observe a registered accepted destination under paired-owner/CSRF control without performing publication."""
    try:
        return await service(request).preview_remote(
            project_id, run_id, body.target_ref, body.base_ref
        )
    except ValueError as error:
        raise HTTPException(422, "Invalid remote branch observation") from error


@router.get("/{project_id}/code-publications/{run_id}/remote-publications")
async def remote_publication_history(project_id: int, run_id: str, request: Request):
    """Read only saved original remote actions for this exact scoped local publication; no implicit server lookup or retry."""
    from backend.runtime.remote_destinations import RemoteDestinations

    data = await asyncio.to_thread(
        RemoteDestinations(read_store(request)).history, project_id, run_id
    )
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.get("/{project_id}/remote-publications/{run_id}")
async def remote_publication_detail(project_id: int, run_id: str, request: Request):
    """Inspect original remote owner intent and issued/unknown/result stages without network calls or retry."""
    from backend.runtime.remote_runtime import RemotePublications

    packet = await asyncio.to_thread(
        RemotePublications(read_store(request)).request, project_id, run_id
    )
    return JSONResponse(packet, headers={"Cache-Control": "no-store"})


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


@router.post("/{project_id}/remote-publications/{run_id}/recovery")
async def recover_remote_publication(
    project_id: int, run_id: str, body: RecoverRun, request: Request
):
    """Observe original remote history with fresh readonly authority after actual original Git/HTTP closure; never repeat push or POST."""
    return await service(request).reconcile_remote_publication(
        project_id=project_id, run_id=run_id, **body.model_dump()
    )


@router.post("/{project_id}/tasks/{task_id}/runs", status_code=202)
async def start_run(project_id: int, task_id: int, body: StartRun, request: Request):
    """Start fresh native work with an exact optional earlier candidate selection; never transfer its approval."""
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
    return asdict(await service(request).submit(spec, repository_id=body.repository_id, prior_code=body.prior_code.target() if body.prior_code else None))


@router.get("/{project_id}/tasks/{task_id}/prior-code/{attempt_id}")
async def preview_prior_code(project_id: int, task_id: int, attempt_id: str, request: Request):
    """Inspect retained original native input and exact diff without resuming, editing or accepting it."""
    from backend.runtime.code_carryover import CodeCarryovers

    return await asyncio.to_thread(CodeCarryovers(read_store(request)).preview, project_id, task_id, attempt_id)


@router.get("/{project_id}/tasks/{task_id}/prior-files/sources")
async def prior_file_sources(project_id: Annotated[int, Path(gt=0)], task_id: Annotated[int, Path(gt=0)], request: Request):
    """List recorded old file origins for explicit owner choice, without inferring task ownership from a legacy agent label."""
    from backend.runtime.file_imports import FileImports

    return await asyncio.to_thread(FileImports(read_store(request)).sources, project_id, task_id)


@router.get('/{project_id}/tasks/{task_id}/prior-branches')
async def prior_branch_sources(project_id: Annotated[int, Path(gt=0)], task_id: Annotated[int, Path(gt=0)], request: Request):
    """List scoped recorded branches without executing Git; the owner chooses a full commit and original preparation must verify/capture it."""
    from backend.runtime.branch_inputs import BranchInputs

    return await asyncio.to_thread(BranchInputs(read_store(request)).sources, project_id, task_id)


@router.post("/{project_id}/tasks/{task_id}/prior-files/preview")
async def preview_prior_files(project_id: Annotated[int, Path(gt=0)], task_id: Annotated[int, Path(gt=0)], body: PreviewFileImport, request: Request):
    """Observe only selected bytes from an actual registered origin; this preview starts no process or inference."""
    from backend.runtime.file_imports import FileImports

    runtime = service(request)
    binding = await asyncio.to_thread(runtime.workspaces.bind, project_id, body.repository_id)
    return await asyncio.to_thread(FileImports(runtime.store).preview, project_id, task_id, binding, body.source_kind, body.source_id, tuple(body.paths))


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
    from backend.runtime.task_profiles import (
        DEVELOPMENT_TASK_TYPES,
        OWNER_ONLY_LEGACY_TASK_TYPES,
    )

    service = request.app.state.runtime_service
    data["runtime"] = {
        "owner_controlled_task_types": list(OWNER_ONLY_LEGACY_TASK_TYPES),
        "development_task_types": [kind for kind in DEVELOPMENT_TASK_TYPES if service is not None and kind in service.supported_task_types],
        "configured": request.app.state.runtime_service is not None,
        "supported_task_types": list(
            request.app.state.runtime_service.supported_task_types
        )
        if request.app.state.runtime_service is not None
        else [],
        "remote_publication": getattr(
            getattr(request.app.state.runtime_service, "runtime", None),
            "supports_remote_publication",
            False,
        )
        is True,
        "model": getattr(
            getattr(request.app.state.runtime_service, "runtime", None), "model", None
        ),
    }
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.get("/{project_id}/agent-runs")
async def agent_runs(
    project_id: int,
    request: Request,
    before_seq: int | None = Query(default=None, ge=1, le=9223372036854775807),
    limit: int = Query(default=25, ge=1, le=100),
):
    """Read project-native actors and current attempt usage without dispatching or probing processes."""
    data = await asyncio.to_thread(
        owner_view(request).agent_runs, project_id, before_seq=before_seq, limit=limit
    )
    data['runtime_configured'] = request.app.state.runtime_service is not None
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.get("/{project_id}/tasks/{task_id}/run-history")
async def task_run_history(
    project_id: int,
    task_id: int,
    request: Request,
    before_seq: int | None = Query(default=None, ge=1, le=9223372036854775807),
    limit: int = Query(default=25, ge=1, le=100),
):
    """Read older task executions without changing the current workspace or granting execution."""
    from backend.runtime.history import RuntimeHistory

    data = await asyncio.to_thread(RuntimeHistory(read_store(request).database).task_runs,
                                   project_id, task_id, before_seq=before_seq, limit=limit)
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.get("/{project_id}/runs/{run_id}/attempts")
async def run_attempt_history(
    project_id: int,
    run_id: str,
    request: Request,
    before_seq: int | None = Query(default=None, ge=1, le=9223372036854775807),
    limit: int = Query(default=25, ge=1, le=100),
):
    """Read each attempt's original observations through the authenticated project owner."""
    from backend.runtime.history import RuntimeHistory

    data = await asyncio.to_thread(RuntimeHistory(read_store(request).database).attempts,
                                   project_id, run_id, before_seq=before_seq, limit=limit)
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.get("/{project_id}/work-budget")
async def project_work_budget(project_id: int, request: Request):
    """Expose recorded admission capacity without representing it as subscription quota or billing."""
    from backend.runtime.history import RuntimeHistory

    data = await asyncio.to_thread(RuntimeHistory(read_store(request).database).budget, project_id)
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


class ProjectBudgetChange(BaseModel):
    """One explicit owner decision over total project capacity, never a request to resume or spend."""

    model_config = ConfigDict(extra='forbid', strict=True)
    operation_key: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_.:-]+$')
    expected_revision: int = Field(ge=0, le=9007199254740991)
    turn_limit: int = Field(ge=1, le=9007199254740991)
    token_limit: int = Field(ge=1, le=9007199254740991)
    auxiliary_operation_limit: int | None = Field(default=None, ge=1, le=9007199254740991)
    auxiliary_cpu_ms_limit: int | None = Field(default=None, ge=1, le=9007199254740991)
    reason: str = Field(default='', max_length=2000)


@router.post("/{project_id}/work-budget")
async def change_project_work_budget(project_id: int, body: ProjectBudgetChange, request: Request):
    """Record owner-authorized total limits with revision/idempotency checks, even without a configured runtime; never dispatch work."""
    from backend.runtime.project_budget import ProjectBudgetPolicies

    try:
        receipt = await asyncio.to_thread(ProjectBudgetPolicies(read_store(request)).update, project_id, **body.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return JSONResponse(receipt, headers={"Cache-Control": "no-store"})


@router.get("/{project_id}/work-budget/changes/{operation_key}")
async def project_budget_change_receipt(project_id: int, operation_key: str, request: Request):
    """Read the original scoped budget decision without resending it or reinterpreting later policy as its receipt."""
    from backend.runtime.project_budget import ProjectBudgetPolicies

    try:
        receipt = await asyncio.to_thread(ProjectBudgetPolicies(read_store(request)).receipt, project_id, operation_key)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return JSONResponse(receipt, headers={"Cache-Control": "no-store"})


class ProjectCheckPolicyChange(BaseModel):
    """Owner choice for future code acceptance, bound to the observed project revision."""

    model_config = ConfigDict(extra='forbid', strict=True)
    operation_key: str = Field(pattern=r'^[A-Za-z0-9_.:-]{1,128}$')
    expected_revision: int = Field(ge=0, lt=9007199254740991)
    mode: Literal['require_tests', 'allow_missing']


@router.get('/{project_id}/check-policy')
async def project_check_policy(project_id: int, request: Request):
    """Read the explicit project decision without requiring a configured model runtime."""
    from backend.runtime.project_check_policy import ProjectCheckPolicies

    data = await asyncio.to_thread(ProjectCheckPolicies(read_store(request)).state, project_id)
    return JSONResponse(data, headers={'Cache-Control': 'no-store'})


@router.post('/{project_id}/check-policy')
async def change_project_check_policy(project_id: int, body: ProjectCheckPolicyChange, request: Request):
    """Record an owner/CSRF decision; it neither reruns checks nor accepts or publishes code."""
    from backend.runtime.project_check_policy import ProjectCheckPolicies

    data = await asyncio.to_thread(ProjectCheckPolicies(read_store(request)).update, project_id, **body.model_dump())
    return JSONResponse(data, headers={'Cache-Control': 'no-store'})


@router.get('/{project_id}/check-policy/changes/{operation_key}')
async def project_check_policy_receipt(project_id: int, operation_key: str, request: Request):
    """Recover the original decision after a lost response, without repeating a write."""
    from backend.runtime.project_check_policy import ProjectCheckPolicies

    try:
        data = await asyncio.to_thread(ProjectCheckPolicies(read_store(request)).receipt, project_id, operation_key)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return JSONResponse(data, headers={'Cache-Control': 'no-store'})


class AuxiliaryContinuation(BaseModel):
    """Freeze the exact interrupted calculation and owner command; no input replay is part of this request."""

    model_config = ConfigDict(extra='forbid', strict=True)
    operation_key: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_.:-]+$')
    source_operation_id: str = Field(pattern=r'^[0-9a-f]{64}$')
    reason: str = Field(default='', max_length=2000)


@router.get('/{project_id}/local-work')
async def local_work_history(project_id: int, request: Request,
                             before: int | None = Query(None, ge=1, le=9007199254740991),
                             limit: int = Query(20, ge=1, le=100)):
    """Show owner-scoped local calculations and observed closure without fetching result blobs or starting work."""
    from backend.runtime.auxiliary_recovery import AuxiliaryRecovery

    data=await asyncio.to_thread(AuxiliaryRecovery(read_store(request)).list,project_id,before=before,limit=limit)
    return JSONResponse(data,headers={'Cache-Control':'no-store'})


@router.post('/{project_id}/local-work/continuations')
async def authorize_local_continuation(project_id: int, body: AuxiliaryContinuation, request: Request):
    """Authorize one identical future calculation after fresh closure verification, without dispatch or refund."""
    from backend.runtime.auxiliary_recovery import AuxiliaryRecovery

    try:data=await asyncio.to_thread(AuxiliaryRecovery(read_store(request)).authorize,project_id,**body.model_dump())
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    return JSONResponse(data,headers={'Cache-Control':'no-store'})


@router.get('/{project_id}/local-work/continuations/{operation_key}')
async def local_continuation_receipt(project_id: int, operation_key: str, request: Request):
    """Recover the original local continuation decision without repeating its write or the worker calculation."""
    from backend.runtime.auxiliary_recovery import AuxiliaryRecovery

    try:data=await asyncio.to_thread(AuxiliaryRecovery(read_store(request)).receipt,project_id,operation_key)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    return JSONResponse(data,headers={'Cache-Control':'no-store'})


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
