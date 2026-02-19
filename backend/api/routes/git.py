"""REST endpoints for git operations — repos, branches, PRs, cleanup."""

from __future__ import annotations

import base64
import json
import re
import sqlite3

from fastapi import APIRouter, HTTPException, Query

from backend.api.models.git import (
    BranchCreate,
    BranchDetail,
    BranchResponse,
    CleanupRequest,
    FileContent,
    PRComment,
    PRCommentCreate,
    PRMergeRequest,
    PRResponse,
    RepoCreate,
    RepoResponse,
    RepoTreeEntry,
)
from backend.config.settings import settings
from backend.git import (
    branch_service,
    cleanup_service,
    pr_service,
    repository_manager,
)
from backend.git.forgejo_client import forgejo_client
from backend.tools.base.db import execute_with_retry

router = APIRouter(prefix="/api/git", tags=["git"])


# ── Repositories ──────────────────────────────────────────────────────────────


@router.get("/repos", response_model=list[RepoResponse])
async def list_repos(project_id: int = Query(...)):
    """List active repositories for a project."""
    repos = repository_manager.list_repos(project_id)
    return [RepoResponse(**r) for r in repos]


@router.post("/repos", response_model=RepoResponse, status_code=201)
async def create_repo(project_id: int = Query(...), body: RepoCreate = ...):
    """Initialize or clone a repository."""
    repo = repository_manager.init_repo(
        project_id=project_id,
        name=body.name,
        local_path=body.local_path,
        remote_url=body.remote_url,
        default_branch=body.default_branch,
    )

    # Log event
    _log_event(project_id, "repo_created", "api", "repository", repo["id"], {
        "name": body.name, "local_path": body.local_path,
    })

    return RepoResponse(**repo)


@router.delete("/repos/{name}", status_code=204)
async def archive_repo(name: str, project_id: int = Query(...)):
    """Archive (soft-delete) a repository."""
    archived = repository_manager.archive_repo(project_id, name)
    if not archived:
        raise HTTPException(
            status_code=404,
            detail=f"Repository '{name}' not found for project {project_id}",
        )

    _log_event(project_id, "repo_archived", "api", "repository", None, {"name": name})


# ── Branches ──────────────────────────────────────────────────────────────────


@router.get("/branches", response_model=list[BranchResponse])
async def list_branches(
    project_id: int = Query(...),
    repo_name: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    """List branches for a project with optional filters."""
    branches = branch_service.list_branches(project_id, repo_name=repo_name, status=status)
    return [BranchResponse(**b) for b in branches]


@router.post("/branches", response_model=BranchResponse, status_code=201)
async def create_branch(body: BranchCreate):
    """Create a git branch for a task.

    Generates a branch name from the task title, runs ``git checkout -b``,
    registers the branch in the DB, and updates ``tasks.branch_name``.
    """
    branch_name = branch_service.create_branch_for_task(
        task_id=body.task_id,
        repo_path=body.repo_path,
        base_branch=body.base_branch,
        repo_name=body.repo_name,
    )

    branch = branch_service.get_branch_for_task(body.task_id)
    if not branch:
        raise HTTPException(status_code=500, detail="Branch created but not found in DB")

    _log_event(
        branch["project_id"], "branch_created", "api", "branch", branch["id"],
        {"branch_name": branch_name, "task_id": body.task_id},
    )

    return BranchResponse(**branch)


# ── Pull Requests ─────────────────────────────────────────────────────────────


@router.get("/prs", response_model=list[PRResponse])
async def list_prs(
    project_id: int = Query(...),
    status: str | None = Query(default=None),
):
    """List pull requests for a project."""
    prs = pr_service.list_prs(project_id, status=status)
    return [PRResponse(**p) for p in prs]


@router.get("/prs/{pr_id}", response_model=PRResponse)
async def get_pr(pr_id: int):
    """Get a single pull request."""
    pr = pr_service.get_pr(pr_id)
    if not pr:
        raise HTTPException(status_code=404, detail=f"PR {pr_id} not found")
    return PRResponse(**pr)


@router.post("/prs/{pr_id}/merge", response_model=PRResponse)
async def merge_pr(pr_id: int, body: PRMergeRequest):
    """Merge a pull request."""
    pr = pr_service.get_pr(pr_id)
    if not pr:
        raise HTTPException(status_code=404, detail=f"PR {pr_id} not found")

    # Resolve repo_path from repositories table
    repo_path = _resolve_repo_path(pr.get("project_id"), pr["repo_name"])

    pr_service.merge_pr(pr_id, repo_path, merge_message=body.merge_message)

    _log_event(
        pr.get("project_id"), "pr_merged", "api", "code_review", pr_id,
        {"branch": pr["branch"]},
    )

    updated = pr_service.get_pr(pr_id)
    return PRResponse(**updated)


@router.post("/prs/{pr_id}/close", response_model=PRResponse)
async def close_pr(pr_id: int):
    """Close/abandon a pull request."""
    pr = pr_service.get_pr(pr_id)
    if not pr:
        raise HTTPException(status_code=404, detail=f"PR {pr_id} not found")

    pr_service.close_pr(pr_id)

    _log_event(
        pr.get("project_id"), "pr_closed", "api", "code_review", pr_id,
        {"branch": pr["branch"]},
    )

    updated = pr_service.get_pr(pr_id)
    return PRResponse(**updated)


# ── Cleanup ───────────────────────────────────────────────────────────────────


@router.post("/cleanup")
async def trigger_cleanup(body: CleanupRequest):
    """Trigger branch cleanup for merged branches."""
    cleaned = cleanup_service.cleanup_merged_branches(
        project_id=body.project_id,
        repo_path=body.repo_path,
        delete_remote=body.delete_remote,
    )
    return {"cleaned": cleaned, "project_id": body.project_id}


# ── Forgejo Repo Browsing ─────────────────────────────────────────────────


@router.get("/repos/{repo_name}/branches", response_model=list[BranchDetail])
async def list_repo_branches(
    repo_name: str,
    project_id: int = Query(...),
):
    """List branches for a repository via Forgejo, with commit metadata."""
    if not settings.FORGEJO_API_URL or not _is_forgejo_remote(project_id, repo_name):
        # Fallback to DB-only branches when Forgejo is not configured or
        # the remote is not a Forgejo instance.
        db_branches = branch_service.list_branches(project_id, repo_name=repo_name)
        return [BranchDetail(name=b["branch_name"]) for b in db_branches]

    owner_repo = _require_forgejo_remote(project_id, repo_name)

    branches = forgejo_client.get_branches(owner_repo)
    return [
        BranchDetail(
            name=b["name"],
            last_commit_sha=b.get("commit", {}).get("id"),
            last_commit_message=b.get("commit", {}).get("message"),
            last_commit_date=b.get("commit", {}).get("timestamp"),
            committer_name=b.get("commit", {}).get("committer", {}).get("name")
            if b.get("commit", {}).get("committer")
            else None,
        )
        for b in branches
    ]


@router.get("/repos/{repo_name}/tree", response_model=list[RepoTreeEntry])
async def get_repo_tree(
    repo_name: str,
    project_id: int = Query(...),
    ref: str = Query(default="main"),
):
    """Get the file tree for a repository at a given ref.

    *ref* can be a branch name, tag, or commit SHA (7-40 hex chars).
    """
    owner_repo = _require_forgejo_remote(project_id, repo_name)

    # Resolve ref to a tree SHA.  If the ref already looks like a commit SHA
    # (7-40 hex characters), use it directly as a fallback when the branch
    # lookup fails.
    _SHA_RE = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)
    sha: str | None = None
    try:
        sha = forgejo_client.get_ref_sha(owner_repo, ref)
    except (ValueError, KeyError):
        if _SHA_RE.match(ref):
            sha = ref
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Ref '{ref}' not found and is not a valid commit SHA",
            )

    tree_resp = forgejo_client.get_tree(owner_repo, sha, recursive=True)
    entries = tree_resp.get("tree", [])

    result = [
        RepoTreeEntry(
            path=e["path"],
            type=e["type"],
            sha=e["sha"],
            size=e.get("size"),
        )
        for e in entries
    ]
    # Sort: trees first, then blobs, alphabetical within each group
    result.sort(key=lambda e: (0 if e.type == "tree" else 1, e.path))
    return result


@router.get("/repos/{repo_name}/contents", response_model=FileContent)
async def get_file_contents(
    repo_name: str,
    project_id: int = Query(...),
    path: str = Query(...),
    ref: str = Query(default="main"),
):
    """Get the decoded contents of a file from Forgejo."""
    owner_repo = _require_forgejo_remote(project_id, repo_name)

    resp = forgejo_client.get_contents(owner_repo, path, ref)
    raw_b64 = resp.get("content", "")
    # Forgejo base64 may contain newlines
    raw_bytes = base64.b64decode(raw_b64.replace("\n", ""))
    try:
        decoded = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        decoded = "[binary file]"

    return FileContent(
        path=path,
        content=decoded,
        sha=resp["sha"],
        size=resp.get("size", len(raw_bytes)),
        html_url=resp.get("html_url"),
    )


# ── PR Comments ──────────────────────────────────────────────────────────


@router.get("/prs/{pr_id}/comments", response_model=list[PRComment])
async def list_pr_comments(pr_id: int):
    """List Forgejo comments on a pull request."""
    _require_forgejo()

    pr = pr_service.get_pr(pr_id)
    if not pr:
        raise HTTPException(status_code=404, detail=f"PR {pr_id} not found")

    pr_index = pr.get("forgejo_pr_index")
    if pr_index is None:
        raise HTTPException(
            status_code=400,
            detail="PR has no Forgejo index; was it created via the Forgejo API?",
        )

    owner_repo = _require_forgejo_remote(pr.get("project_id"), pr["repo_name"])

    comments = forgejo_client.get_pr_comments(owner_repo, pr_index)
    return [
        PRComment(
            id=c["id"],
            author=c.get("user", {}).get("login", "unknown"),
            body=c.get("body", ""),
            created_at=c.get("created_at", ""),
            html_url=c.get("html_url"),
        )
        for c in comments
    ]


@router.post("/prs/{pr_id}/comments", response_model=PRComment, status_code=201)
async def create_pr_comment(pr_id: int, body: PRCommentCreate):
    """Post a comment on a pull request via Forgejo."""
    _require_forgejo()

    pr = pr_service.get_pr(pr_id)
    if not pr:
        raise HTTPException(status_code=404, detail=f"PR {pr_id} not found")

    pr_index = pr.get("forgejo_pr_index")
    if pr_index is None:
        raise HTTPException(
            status_code=400,
            detail="PR has no Forgejo index; was it created via the Forgejo API?",
        )

    owner_repo = _require_forgejo_remote(pr.get("project_id"), pr["repo_name"])

    c = forgejo_client.create_pr_comment(owner_repo, pr_index, body.body)

    _log_event(
        pr.get("project_id"), "pr_comment_added", "api", "code_review", pr_id,
        {"author": "api"},
    )

    return PRComment(
        id=c["id"],
        author=c.get("user", {}).get("login", "unknown"),
        body=c.get("body", ""),
        created_at=c.get("created_at", ""),
        html_url=c.get("html_url"),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _require_forgejo() -> None:
    """Raise HTTP 400 if ``FORGEJO_API_URL`` is not configured."""
    if not settings.FORGEJO_API_URL:
        raise HTTPException(
            status_code=400,
            detail="Forgejo is not configured (PABADA_FORGEJO_API_URL is unset)",
        )


def _is_forgejo_remote(project_id: int | None, repo_name: str) -> bool:
    """Return ``True`` when the repository's ``remote_url`` points at Forgejo."""
    if not settings.FORGEJO_API_URL or project_id is None:
        return False
    remote_url = _get_remote_url(project_id, repo_name)
    if not remote_url:
        return False
    # Compare the host portion of FORGEJO_API_URL against the remote_url.
    # FORGEJO_API_URL is e.g. "http://localhost:3000/api/v1"
    # remote_url   is e.g. "http://localhost:3000/pabada/myrepo.git"
    from urllib.parse import urlparse

    api_host = urlparse(settings.FORGEJO_API_URL).netloc
    remote_host = urlparse(remote_url).netloc
    return api_host == remote_host


def _require_forgejo_remote(project_id: int | None, repo_name: str) -> str:
    """Validate Forgejo is configured and the repo is a Forgejo remote.

    Returns the ``owner/repo`` string on success.  Raises HTTP 400 otherwise.
    """
    _require_forgejo()
    owner_repo = _resolve_owner_repo(project_id, repo_name)
    if owner_repo is None:
        raise HTTPException(
            status_code=400,
            detail="Repository has no remote_url configured",
        )
    if not _is_forgejo_remote(project_id, repo_name):
        raise HTTPException(
            status_code=400,
            detail="Repository remote is not a Forgejo instance",
        )
    return owner_repo


def _resolve_repo_path(project_id: int | None, repo_name: str) -> str:
    """Look up the local_path for a repo from the repositories table."""
    if project_id is None:
        raise HTTPException(
            status_code=400, detail="Cannot resolve repo path without project_id",
        )

    def _query(conn: sqlite3.Connection) -> str | None:
        row = conn.execute(
            "SELECT local_path FROM repositories WHERE project_id = ? AND name = ?",
            (project_id, repo_name),
        ).fetchone()
        return row["local_path"] if row else None

    path = execute_with_retry(_query)
    if not path:
        raise HTTPException(
            status_code=404,
            detail=f"Repository '{repo_name}' not found for project {project_id}",
        )
    return path


def _get_remote_url(project_id: int, repo_name: str) -> str | None:
    """Look up the ``remote_url`` for a repo from the repositories table."""

    def _query(conn: sqlite3.Connection) -> str | None:
        row = conn.execute(
            "SELECT remote_url FROM repositories WHERE project_id = ? AND name = ?",
            (project_id, repo_name),
        ).fetchone()
        return row["remote_url"] if row else None

    return execute_with_retry(_query)


def _resolve_owner_repo(project_id: int | None, repo_name: str) -> str | None:
    """Derive ``owner/repo`` from the repository's ``remote_url``.

    Returns ``None`` when the repository has no remote configured (so
    callers can fall back to local-only behaviour).
    """
    if project_id is None:
        return None
    try:
        return pr_service._resolve_owner_repo(project_id, repo_name)
    except ValueError:
        return None


def _log_event(
    project_id: int | None,
    event_type: str,
    event_source: str,
    entity_type: str,
    entity_id: int | None,
    event_data: dict,
) -> None:
    """Best-effort event logging to events_log."""
    if project_id is None:
        return
    try:
        def _insert(conn: sqlite3.Connection) -> None:
            conn.execute(
                """INSERT INTO events_log
                       (project_id, event_type, event_source, entity_type,
                        entity_id, event_data_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (project_id, event_type, event_source, entity_type,
                 entity_id, json.dumps(event_data)),
            )
            conn.commit()

        execute_with_retry(_insert)
    except Exception:
        pass
