"""Project-bound research tools; no arbitrary SQL, paths or model-side grants."""

import asyncio

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.responses import JSONResponse

from backend.api.models.questions import AskUser
from backend.api.models.research import (
    CaptureReference,
    CaptureWeb,
    FindingDetail,
    FindingReceipt,
    RecordFinding,
    ReportReceipt,
    ReportWindow,
    SourceReceipt,
    SourceWindow,
    WriteReport,
)
from backend.api.research_dependencies import Context
from backend.research.models import (
    EvidenceReference,
    FindingDraft,
    InvalidEvidence,
    OperationConflict,
    ReportDraft,
    ResearchForbidden,
    ResearchInputError,
    ResearchNotFound,
    SourceTooLarge,
    SourceUnavailable,
)

router = APIRouter(prefix="/api/research-tools", tags=["research-tools"])


@router.post("/questions", status_code=201)
async def ask_user(command: AskUser, ctx: Context, request: Request):
    from backend.api.routes.runs import service

    runtime = service(request)
    receipt = await asyncio.to_thread(
        runtime.questions.ask, ctx.scope, command.operation_key, command.domain()
    )
    runtime.question_requested(receipt["run_id"], receipt["attempt_id"])
    return receipt


def install_research_errors(app: FastAPI):
    for error, status, code in [
        (ResearchForbidden, 403, "scope_forbidden"),
        (ResearchNotFound, 404, "research_not_found"),
        (OperationConflict, 409, "operation_conflict"),
        (ResearchInputError, 422, "invalid_research_input"),
        (InvalidEvidence, 422, "invalid_evidence"),
        (SourceTooLarge, 413, "source_too_large"),
        (SourceUnavailable, 422, "source_unavailable"),
    ]:

        async def handle(request: Request, exc: Exception, _status=status, _code=code):
            return JSONResponse(
                status_code=_status,
                content={"error": str(exc), "code": _code, "detail": str(exc)},
            )

        app.add_exception_handler(error, handle)


def _window(text, offset, max_chars):
    content = text[offset : offset + max_chars]
    end = offset + len(content)
    return {
        "content": content,
        "total_chars": len(text),
        "offset": offset,
        "next_offset": end if end < len(text) else None,
    }


@router.get("/references")
def references(ctx: Context):
    return {
        "project_id": ctx.scope.project_id,
        "references": ctx.store.list_references(ctx.scope),
    }


@router.post("/sources/reference", response_model=SourceReceipt)
def capture_reference(command: CaptureReference, ctx: Context):
    return ctx.service.capture_reference(
        ctx.scope, command.operation_key, command.reference_file_id
    )


@router.post("/sources/web", response_model=SourceReceipt)
def capture_web(command: CaptureWeb, ctx: Context):
    return ctx.service.capture_web(ctx.scope, command.operation_key, command.url)


@router.get("/sources")
def sources(
    ctx: Context, after_id: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)
):
    result = ctx.store.list_sources(ctx.scope, after_id=after_id, limit=limit)
    return {
        "sources": result,
        "next_after_id": result[-1]["id"] if len(result) == limit else None,
    }


@router.get("/sources/{source_id}", response_model=SourceWindow)
def source_read(
    source_id: int,
    ctx: Context,
    offset: int = Query(0, ge=0),
    max_chars: int = Query(12000, ge=1, le=20000),
):
    source = ctx.store.read_source(ctx.scope, source_id)
    return {
        "source_id": source["id"],
        "project_id": source["project_id"],
        "captured_for_task_id": source["task_id"],
        "kind": source["kind"],
        "locator": source["locator"],
        "title": source["title"],
        "sha256": source["sha256"],
        "captured_at": source["captured_at"],
        "provenance": source["provenance"],
        **_window(source["content"], offset, max_chars),
    }


@router.get("/sources/{source_id}/search")
def source_search(
    source_id: int,
    ctx: Context,
    needle: str = Query(min_length=1, max_length=200),
    after_offset: int = Query(0, ge=0),
):
    source = ctx.store.read_source(ctx.scope, source_id)
    text = source["content"]
    matches = []
    position = text.find(needle, after_offset)
    while position >= 0 and len(matches) < 10:
        start = max(0, position - 200)
        end = min(len(text), position + len(needle) + 400)
        matches.append(
            {
                "match_offset": position,
                "excerpt_offset": start,
                "excerpt": text[start:end],
            }
        )
        position = text.find(needle, position + len(needle))
    return {
        "source_id": source_id,
        "sha256": source["sha256"],
        "total_chars": len(text),
        "matches": matches,
        "next_offset": position if position >= 0 else None,
        "search_kind": "exact_text",
    }


@router.post("/findings", response_model=FindingReceipt)
def finding_record(command: RecordFinding, ctx: Context):
    draft = FindingDraft(
        topic=command.topic,
        content=command.content,
        finding_type=command.finding_type,
        evidence=tuple(
            EvidenceReference(ref.source_id, ref.quote) for ref in command.evidence
        ),
    )
    return ctx.store.record_finding(ctx.scope, command.operation_key, draft)


@router.get("/findings/{finding_id}", response_model=FindingDetail)
def finding_read(finding_id: int, ctx: Context):
    row = ctx.store.read_finding(ctx.scope, finding_id)
    return {
        "finding_id": row["id"],
        **{
            key: row[key]
            for key in (
                "project_id",
                "task_id",
                "topic",
                "content",
                "finding_type",
                "status",
                "confidence",
                "evidence",
            )
        },
    }


@router.post("/reports", response_model=ReportReceipt)
def report_write(command: WriteReport, ctx: Context):
    draft = ReportDraft(
        title=command.title,
        content=command.content,
        finding_ids=tuple(command.finding_ids),
        report_type=command.report_type,
    )
    return ctx.store.write_report(ctx.scope, command.operation_key, draft)


@router.get("/reports/{artifact_id}", response_model=ReportWindow)
def report_read(
    artifact_id: int,
    ctx: Context,
    offset: int = Query(0, ge=0),
    max_chars: int = Query(12000, ge=1, le=20000),
    evidence_offset: int = Query(0, ge=0),
):
    row = ctx.store.read_report(ctx.scope, artifact_id)
    evidence = row["evidence"][evidence_offset : evidence_offset + 20]
    end = evidence_offset + len(evidence)
    return {
        "artifact_id": row["id"],
        **{
            key: row[key]
            for key in (
                "project_id",
                "title",
                "status",
                "report_type",
                "content_sha256",
                "finding_ids",
            )
        },
        "evidence": evidence,
        "total_evidence": len(row["evidence"]),
        "evidence_offset": evidence_offset,
        "next_evidence_offset": end if end < len(row["evidence"]) else None,
        **_window(row["content"], offset, max_chars),
    }
