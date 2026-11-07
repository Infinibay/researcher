"""Owner finding registry and exact captured evidence; no hidden inference or global-id reads.

Owner session protection is provided by middleware. Native tools use the separate
research routes and revalidate their host-issued project/capability authority.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from backend.knowledge.findings import FindingStore

router = APIRouter(prefix="/api", tags=["findings"])


def store(request):
    """Choose the serving store's database before consulting transitional global configuration."""
    research = getattr(request.app.state, "runtime_research_store", None)
    runtime = getattr(request.app.state, "runtime_service", None)
    if research is None and runtime is not None:
        research = runtime.research
    if research is None:
        from backend.tools.base.db import get_db_path

        database = get_db_path()
    else:
        database = research.database
    return FindingStore(database)


def selection(
    q: str | None = Query(None, min_length=1, max_length=1000),
    finding_type: str | None = None,
    status: str | None = None,
    min_confidence: float | None = Query(None, ge=0, le=1),
    task_id: int | None = Query(None, gt=0),
):
    """Translate owner query fields once, retaining every chosen filter together."""
    return {
        "query": q,
        "finding_type": finding_type,
        "status": status,
        "min_confidence": min_confidence,
        "task_id": task_id,
    }


Filters = Annotated[dict, Depends(selection)]


@router.get("/findings")
def list_findings(
    request: Request,
    filters: Filters,
    project_id: int = Query(..., gt=0),
    after_id: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Retain the old array shape with explicit excerpt/continuation fields and bounded text."""
    result = store(request).list(project_id, after_id=after_id, limit=limit, **filters)
    return [
        {
            **row,
            "content": row["content_excerpt"],
            "total_chars": row["content_chars"],
            "next_offset": len(row["content_excerpt"])
            if row["content_chars"] > len(row["content_excerpt"])
            else None,
        }
        for row in result["items"]
    ]


@router.get("/findings-index")
def finding_index(
    request: Request,
    filters: Filters,
    project_id: int = Query(..., gt=0),
    after_id: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """Expose a cursor/count envelope for the scoped metadata-only findings index."""
    return store(request).list(project_id, after_id=after_id, limit=limit, **filters)


@router.get("/findings-summary")
def finding_summary(
    request: Request, filters: Filters, project_id: int = Query(..., gt=0)
):
    """Return structured complete counts with unknown scientific confidence kept unknown."""
    return store(request).summary(project_id, **filters)


@router.get("/findings-query")
def finding_query(
    request: Request,
    project_id: int = Query(..., gt=0),
    query: str = Query(..., min_length=1, max_length=1000),
    finding_type: str | None = None,
    status: str | None = None,
    min_confidence: float | None = Query(None, ge=0, le=1),
    task_id: int | None = Query(None, gt=0),
    finding_ids: str | None = Query(None, max_length=1000),
    limit: int = Query(5, ge=1, le=20),
    after_rank: int = Query(0, ge=0, le=2048),
    expected_corpus_sha256: str | None = Query(None, pattern=r"^[0-9a-f]{64}$"),
    expected_record_set_sha256: str | None = Query(None, pattern=r"^[0-9a-f]{64}$"),
):
    """Search a complete bounded current set with the existing offline worker, never a lexical fallback."""
    from backend.knowledge.findings import corpus_unchanged, query_corpus, selected_ids
    from backend.research.retrieval_assets import RetrievalUnavailable
    from backend.runtime.auxiliary_budget import AuxiliaryBudget

    repository = store(request)
    filters = {
        "finding_type": finding_type,
        "status": status,
        "min_confidence": min_confidence,
        "task_id": task_id,
        "finding_ids": selected_ids(finding_ids),
    }
    corpus = repository.corpus(project_id, **filters)
    with AuxiliaryBudget(repository.database,project_id).bound():
        result = query_corpus(
            corpus,
            request.app.state.retrieval,
            query,
            limit=limit,
            after_rank=after_rank,
            expected_corpus_sha256=expected_corpus_sha256,
            expected_record_set_sha256=expected_record_set_sha256,
        )
    if not corpus_unchanged(corpus, repository.corpus(project_id, **filters)):
        raise RetrievalUnavailable(
            "Finding corpus changed during semantic retrieval; retry the current selection"
        )
    return {"project_id": project_id, **result}


@router.get("/findings/search")
def search_findings_semantic(
    request: Request,
    project_id: int = Query(..., gt=0),
    query: str = Query(..., min_length=1, max_length=1000),
    threshold: float = Query(0.7, ge=0, le=1),
    limit: int = Query(20, ge=1, le=20),
):
    """Retain an array-shaped adapter with real local chunk scores and explicit corpus identity."""
    result = finding_query(
        request=request,
        project_id=project_id,
        query=query,
        finding_type=None,
        status=None,
        min_confidence=None,
        task_id=None,
        finding_ids=None,
        limit=limit,
        after_rank=0,
        expected_corpus_sha256=None,
        expected_record_set_sha256=None,
    )
    found = {}
    for match in result["matches"]:
        if match["score"] < threshold or match["finding_id"] in found:
            continue
        row = store(request).read(project_id, match["finding_id"])
        found[match["finding_id"]] = {
            **row,
            "similarity": match["score"],
            "search_kind": result["search_kind"],
            "corpus_sha256": result["corpus_sha256"],
            "corpus_count": result["corpus_count"],
            "next_rank": result.get("next_rank"),
        }
    return list(found.values())


@router.get("/findings/{finding_id}")
def get_finding(
    finding_id: int,
    request: Request,
    project_id: int = Query(..., gt=0),
    offset: int = Query(0, ge=0),
    max_chars: int = Query(12000, ge=1, le=20000),
    evidence_offset: int = Query(0, ge=0),
):
    """Read bounded current body/citations only for the explicitly selected project."""
    return store(request).read(
        project_id,
        finding_id,
        offset=offset,
        max_chars=max_chars,
        evidence_offset=evidence_offset,
    )


@router.get("/findings/{finding_id}/evidence")
def finding_evidence(
    finding_id: int,
    request: Request,
    project_id: int = Query(..., gt=0),
    offset: int = Query(0, ge=0),
):
    """Page saved exact quotations independently of body windows; missing relations stay visible."""
    return store(request).evidence(project_id, finding_id, offset=offset)


@router.get("/findings/{finding_id}/legacy-sources")
def finding_legacy_sources(
    finding_id: int,
    request: Request,
    project_id: int = Query(..., gt=0),
    offset: int = Query(0, ge=0),
    max_chars: int = Query(8000, ge=1, le=20000),
):
    """Read unverified original source declarations literally with explicit continuation."""
    return store(request).legacy_sources(
        project_id, finding_id, offset=offset, max_chars=max_chars
    )


@router.get("/findings/{finding_id}/sources/{source_id}")
def finding_source(
    finding_id: int,
    source_id: int,
    request: Request,
    project_id: int = Query(..., gt=0),
    offset: int = Query(0, ge=0),
    max_chars: int = Query(12000, ge=1, le=20000),
):
    """Inspect an actually cited, hash-verified saved source rather than opening a live URL/file."""
    return store(request).source(
        project_id, finding_id, source_id, offset=offset, max_chars=max_chars
    )
