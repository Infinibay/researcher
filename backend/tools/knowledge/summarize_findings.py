"""Deterministic finding counts with paged topics and explicitly historical confidence."""

from pydantic import BaseModel, ConfigDict, Field

from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.knowledge._finding_reader import FINDING_READ_ERRORS, finding_reader


class SummarizeFindingsInput(BaseModel):
    """Select a task only inside the bound project and page its topic metadata."""

    model_config = ConfigDict(extra="forbid")
    task_id: int | None = Field(
        None,
        ge=0,
        description="Omit for current task, 0 for all tasks in the bound project.",
    )
    after_id: int = Field(0, ge=0)
    limit: int = Field(50, ge=1, le=200)


class SummarizeFindingsTool(InfinibayBaseTool):
    """Reuse the canonical complete-set aggregate without LLM synthesis or confidence promotion."""

    name: str = "summarize_findings"
    description: str = "Count all findings in this project/task by type/status and report known/unknown historical confidence separately from scientific certainty. topics is a metadata page: follow next_after_id. This deterministic summary does not read full claim bodies or establish independent review; use read_findings/read_finding_reviews to inspect them."
    args_schema: type[BaseModel] = SummarizeFindingsInput

    def _run(self, task_id=None, after_id=0, limit=50):
        """Keep aggregate counts and the current topic page in the same scoped SQL snapshot."""
        try:
            store, project, task = finding_reader(self, task_id)
            return self._success(
                store.summary_page(
                    project, task_id=task, after_id=after_id, limit=limit
                )
            )
        except FINDING_READ_ERRORS as exc:
            return self._error(f"Finding summary failed: {exc}")
