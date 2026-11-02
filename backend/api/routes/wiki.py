"""Owner wiki reads/edits with explicit namespaces, revision conflicts and retained history.

Owner session/CSRF protection is supplied by the application middleware. Agent tools
use the separate grant-checked research routes; these endpoints never issue a grant.
"""

from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Query, Request

from backend.api.models.wiki import (
    WikiPageCreate,
    WikiPageResponse,
    WikiPageUpdate,
    WikiSearchResult,
)
from backend.knowledge.wiki import WikiStore
from backend.research.models import ResearchNotFound

router = APIRouter(prefix="/api", tags=["wiki"])
Namespace = Literal["project", "global"]


def store(request):
    """Use the serving database's exact identity; never bootstrap a missing wiki store."""
    research = getattr(request.app.state, "runtime_research_store", None)
    runtime = getattr(request.app.state, "runtime_service", None)
    if research is None and runtime is not None:
        research = runtime.research
    if research is None:
        from backend.tools.base.db import get_db_path

        database = get_db_path()
    else:
        database = research.database
    return WikiStore(database)


@router.get("/wiki", response_model=list[WikiPageResponse])
def list_wiki_pages(
    request: Request,
    project_id: int = Query(..., gt=0),
    namespace: Namespace = "project",
    after_id: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """Keep the legacy list shape but bound it and require an explicit global selection."""
    return store(request).list(
        project_id, namespace=namespace, after_id=after_id, limit=limit
    )["pages"]


@router.get("/wiki-index")
def wiki_index(
    request: Request,
    project_id: int = Query(..., gt=0),
    namespace: Namespace = "project",
    after_id: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    query: str | None = Query(None, min_length=1, max_length=500),
):
    """Return a recoverable index cursor and lexical query semantics to the current frontend."""
    return store(request).list(
        project_id, namespace=namespace, after_id=after_id, limit=limit, query=query
    )


def revision_response(row):
    """Return the receipt's retained revision even after its active page changes or disappears."""
    return {
        "id": row["page_id"],
        "project_id": row["project_id"],
        "namespace": row["namespace"],
        "path": row["path"],
        "title": row["title"],
        "content": row["content"],
        "parent_path": row["parent_path"],
        "revision": row["revision"],
        "sha256": row["sha256"],
        "updated_by": row["actor"],
        "updated_at": row["recorded_at"],
        "total_chars": len(row["content"]),
        "offset": 0,
        "next_offset": None,
    }


@router.post("/wiki", response_model=WikiPageResponse, status_code=201)
def create_wiki_page(body: WikiPageCreate, request: Request):
    """Create once at revision zero; retry returns the committed revision, not current content."""
    wiki = store(request)
    receipt = wiki.write(
        project_id=body.project_id,
        namespace=body.namespace,
        path=body.path,
        title=body.title or body.path.rsplit("/", 1)[-1] or body.path,
        content=body.content,
        parent_path=body.parent_path,
        expected_revision=0,
        actor="owner",
        operation_key=body.operation_key or uuid4().hex,
    )
    return revision_response(
        wiki.read_revision(
            body.project_id,
            receipt["page_id"],
            receipt["revision"],
            namespace=body.namespace,
        )
    )


@router.get("/wiki/{path:path}", response_model=WikiPageResponse)
def get_wiki_page(
    path: str,
    request: Request,
    project_id: int = Query(..., gt=0),
    namespace: Namespace = "project",
    offset: int = Query(0, ge=0),
    max_chars: int = Query(200000, ge=1, le=200000),
):
    """Read an exact logical path as stored, including leading slashes, without rewriting identity."""
    return store(request).read(
        project_id, path, namespace=namespace, offset=offset, max_chars=max_chars
    )


@router.put("/wiki/{path:path}", response_model=WikiPageResponse)
def update_wiki_page(
    path: str,
    body: WikiPageUpdate,
    request: Request,
    project_id: int = Query(..., gt=0),
    namespace: Namespace = "project",
):
    """Apply a complete observed edit; reconcile the original receipt before reading current state."""
    wiki = store(request)
    receipt = wiki.write(
        project_id=project_id,
        namespace=namespace,
        path=path,
        title=body.title,
        content=body.content,
        parent_path=body.parent_path,
        page_id=body.page_id,
        expected_revision=body.expected_revision,
        actor="owner",
        operation_key=body.operation_key or uuid4().hex,
    )
    return revision_response(
        wiki.read_revision(
            project_id, receipt["page_id"], receipt["revision"], namespace=namespace
        )
    )


@router.delete("/wiki/{path:path}", status_code=204)
def delete_wiki_page(
    path: str,
    request: Request,
    project_id: int = Query(..., gt=0),
    namespace: Namespace = "project",
    expected_revision: int = Query(..., gt=0),
    page_id: int = Query(..., gt=0),
    operation_key: str | None = Query(None, min_length=1, max_length=128),
):
    """Delete only the named scope/revision; retained versions remain recoverable by their ids."""
    store(request).delete(
        project_id,
        path,
        namespace=namespace,
        expected_revision=expected_revision,
        page_id=page_id,
        actor="owner",
        operation_key=operation_key or uuid4().hex,
    )


@router.get("/wiki-search", response_model=list[WikiSearchResult])
def search_wiki(
    q: str,
    request: Request,
    project_id: int = Query(..., gt=0),
    namespace: Namespace = "project",
):
    """Preserve the legacy result list with explicit lexical semantics and scope identity."""
    pages = store(request).list(project_id, namespace=namespace, query=q, limit=100)[
        "pages"
    ]
    return [{**page, "snippet": None} for page in pages]


@router.get("/wiki-revisions/{page_id}")
def wiki_revisions(
    page_id: int,
    request: Request,
    project_id: int = Query(..., gt=0),
    namespace: Namespace = "project",
    before_revision: int | None = Query(None, gt=0),
    limit: int = Query(20, ge=1, le=100),
):
    """Page retained revision metadata newest first; an absent active page does not erase history."""
    from backend.knowledge.wiki import namespace_filter

    wiki = store(request)
    where, params = namespace_filter(project_id, namespace)
    if before_revision is not None:
        where += " AND revision<?"
        params.append(before_revision)
    with wiki.transaction() as conn:
        rows = conn.execute(
            f"SELECT page_id,revision,path,title,sha256,actor,recorded_at,origin FROM wiki_revisions WHERE {where} AND page_id=? ORDER BY revision DESC LIMIT ?",
            (*params, page_id, limit + 1),
        ).fetchall()
    selected = [dict(row) for row in rows[:limit]]
    if not selected and before_revision is None:
        raise ResearchNotFound("Wiki revision history not found in this namespace")
    return {
        "revisions": selected,
        "namespace": namespace,
        "next_before_revision": selected[-1]["revision"] if len(rows) > limit else None,
    }


@router.get("/wiki-revisions/{page_id}/{revision}")
def wiki_revision_read(
    page_id: int,
    revision: int,
    request: Request,
    project_id: int = Query(..., gt=0),
    namespace: Namespace = "project",
    offset: int = Query(0, ge=0),
    max_chars: int = Query(12000, ge=1, le=20000),
):
    """Read one retained version with bounded text for comparison, never overwrite the editor."""
    row = store(request).read_revision(
        project_id, page_id, revision, namespace=namespace
    )
    text = row.pop("content")
    content = text[offset : offset + max_chars]
    end = offset + len(content)
    return {
        **row,
        "content": content,
        "offset": offset,
        "total_chars": len(text),
        "next_offset": end if end < len(text) else None,
    }
