"""Tool for writing/updating wiki pages."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


class WriteWikiInput(BaseModel):
    page: str = Field(..., description="Wiki page path (e.g. 'architecture/overview')")
    content: str = Field(..., description="Page content in markdown")
    title: str | None = Field(default=None, description="Page title (defaults to last path segment)")
    parent_path: str | None = Field(default=None, description="Parent page path for hierarchy")


class WriteWikiTool(PabadaBaseTool):
    name: str = "write_wiki"
    description: str = (
        "Create or update a wiki page. Pages are identified by their path "
        "and support hierarchical organization."
    )
    args_schema: Type[BaseModel] = WriteWikiInput

    def _run(
        self,
        page: str,
        content: str,
        title: str | None = None,
        parent_path: str | None = None,
    ) -> str:
        agent_id = self._validate_agent_context()
        project_id = self.project_id

        # Default title from path
        if title is None:
            title = page.split("/")[-1].replace("-", " ").replace("_", " ").title()

        def _write(conn: sqlite3.Connection) -> dict:
            existing = conn.execute(
                "SELECT id FROM wiki_pages WHERE path = ?", (page,)
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE wiki_pages
                       SET content = ?, title = ?, parent_path = ?,
                           updated_by = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE id = ?""",
                    (content, title, parent_path, agent_id, existing["id"]),
                )
                action = "updated"
                page_id = existing["id"]
            else:
                cursor = conn.execute(
                    """INSERT INTO wiki_pages
                       (project_id, path, title, content, parent_path,
                        created_by, updated_by)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (project_id, page, title, content, parent_path,
                     agent_id, agent_id),
                )
                action = "created"
                page_id = cursor.lastrowid

            # Pre-compute embedding for semantic search
            try:
                from backend.tools.base.embeddings import store_wiki_embedding
                store_wiki_embedding(conn, page_id, f"{title} {content[:500]}")
            except Exception:
                pass  # embedding is optional

            conn.commit()
            return {"page_id": page_id, "action": action}

        try:
            result = execute_with_retry(_write)
        except Exception as e:
            return self._error(f"Failed to write wiki page: {e}")

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
                    "agent_id": agent_id,
                },
            )
        )

        self._log_tool_usage(
            f"Wiki page {result['action']}: {page}"
        )
        return self._success({
            "page_id": result["page_id"],
            "path": page,
            "title": title,
            "action": result["action"],
        })
