"""Owner-facing artifact metadata, saved content and paged report citations."""

from __future__ import annotations

from pydantic import BaseModel

from backend.api.models.research import EvidenceResponse


class ArtifactListResponse(BaseModel):
    """Describe a saved artifact without loading its body into the catalog.

    Research title and review status are optional for legacy/non-report records.
    """

    id: int
    project_id: int | None = None
    task_id: int | None = None
    type: str
    file_path: str
    description: str | None = None
    title: str | None = None
    research_status: str | None = None
    created_at: str | None = None


class ArtifactDetailResponse(ArtifactListResponse):
    """Return the original stored artifact body alongside catalog metadata."""

    content: str | None = None


class ArtifactEvidenceResponse(BaseModel):
    """Page exact citations linked to a report within one project snapshot.

    The recorded content hash identifies the saved report; it does not assert
    that source captures are current. A null next_offset marks the final page.
    """

    artifact_id: int
    project_id: int
    content_sha256: str | None = None
    evidence: list[EvidenceResponse]
    total_evidence: int
    offset: int
    next_offset: int | None
