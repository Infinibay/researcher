"""Retained role reader over canonical project-scoped finding metadata and exact windows.

This compatibility entry point has legacy host context, not a native tool grant.
Reading an old active flag or a saved review never creates review authority.
"""

from pydantic import BaseModel, ConfigDict, Field

from backend.research.models import ResearchInputError, ResearchNotFound
from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.knowledge._finding_reader import FINDING_READ_ERRORS, finding_reader


class ReadFindingsInput(BaseModel):
    """Choose a paged metadata query or one finding's complete text/evidence windows."""

    model_config = ConfigDict(extra="forbid")
    query: str | None = None
    task_id: int | None = Field(
        None,
        ge=0,
        description="Omit for current task; 0 selects all tasks inside the bound project.",
    )
    min_confidence: float | None = Field(
        None,
        ge=0,
        le=1,
        description="Optional historical declared-confidence threshold; omit to include unknowns. Not scientific certainty.",
    )
    finding_type: str | None = None
    status: str | None = None
    limit: int = Field(50, ge=1, le=200)
    after_id: int = Field(0, ge=0)
    finding_id: int | None = Field(None, ge=1)
    offset: int = Field(0, ge=0)
    max_chars: int = Field(12000, ge=1, le=20000)
    evidence_offset: int = Field(0, ge=0)


class ReadFindingsTool(InfinibayBaseTool):
    """Preserve the role tool name while sharing native finding identity and assessment semantics."""

    name: str = "read_findings"
    description: str = "Read project-scoped finding metadata or one finding by finding_id. Metadata has content_excerpt, not the full claim; use finding_id and follow next_offset/next_evidence_offset for full text/citations. Follow next_after_id for metadata. task_id=0 widens only within this project. Unknown confidence is included by default; a selected numeric threshold filters historical declarations only. Stored flags and review presence do not certify science; use read_finding_reviews for actual feedback/currentness."
    args_schema: type[BaseModel] = ReadFindingsInput

    def _run(
        self,
        query=None,
        task_id=None,
        min_confidence=None,
        finding_type=None,
        limit=50,
        after_id=0,
        finding_id=None,
        offset=0,
        max_chars=12000,
        evidence_offset=0,
        status=None,
    ):
        """Return explicit paged data or a visible failure, never global or silently truncated content."""
        try:
            store, project, task = finding_reader(self, task_id)
            if finding_id is not None:
                if (
                    query is not None
                    or finding_type is not None
                    or status is not None
                    or min_confidence is not None
                    or after_id != 0
                ):
                    raise ResearchInputError(
                        "Select a finding_id or metadata filters, not both"
                    )
                finding = store.read(
                    project,
                    finding_id,
                    offset=offset,
                    max_chars=max_chars,
                    evidence_offset=evidence_offset,
                )
                if task_id not in (None, 0) and finding["task_id"] != task:
                    raise ResearchNotFound(
                        "Finding does not belong to the selected project/task"
                    )
                return self._success(
                    {"project_id": project, "read_kind": "detail", "finding": finding}
                )
            if offset != 0 or evidence_offset != 0:
                raise ResearchInputError(
                    "Choose finding_id before paging its body or evidence"
                )
            page = store.list(
                project,
                query=query,
                task_id=task,
                min_confidence=min_confidence,
                finding_type=finding_type,
                status=status,
                after_id=after_id,
                limit=limit,
            )
            rows = page.pop("items")
            return self._success(
                {**page, "read_kind": "metadata", "findings": rows, "count": len(rows)}
            )
        except FINDING_READ_ERRORS as exc:
            return self._error(f"Finding read failed: {exc}")
