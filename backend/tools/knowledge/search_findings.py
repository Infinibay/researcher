"""Retained semantic finding reader using the complete canonical corpus and pinned local worker."""

from pydantic import BaseModel, ConfigDict, Field

from backend.config.settings import settings
from backend.research.semantic import SemanticRetriever
from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.knowledge._finding_reader import FINDING_READ_ERRORS, finding_reader


class SearchFindingsInput(BaseModel):
    """Search natural text with explicit chunk pagination; no stored embedding or download fallback."""

    model_config = ConfigDict(extra="forbid")
    query: str = Field(
        min_length=1,
        max_length=1000,
        description="Natural-language semantic query. Use read_findings for lexical OR/AND/prefix syntax.",
    )
    threshold: float = Field(
        0.65,
        ge=0,
        le=1,
        description="Minimum chunk similarity, not scientific confidence.",
    )
    task_id: int | None = Field(
        None,
        ge=0,
        description="Omit for current task; 0 selects all tasks in this project.",
    )
    include_content: bool = Field(
        False,
        description="Include a bounded body window with next_offset; read_findings recovers the rest and citations.",
    )
    limit: int = Field(20, ge=1, le=20)
    after_rank: int = Field(0, ge=0, le=2048)
    expected_corpus_sha256: str | None = None
    expected_record_set_sha256: str | None = None


class SearchFindingsTool(InfinibayBaseTool):
    """Retain the role tool while eliminating sampled candidates and unversioned vector reuse."""

    name: str = "search_findings"
    description: str = "Search complete finding titles/bodies in the bound project/current task with prepared pinned offline assets. task_id=0 widens only within this project. Oversized corpora fail explicitly instead of sampling500rows. limit1-20 returns ranked chunks (a finding may appear twice); follow next_rank with both returned corpus fingerprints. Scores and stored confidence do not certify science. Inspect read_findings/read_finding_reviews for full context, citations and review currentness. No automatic downloads or alternate-provider fallback."
    args_schema: type[BaseModel] = SearchFindingsInput

    def _run(
        self,
        query,
        threshold=0.65,
        task_id=None,
        include_content=False,
        limit=20,
        after_rank=0,
        expected_corpus_sha256=None,
        expected_record_set_sha256=None,
    ):
        """Bind scope/configuration once and disclose results only after current corpus revalidation."""
        try:
            store, project, task = finding_reader(self, task_id)
            retriever = SemanticRetriever(settings.RETRIEVAL_ASSET_DIR)
            result = store.query(
                project,
                retriever,
                query,
                task_id=task,
                threshold=threshold,
                include_content=include_content,
                limit=limit,
                after_rank=after_rank,
                expected_corpus_sha256=expected_corpus_sha256,
                expected_record_set_sha256=expected_record_set_sha256,
            )
            return self._success(result)
        except FINDING_READ_ERRORS as exc:
            return self._error(f"Finding semantic search failed: {exc}")
