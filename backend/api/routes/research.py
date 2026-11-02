"""Project-bound research tools; no arbitrary SQL, paths or model-side grants."""

import asyncio
from typing import Literal

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.responses import JSONResponse

from backend.api.models.questions import AskUser
from backend.api.models.research import (
    CapturePaper,
    CaptureReference,
    CaptureWeb,
    CaptureWiki,
    CaptureWikiCollection,
    FindingDetail,
    FindingReceipt,
    ProposeResult,
    RecordFinding,
    RecordReview,
    ReportReceipt,
    ReportWindow,
    SourceReceipt,
    SourceWindow,
    WriteReport,
    WriteWiki,
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
    ResultDraft,
    ReviewCheck,
    ReviewDecision,
    SourceTooLarge,
    SourceUnavailable,
)
from backend.research.provenance import (
    intersecting_units,
    provenance_summary,
    structure_page,
)
from backend.research.retrieval_assets import RetrievalBusy, RetrievalUnavailable

router = APIRouter(prefix="/api/research-tools", tags=["research-tools"])


@router.get("/review-subject")
async def read_review_subject(
    ctx: Context,
    offset: int = Query(0, ge=0),
    max_chars: int = Query(12000, ge=1, le=20000),
):
    """Page only the authenticated reviewer's exact admitted subject."""
    return await asyncio.to_thread(
        ctx.store.read_review_subject, ctx.scope, offset=offset, max_chars=max_chars
    )


@router.post("/review-decisions", status_code=201)
async def record_review(command: RecordReview, ctx: Context):
    """Keep actor, attempt, target and subject version fixed by the stored grant."""
    draft = ReviewDecision(
        command.verdict,
        command.rationale,
        tuple(
            ReviewCheck(c.criterion, c.outcome, c.explanation) for c in command.checks
        ),
        tuple(EvidenceReference(e.source_id, e.quote) for e in command.evidence),
        tuple(command.limitations),
    )
    return await asyncio.to_thread(
        ctx.store.record_review, ctx.scope, command.operation_key, draft
    )


@router.post("/result-proposals", status_code=201)
async def propose_result(command: ProposeResult, ctx: Context):
    """Freeze only an actual admitted author's selected report and evidence versions."""
    draft = ResultDraft(
        tuple(command.report_ids), command.summary, tuple(command.limitations)
    )
    return await asyncio.to_thread(
        ctx.store.propose_result, ctx.scope, command.operation_key, draft
    )


@router.post("/questions", status_code=201)
async def ask_user(command: AskUser, ctx: Context, request: Request):
    """Record material questions and close the current turn before waiting for owner input."""
    from backend.api.routes.runs import service

    runtime = service(request)
    receipt = await asyncio.to_thread(
        runtime.questions.ask, ctx.scope, command.operation_key, command.domain()
    )
    runtime.question_requested(receipt["run_id"], receipt["attempt_id"])
    return receipt


def install_research_errors(app: FastAPI):
    """Map scoped domain failures to explicit HTTP errors without retrying effects."""
    for error, status, code in [
        (RetrievalUnavailable, 503, "retrieval_unavailable"),
        (RetrievalBusy, 429, "retrieval_busy"),
        (ResearchForbidden, 403, "scope_forbidden"),
        (ResearchNotFound, 404, "research_not_found"),
        (OperationConflict, 409, "operation_conflict"),
        (ResearchInputError, 422, "invalid_research_input"),
        (InvalidEvidence, 422, "invalid_evidence"),
        (SourceTooLarge, 413, "source_too_large"),
        (SourceUnavailable, 422, "source_unavailable"),
    ]:

        async def handle(request: Request, exc: Exception, _status=status, _code=code):
            """Keep the registered exception's status/code bound to its own handler."""
            return JSONResponse(
                status_code=_status,
                content={"error": str(exc), "code": _code, "detail": str(exc)},
            )

        app.add_exception_handler(error, handle)


def _window(text, offset, max_chars):
    """Return a character window with an explicit continuation offset, never silent truncation."""
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
    """List this grant's project attachments without exposing their filesystem paths."""
    return {
        "project_id": ctx.scope.project_id,
        "references": ctx.store.list_references(ctx.scope),
    }


@router.post("/sources/reference", response_model=SourceReceipt)
def capture_reference(command: CaptureReference, ctx: Context):
    """Acquire an attachment under the current grant and reuse its committed receipt."""
    return ctx.service.capture_reference(
        ctx.scope, command.operation_key, command.reference_file_id
    )


@router.post("/sources/web", response_model=SourceReceipt)
def capture_web(command: CaptureWeb, ctx: Context):
    """Capture a public source with scoped authority and retry-safe intent identity."""
    return ctx.service.capture_web(ctx.scope, command.operation_key, command.url)


@router.post("/sources/paper", response_model=SourceReceipt)
def capture_paper(command: CapturePaper, ctx: Context):
    """Capture a supplied paper identifier with existing grant, retry and PDF limits."""
    return ctx.service.capture_paper(
        ctx.scope,
        command.operation_key,
        url=command.url,
        doi=command.doi,
        arxiv_id=command.arxiv_id,
    )


@router.get("/sources")
def sources(
    ctx: Context,
    request: Request,
    after_id: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """Page saved source metadata inside the credential-bound project."""
    result = ctx.store.list_sources(ctx.scope, after_id=after_id, limit=limit)
    return {
        "sources": result,
        "retrieval": {
            "literal": {"method": "exact_text"},
            "semantic": request.app.state.retrieval.status(),
        },
        "next_after_id": result[-1]["id"] if len(result) == limit else None,
    }


@router.get("/sources/{source_id}", response_model=SourceWindow)
def source_read(
    source_id: int,
    ctx: Context,
    offset: int = Query(0, ge=0),
    max_chars: int = Query(12000, ge=1, le=20000),
):
    """Return one captured revision, provenance and an explicit unread text tail."""
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
        "provenance": provenance_summary(source["provenance"]),
        **_window(source["content"], offset, max_chars),
    }


@router.get("/sources/{source_id}/units")
def source_structure(
    source_id: int,
    ctx: Context,
    after_index: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """Recover bounded normalized CSV/JSON/XML/DOCX locators under the same source grant."""
    source = ctx.store.read_source(ctx.scope, source_id)
    return {
        "source_id": source_id,
        "sha256": source["sha256"],
        **structure_page(source["provenance"], after_index=after_index, limit=limit),
    }


@router.get("/sources/{source_id}/search")
def source_search(
    source_id: int,
    ctx: Context,
    needle: str = Query(min_length=1, max_length=200),
    after_offset: int = Query(0, ge=0),
):
    """Find exact case-sensitive text in a snapshot; missing matches are not semantic absence."""
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
                "unit_indices": intersecting_units(source["provenance"], start, end),
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


@router.get("/sources/{source_id}/query")
def source_query(
    source_id: int,
    ctx: Context,
    request: Request,
    query: str = Query(min_length=1, max_length=1000),
    limit: int = Query(5, ge=1, le=20),
    after_rank: int = Query(0, ge=0, le=2048),
):
    """Rank every source chunk with local embeddings, revalidating authority before disclosure."""
    source = ctx.store.read_source(ctx.scope, source_id)
    with request.app.state.live_grants.operation(ctx.scope.grant_id) as cancelled:
        result = request.app.state.retrieval.query(
            source, query, limit=limit, after_rank=after_rank, cancelled=cancelled
        )
        current = ctx.store.read_source(ctx.scope, source_id)
        if (
            current["sha256"] != source["sha256"]
            or current["content"] != source["content"]
        ):
            raise RetrievalUnavailable("Saved source changed during semantic retrieval")
        if cancelled.is_set():
            raise ResearchForbidden("Semantic query authority was withdrawn")
        return result


@router.get("/findings")
def finding_list(
    ctx: Context,
    q: str | None = Query(None, min_length=1, max_length=1000),
    finding_type: str | None = None,
    status: str | None = None,
    min_confidence: float | None = Query(None, ge=0, le=1),
    for_task_id: int | None = Query(None, gt=0),
    after_id: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """List bound-project metadata; combine lexical/type/status/historical-confidence filters."""
    return ctx.store.list_findings(
        ctx.scope,
        query=q,
        finding_type=finding_type,
        status=status,
        min_confidence=min_confidence,
        task_id=for_task_id,
        after_id=after_id,
        limit=limit,
    )


@router.get("/findings-summary")
def finding_summary(
    ctx: Context,
    q: str | None = Query(None, min_length=1, max_length=1000),
    finding_type: str | None = None,
    status: str | None = None,
    min_confidence: float | None = Query(None, ge=0, le=1),
    for_task_id: int | None = Query(None, gt=0),
):
    """Count the complete selected set without synthesizing claims or averaging scientific certainty."""
    return ctx.store.summarize_findings(
        ctx.scope,
        query=q,
        finding_type=finding_type,
        status=status,
        min_confidence=min_confidence,
        task_id=for_task_id,
    )


@router.get("/findings-query")
def finding_query(
    ctx: Context,
    request: Request,
    query: str = Query(min_length=1, max_length=1000),
    finding_type: str | None = None,
    status: str | None = None,
    min_confidence: float | None = Query(None, ge=0, le=1),
    for_task_id: int | None = Query(None, gt=0),
    finding_ids: str | None = Query(None, max_length=1000),
    limit: int = Query(5, ge=1, le=20),
    after_rank: int = Query(0, ge=0, le=2048),
    expected_corpus_sha256: str | None = Query(None, pattern=r"^[0-9a-f]{64}$"),
    expected_record_set_sha256: str | None = Query(None, pattern=r"^[0-9a-f]{64}$"),
):
    """Rank complete scoped finding text, then revalidate the exact set and live authority."""
    from backend.knowledge.findings import corpus_unchanged, query_corpus, selected_ids

    selection = {
        "finding_type": finding_type,
        "status": status,
        "min_confidence": min_confidence,
        "task_id": for_task_id,
        "finding_ids": selected_ids(finding_ids),
    }
    corpus = ctx.store.finding_corpus(ctx.scope, **selection)
    with request.app.state.live_grants.operation(ctx.scope.grant_id) as cancelled:
        result = query_corpus(
            corpus,
            request.app.state.retrieval,
            query,
            limit=limit,
            after_rank=after_rank,
            expected_corpus_sha256=expected_corpus_sha256,
            expected_record_set_sha256=expected_record_set_sha256,
            cancelled=cancelled,
        )
        current = ctx.store.finding_corpus(ctx.scope, **selection)
        if not corpus_unchanged(corpus, current):
            raise RetrievalUnavailable(
                "Finding corpus changed during semantic retrieval; retry the current selection"
            )
        if cancelled.is_set():
            raise ResearchForbidden("Semantic query authority was withdrawn")
        return result


@router.get("/findings/{finding_id}/reviews")
def finding_reviews(
    finding_id: int,
    ctx: Context,
    request_id: int | None = Query(None, gt=0),
    part: Literal["decision", "subject"] = "decision",
    after_id: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    max_chars: int = Query(12000, ge=1, le=20000),
):
    """Read review feedback without exposing owner admission or choosing another project."""
    return ctx.store.read_reviews(
        ctx.scope,
        finding_id,
        request_id=request_id,
        part=part,
        after_id=after_id,
        limit=limit,
        offset=offset,
        max_chars=max_chars,
    )


@router.post("/findings", response_model=FindingReceipt)
def finding_record(command: RecordFinding, ctx: Context):
    """Persist a provisional finding only after checking its exact saved-source quotations."""
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
def finding_read(
    finding_id: int,
    ctx: Context,
    offset: int = Query(0, ge=0),
    max_chars: int = Query(12000, ge=1, le=20000),
    evidence_offset: int = Query(0, ge=0),
):
    """Read explicit claim/evidence windows; stored flags and confidence retain their actual provenance."""
    row = ctx.store.read_finding(
        ctx.scope,
        finding_id,
        offset=offset,
        max_chars=max_chars,
        evidence_offset=evidence_offset,
    )
    return {"finding_id": row["id"], **row}


@router.post("/reports", response_model=ReportReceipt)
def report_write(command: WriteReport, ctx: Context):
    """Persist a canonical draft linked to findings without accepting or publishing it."""
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
    """Read report text and citations using independent bounded continuation offsets."""
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


@router.get("/wiki")
def wiki_list(
    ctx: Context,
    namespace: Literal["project", "global"] = "project",
    after_id: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    query: str | None = Query(None, min_length=1, max_length=500),
):
    """List one namespace and optional lexical search, with stable cursor and grant checks."""
    return ctx.store.wiki_list(
        ctx.scope, namespace=namespace, after_id=after_id, limit=limit, query=query
    )


@router.post("/wiki")
def wiki_write(command: WriteWiki, ctx: Context):
    """Apply one observed project wiki edit; the model cannot select actor/project/global write."""
    return ctx.store.wiki_write(
        ctx.scope,
        command.operation_key,
        **command.model_dump(exclude={"operation_key"}),
    )


@router.get("/wiki/{path:path}")
def wiki_read(
    path: str,
    ctx: Context,
    namespace: Literal["project", "global"] = "project",
    offset: int = Query(0, ge=0),
    max_chars: int = Query(12000, ge=1, le=20000),
):
    """Read a bounded explicitly scoped page without implying a captured source or validation."""
    return ctx.store.wiki_read(
        ctx.scope, path, namespace=namespace, offset=offset, max_chars=max_chars
    )


@router.post("/sources/wiki", response_model=SourceReceipt)
def capture_wiki(command: CaptureWiki, ctx: Context):
    """Turn one named retained wiki revision into immutable exact-quotation source evidence."""
    return ctx.store.capture_wiki(
        ctx.scope,
        command.operation_key,
        page_id=command.page_id,
        revision=command.revision,
        namespace=command.namespace,
    )


@router.post("/sources/wiki-collection", response_model=SourceReceipt)
def capture_wiki_collection(command: CaptureWikiCollection, ctx: Context):
    """Capture a bounded explicit corpus into the existing source/semantic pipeline; never silently sample."""
    return ctx.store.capture_wiki_collection(
        ctx.scope,
        command.operation_key,
        members=[member.model_dump() for member in command.members],
    )
