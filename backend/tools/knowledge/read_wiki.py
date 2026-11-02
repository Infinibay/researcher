"""Transitional legacy wiki reader backed by explicit namespaces and recorded revisions.

The legacy agent context remains separate from native grants; this adapter does not
claim to migrate the old inference loop. Reads never select a global page implicitly.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.knowledge.wiki import WikiStore
from backend.research.models import (
    OperationConflict,
    ResearchInputError,
    ResearchNotFound,
)
from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.base.db import ensure_migrations, get_db_path


class ReadWikiInput(BaseModel):
    """Select an exact stored path or lexical search, with scope and recoverable cursors."""

    model_config = ConfigDict(extra="forbid")

    page: str | None = None
    search: str | None = None
    namespace: Literal["project", "global"] = "project"
    after_id: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    max_chars: int = Field(default=12000, ge=1, le=20000)


class ReadWikiTool(InfinibayBaseTool):
    """Keep the legacy role tool usable while sharing exact identity and revision semantics."""

    name: str = "read_wiki"
    description: str = "Read an exact wiki path, lexical search, or paged index. Choose namespace project/global explicitly; project is default and never falls back globally. Reads return id/revision/hash. Follow next_offset/next_after_id. Read complete content before editing and retain page_id/revision; a read is not a captured scientific source."
    args_schema: type[BaseModel] = ReadWikiInput

    def _run(
        self,
        page=None,
        search=None,
        namespace="project",
        after_id=0,
        limit=50,
        offset=0,
        max_chars=12000,
    ):
        """Use shared recorded wiki state; do not rewrite paths or invoke embeddings."""
        if page is not None and search is not None:
            return self._error("Select a page or search, not both")
        try:
            database = get_db_path()
            ensure_migrations(database, existing_only=True)
            store = WikiStore(database)
            if page is not None:
                return self._success(
                    store.read(
                        self.project_id,
                        page,
                        namespace=namespace,
                        offset=offset,
                        max_chars=max_chars,
                    )
                )
            result = store.list(
                self.project_id,
                namespace=namespace,
                after_id=after_id,
                limit=limit,
                query=search,
            )
            pages = result.pop("pages")
            return self._success(
                {
                    **result,
                    "results" if search is not None else "pages": pages,
                    "count": len(pages),
                }
            )
        except (ResearchInputError, ResearchNotFound, OperationConflict) as exc:
            return self._error(str(exc))
