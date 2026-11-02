"""Transitional project wiki writer with observed identity/revision and no hidden embeddings.

The owner/native APIs use the same records, but this old role adapter still uses its
legacy context and informational event bus. It does not confer native grant semantics.
"""

from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from backend.knowledge.wiki import WikiStore
from backend.research.models import (
    OperationConflict,
    ResearchInputError,
    ResearchNotFound,
)
from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.base.db import ensure_migrations, get_db_path


class WriteWikiInput(BaseModel):
    """Create with revision zero, or supply the observed page id/revision and complete edit."""

    model_config = ConfigDict(extra="forbid")

    page: str
    content: str
    title: str | None = None
    parent_path: str | None = None
    expected_revision: int = Field(default=0, ge=0)
    page_id: int | None = Field(default=None, gt=0)
    operation_key: str | None = Field(default=None, min_length=1, max_length=128)


class WriteWikiTool(InfinibayBaseTool):
    """Migrate legacy writes to the same project-only guarded records without provider calls."""

    name: str = "write_wiki"
    description: str = "Create/update only this project wiki. Creation: expected_revision0, page_id null. To edit, first read the complete page and supply its exact page_id/revision plus full title/content/parent_path; null parent clears it. Preserve operation_key on retry. A conflict requires comparison, not silent rebase. No implicit global write or hidden embeddings. Notes are context, not scientific acceptance."
    args_schema: type[BaseModel] = WriteWikiInput

    def _run(
        self,
        page,
        content,
        title=None,
        parent_path=None,
        expected_revision=0,
        page_id=None,
        operation_key=None,
    ):
        """Persist a guarded revision/receipt, then emit only the retained legacy advisory notice."""
        project_id = self.project_id
        actor = self.agent_id or "unknown"
        title = title or page.rsplit("/", 1)[-1] or page
        try:
            database = get_db_path()
            ensure_migrations(database, existing_only=True)
            result = WikiStore(database).write(
                project_id=project_id,
                namespace="project",
                path=page,
                title=title,
                content=content,
                parent_path=parent_path,
                page_id=page_id,
                expected_revision=expected_revision,
                actor=actor,
                operation_key=operation_key or uuid4().hex,
            )
        except (ResearchInputError, ResearchNotFound, OperationConflict) as exc:
            return self._error(str(exc))
        from backend.flows.event_listeners import FlowEvent, event_bus

        event_bus.emit(
            FlowEvent(
                event_type="wiki_updated",
                project_id=project_id,
                entity_type="wiki_page",
                entity_id=result["page_id"],
                data={
                    "path": page,
                    "title": title,
                    "action": result["action"],
                    "agent_id": actor,
                    "operation_key": result["operation_key"],
                    "revision": result["revision"],
                    "authority": "advisory_notification_only",
                },
            )
        )
        self._log_tool_usage(f"Wiki page {result['action']}: {page}")
        return self._success({**result, "path": page, "title": title})
