"""Scoped deterministic cross-source lookup with explicit partial coverage and review provenance."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.knowledge.search import KnowledgeSearchStore
from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.knowledge._finding_reader import FINDING_READ_ERRORS, finding_reader


class SearchKnowledgeInput(BaseModel):
    """Search selected source kinds; a source error is not evidence of an empty corpus."""

    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=1000)
    sources: list[Literal["findings", "wiki", "reference_files", "reports"]] = Field(
        default_factory=lambda: ["findings", "wiki", "reference_files", "reports"],
        min_length=1,
        max_length=4,
    )
    limit: int = Field(20, ge=1, le=100)
    min_confidence: float | None = Field(
        None,
        ge=0,
        le=1,
        description="Optional historical declaration threshold for findings; omit to retain unknowns.",
    )
    namespace: Literal["project", "global"] = "project"
    cursors: dict[str, int] = Field(
        default_factory=dict,
        description="Per-source next_after_id values from coverage; stable id pagination.",
    )


class SearchKnowledgeTool(InfinibayBaseTool):
    """Retain the old role lookup while sharing canonical findings and disclosing source failures."""

    name: str = "search_knowledge"
    description: str = "Lexical search inside the bound project across selected findings, wiki, reference-file metadata and report text. Unknown finding confidence is included unless an explicit historical threshold is selected. Results are bounded previews with source identity, not evidence that full documents were read. coverage reports each requested source as searched/failed plus its cursor; partial or failed is not no matches. Wiki namespace project/global is explicit, with no implicit global fallback. Read findings and their reviews before claiming scientific support."
    args_schema: type[BaseModel] = SearchKnowledgeInput

    def _run(
        self,
        query,
        sources=None,
        limit=20,
        min_confidence=None,
        namespace="project",
        cursors=None,
    ):
        """Keep source errors visible while paging stable identities in one project-scoped snapshot."""
        try:
            store, project, _ = finding_reader(self, 0)
            return self._success(
                KnowledgeSearchStore(store.database).query(
                    project,
                    query,
                    sources=sources,
                    limit=limit,
                    min_confidence=min_confidence,
                    namespace=namespace,
                    cursors=cursors,
                )
            )
        except FINDING_READ_ERRORS as exc:
            return self._error(f"Knowledge search failed: {exc}")
