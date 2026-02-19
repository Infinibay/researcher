"""Pydantic models for git resources."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RepoCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    local_path: str = Field(..., min_length=1)
    remote_url: str | None = None
    default_branch: str = Field(default="main")


class RepoResponse(BaseModel):
    id: int
    project_id: int
    name: str
    local_path: str
    remote_url: str | None = None
    default_branch: str
    status: str
    created_at: str | None = None


class BranchResponse(BaseModel):
    id: int
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
    task_id: int
    repo_path: str = Field(..., min_length=1)
    base_branch: str = Field(default="main")
    repo_name: str = Field(default="default")


class PRResponse(BaseModel):
    id: int
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
    merge_message: str | None = None


class CleanupRequest(BaseModel):
    project_id: int
    repo_path: str
    delete_remote: bool = True


class BranchDetail(BaseModel):
    name: str
    last_commit_sha: str | None = None
    last_commit_message: str | None = None
    last_commit_date: str | None = None
    committer_name: str | None = None


class RepoTreeEntry(BaseModel):
    path: str
    type: str  # "blob" | "tree"
    sha: str
    size: int | None = None


class FileContent(BaseModel):
    path: str
    content: str
    sha: str
    size: int
    html_url: str | None = None


class PRComment(BaseModel):
    id: int
    author: str
    body: str
    created_at: str
    html_url: str | None = None


class PRCommentCreate(BaseModel):
    body: str = Field(..., min_length=1)
