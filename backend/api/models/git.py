"""Pydantic models for git resources."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RepoCreate(BaseModel):
    """Retain the implicit repository-creation request shape; compatibility guards reject its retired setup effects."""
    name: str = Field(..., min_length=1, max_length=128)
    local_path: str = Field(..., min_length=1)
    remote_url: str | None = None
    default_branch: str = Field(default="main")


class RepoResponse(BaseModel):
    """Expose registered repository metadata independently of source availability or execution authority."""
    id: int
    project_id: int
    name: str
    local_path: str
    remote_url: str | None = None
    default_branch: str
    status: str
    created_at: str | None = None


class BranchResponse(BaseModel):
    """Historical branch identity, with an unresolved repository represented explicitly as null."""
    id: int
    repo_id: int | None = None
    project_id: int
    task_id: int | None = None
    repo_name: str
    branch_name: str
    base_branch: str | None = None
    status: str
    created_by: str | None = None
    created_at: str | None = None
    merged_at: str | None = None
    last_commit_hash: str | None = None


class BranchCreate(BaseModel):
    """Retain the retired branch-creation request shape; its deprecated path does not select authoritative source."""
    task_id: int
    repo_path: str | None = Field(default=None, description="Deprecated; resolved from DB")
    base_branch: str = Field(default="main")
    repo_name: str = Field(default="default")


class PRResponse(BaseModel):
    """Historical PR metadata whose repository binding is independent of its display name."""
    id: int
    repo_id: int | None = None
    project_id: int | None = None
    task_id: int | None = None
    branch: str
    repo_name: str
    summary: str | None = None
    status: str
    reviewer: str | None = None
    comments: str | None = None
    forgejo_pr_index: int | None = None
    created_at: str | None = None
    reviewed_at: str | None = None


class PRMergeRequest(BaseModel):
    """Retain the optional merge-message shape for the retired compatibility mutation endpoint."""
    merge_message: str | None = None


class CleanupRequest(BaseModel):
    """Retain the historical cleanup request shape without granting Git deletion authority."""
    project_id: int
    repo_path: str
    delete_remote: bool = True


class BranchDetail(BaseModel):
    """Describe an observed branch name and available last-commit metadata."""
    name: str
    last_commit_sha: str | None = None
    last_commit_message: str | None = None
    last_commit_date: str | None = None
    committer_name: str | None = None


class RepoTreeEntry(BaseModel):
    """Describe a repository-relative blob or tree identity and optional byte size."""
    path: str
    type: str  # "blob" | "tree"
    sha: str
    size: int | None = None


class FileContent(BaseModel):
    """Carry a repository file body with its path, hash, byte size and optional provider link."""
    path: str
    content: str
    sha: str
    size: int
    html_url: str | None = None


class PRComment(BaseModel):
    """Expose a provider comment identity, author, body and recorded timestamp."""
    id: int
    author: str
    body: str
    created_at: str
    html_url: str | None = None


class PRCommentCreate(BaseModel):
    """Validate a nonempty comment body for the provider-comment request."""
    body: str = Field(..., min_length=1)
