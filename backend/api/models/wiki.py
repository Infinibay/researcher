"""Owner wiki commands name their scope and observed revision; content remains untrusted Markdown."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WikiCommand(BaseModel):
    """Bound an optional legacy retry key; current clients keep a stable key across lost receipts."""

    model_config = ConfigDict(extra="forbid")
    operation_key: str | None = Field(
        default=None, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$"
    )


class WikiPageCreate(WikiCommand):
    """Create a page in an explicit owner-selected namespace; no fallback or overwrite."""

    project_id: int = Field(strict=True, gt=0)
    namespace: Literal["project", "global"] = "project"
    path: str = Field(min_length=1, max_length=512)
    title: str | None = Field(default=None, max_length=1200)
    content: str = Field(default="", max_length=200000)
    parent_path: str | None = Field(default=None, max_length=512)


class WikiPageUpdate(WikiCommand):
    """Name the observed page identity/revision and complete document state for a guarded save."""

    page_id: int = Field(strict=True, gt=0)
    expected_revision: int = Field(strict=True, gt=0)
    title: str = Field(min_length=1, max_length=1200)
    content: str = Field(max_length=200000)
    parent_path: str | None = Field(default=None, max_length=512)


class WikiPageResponse(BaseModel):
    """Expose scope/revision/hash plus bounded content; embedding bytes never leave storage."""

    id: int
    project_id: int | None
    namespace: Literal["project", "global"]
    path: str
    title: str
    content: str | None = None
    parent_path: str | None = None
    created_by: str | None = None
    updated_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    revision: int
    sha256: str
    total_chars: int | None = None
    offset: int | None = None
    next_offset: int | None = None


class WikiSearchResult(BaseModel):
    """Legacy lexical-search result still identifies namespace and exact page revision."""

    id: int
    path: str
    title: str
    namespace: Literal["project", "global"]
    revision: int
    snippet: str | None = None
    updated_at: str | None = None
