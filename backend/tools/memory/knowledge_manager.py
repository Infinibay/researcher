"""Unified knowledge management tool for agents.

Replaces SaveMemoryTool + RetrieveMemoryTool with a single tool that supports
save, search (FTS5), delete, and list operations.
"""

import sqlite3
import uuid
from typing import Literal, Type

from pydantic import BaseModel, Field, model_validator

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


class KnowledgeManagerInput(BaseModel):
    action: Literal["save", "search", "delete", "list"] = Field(
        ...,
        description=(
            "Operation to perform: "
            "'save' — store a note (upserts if key+category already exists), "
            "'search' — full-text search across notes, "
            "'delete' — remove a note by id, "
            "'list' — list notes, optionally filtered by category"
        ),
    )

    # ── save fields ──────────────────────────────────────────────────────
    content: str | None = Field(
        default=None,
        description="Note content. Required for 'save'.",
    )
    key: str | None = Field(
        default=None,
        description=(
            "Short identifier/title for the note. "
            "If omitted on save, one is auto-generated."
        ),
    )
    category: str | None = Field(
        default=None,
        description=(
            "Organizational category (e.g. 'finding', 'decision', "
            "'pattern', 'bug', 'reference'). "
            "Defaults to 'general' on save. "
            "For list: filters by category when provided, returns all if omitted."
        ),
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0–1.0). Default 1.0.",
    )

    # ── search fields ────────────────────────────────────────────────────
    query: str | None = Field(
        default=None,
        description="Full-text search query. Required for 'search'.",
    )

    # ── delete field ─────────────────────────────────────────────────────
    entry_id: int | None = Field(
        default=None,
        description="ID of the entry to delete. Required for 'delete'.",
    )

    # ── shared fields ────────────────────────────────────────────────────
    scope: Literal["agent", "project"] = Field(
        default="agent",
        description=(
            "'agent' (default) — only your own notes. "
            "'project' — notes from all agents in the project."
        ),
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Max entries to return for search/list. Default 20.",
    )

    @model_validator(mode="after")
    def validate_action_fields(self):
        if self.action == "save" and not self.content:
            raise ValueError("'content' is required for action='save'")
        if self.action == "search" and not self.query:
            raise ValueError("'query' is required for action='search'")
        if self.action == "delete" and self.entry_id is None:
            raise ValueError("'entry_id' is required for action='delete'")
        return self


class KnowledgeManagerTool(PabadaBaseTool):
    name: str = "knowledge_manager"
    description: str = (
        "Manage persistent notes and knowledge across runs. "
        "Actions: 'save' a note, 'search' with full-text query, "
        "'delete' by id, or 'list' filtered by category. "
        "Use scope='project' to access notes from all agents."
    )
    args_schema: Type[BaseModel] = KnowledgeManagerInput

    def _run(
        self,
        action: str,
        content: str | None = None,
        key: str | None = None,
        category: str | None = None,
        confidence: float = 1.0,
        query: str | None = None,
        entry_id: int | None = None,
        scope: str = "agent",
        limit: int = 20,
    ) -> str:
        agent_id = self._validate_agent_context()

        handler = {
            "save": self._save,
            "search": self._search,
            "delete": self._delete,
            "list": self._list,
        }.get(action)

        if handler is None:
            return self._error(f"Unknown action: {action}")

        # Only resolve project_id for actions that need it.
        project_id = None
        if action in ("save", "search", "list"):
            project_id = self._validate_project_context()

        try:
            return handler(
                agent_id=agent_id,
                project_id=project_id,
                content=content,
                key=key,
                category=category,
                confidence=confidence,
                query=query,
                entry_id=entry_id,
                scope=scope,
                limit=limit,
            )
        except Exception as e:
            return self._error(f"knowledge_manager/{action} failed: {e}")

    # ── save ─────────────────────────────────────────────────────────────

    def _save(self, *, agent_id, project_id, content, key, category,
              confidence, **_kw) -> str:
        if key is None:
            key = f"note_{uuid.uuid4().hex[:8]}"
        if category is None:
            category = "general"

        def _do(conn: sqlite3.Connection) -> dict:
            existing = conn.execute(
                """SELECT id FROM knowledge
                   WHERE agent_id = ? AND key = ? AND category = ?""",
                (agent_id, key, category),
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE knowledge
                       SET value = ?, confidence = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE id = ?""",
                    (content, confidence, existing["id"]),
                )
                conn.commit()
                return {"id": existing["id"], "action": "updated"}
            else:
                cur = conn.execute(
                    """INSERT INTO knowledge
                       (project_id, category, key, value, agent_id, confidence)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (project_id, category, key, content, agent_id, confidence),
                )
                conn.commit()
                return {"id": cur.lastrowid, "action": "created"}

        result = execute_with_retry(_do)
        self._log_tool_usage(
            f"Knowledge {result['action']}: [{category}] {key}"
        )
        return self._success({
            "id": result["id"],
            "key": key,
            "category": category,
            "action": result["action"],
        })

    # ── search (FTS5) ────────────────────────────────────────────────────

    def _search(self, *, agent_id, project_id, query, scope, limit,
                **_kw) -> str:
        def _do(conn: sqlite3.Connection) -> list[dict]:
            scope_condition, params = self._scope_filter(
                agent_id, project_id, scope
            )

            rows = conn.execute(
                f"""SELECT k.id, k.category, k.key, k.value,
                           k.agent_id, k.confidence,
                           k.created_at, k.updated_at
                    FROM knowledge k
                    JOIN knowledge_fts fts ON k.id = fts.rowid
                    WHERE fts.knowledge_fts MATCH ?
                      AND {scope_condition}
                    ORDER BY rank
                    LIMIT ?""",
                (query, *params, limit),
            ).fetchall()
            return [dict(r) for r in rows]

        entries = execute_with_retry(_do)
        self._log_tool_usage(f"Knowledge search: '{query}' → {len(entries)} results")
        return self._success({"entries": entries, "count": len(entries)})

    # ── delete ───────────────────────────────────────────────────────────

    def _delete(self, *, agent_id, entry_id, **_kw) -> str:
        def _do(conn: sqlite3.Connection) -> bool:
            cur = conn.execute(
                "DELETE FROM knowledge WHERE id = ? AND agent_id = ?",
                (entry_id, agent_id),
            )
            conn.commit()
            return cur.rowcount > 0

        deleted = execute_with_retry(_do)
        if not deleted:
            return self._error(
                f"Entry {entry_id} not found or not owned by this agent"
            )

        self._log_tool_usage(f"Knowledge deleted: id={entry_id}")
        return self._success({"deleted_id": entry_id})

    # ── list ─────────────────────────────────────────────────────────────

    def _list(self, *, agent_id, project_id, category, scope, limit,
              **_kw) -> str:
        def _do(conn: sqlite3.Connection) -> list[dict]:
            scope_condition, params = self._scope_filter(
                agent_id, project_id, scope
            )

            cat_filter = ""
            if category is not None:
                cat_filter = "AND k.category = ?"
                params = (*params, category)

            rows = conn.execute(
                f"""SELECT k.id, k.category, k.key, k.value,
                           k.agent_id, k.confidence,
                           k.created_at, k.updated_at
                    FROM knowledge k
                    WHERE {scope_condition} {cat_filter}
                    ORDER BY k.category, k.updated_at DESC
                    LIMIT ?""",
                (*params, limit),
            ).fetchall()
            return [dict(r) for r in rows]

        entries = execute_with_retry(_do)
        self._log_tool_usage(
            f"Knowledge list: category={category or 'all'}, {len(entries)} entries"
        )
        return self._success({"entries": entries, "count": len(entries)})

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _scope_filter(
        agent_id: str, project_id: int, scope: str
    ) -> tuple[str, tuple]:
        """Return (SQL condition, params) for agent/project scoping."""
        if scope == "project":
            return "k.project_id = ?", (project_id,)
        return "k.agent_id = ?", (agent_id,)
