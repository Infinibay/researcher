"""Tool for creating epics."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.base.db import execute_with_retry


class CreateEpicInput(BaseModel):
    title: str = Field(..., description="Epic title")
    description: str = Field(
        ...,
        description=(
            "Epic description. Must contain three sections: "
            "(1) Measurable Objective — concrete success criteria; "
            "(2) Problem It Solves — the user/system pain this epic addresses; "
            "(3) Definition of Done — conditions for full epic completion."
        ),
    )
    priority: int = Field(default=2, ge=1, le=5, description="Priority 1-5")


class CreateEpicTool(InfinibayBaseTool):
    name: str = "create_epic"
    description: str = (
        "Create a new epic for organizing related tasks. "
        "Epics group milestones and provide high-level project structure."
    )
    args_schema: Type[BaseModel] = CreateEpicInput

    def _run(self, title: str, description: str, priority: int = 2) -> str:
        project_id = self._validate_project_context()
        created_by = self.agent_id or "orchestrator"

        # --- Auto-complete epics whose tasks are all resolved ---
        def _auto_complete_resolved(conn: sqlite3.Connection) -> None:
            """Mark epics as completed if all their tasks are done/cancelled/failed."""
            candidates = conn.execute(
                """SELECT e.id
                   FROM epics e
                   WHERE e.project_id = ? AND e.status NOT IN ('completed', 'cancelled')
                     AND EXISTS (SELECT 1 FROM tasks t WHERE t.epic_id = e.id)
                     AND NOT EXISTS (
                         SELECT 1 FROM tasks t
                         WHERE t.epic_id = e.id
                           AND t.status NOT IN ('done', 'cancelled', 'failed')
                     )""",
                (project_id,),
            ).fetchall()
            for row in candidates:
                conn.execute(
                    "UPDATE epics SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (row["id"],),
                )
            if candidates:
                conn.commit()

        execute_with_retry(_auto_complete_resolved)

        # --- Hard limit on active epics ---
        from backend.config.settings import settings

        def _count_open(conn: sqlite3.Connection) -> int:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM epics WHERE project_id = ? AND status NOT IN ('completed', 'cancelled')",
                (project_id,),
            ).fetchone()
            return row["cnt"]

        open_count = execute_with_retry(_count_open)
        if open_count >= settings.MAX_ACTIVE_EPICS:
            return self._error(
                f"Cannot create epic: {open_count} open epics already exist "
                f"(limit: {settings.MAX_ACTIVE_EPICS}). Complete or close existing "
                f"epics before creating new ones."
            )

        # --- Semantic dedup check ---
        def _fetch_existing(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                "SELECT id, title FROM epics WHERE project_id = ?",
                (project_id,),
            ).fetchall()
            return [{"id": r["id"], "title": r["title"]} for r in rows]

        try:
            existing = execute_with_retry(_fetch_existing)
            if existing:
                from backend.tools.base.dedup import find_semantic_duplicate

                match = find_semantic_duplicate(
                    title, existing, settings.DEDUP_SIMILARITY_THRESHOLD,
                )
                if match:
                    return self._error(
                        f"Semantic duplicate detected: existing epic "
                        f"'{match['title']}' (ID: {match['id']}) is "
                        f"{match['similarity']:.0%} similar to '{title}'. "
                        f"Use the existing epic instead of creating a new one."
                    )
        except Exception:
            pass  # dedup is best-effort; don't block creation

        def _create(conn: sqlite3.Connection) -> int:
            cursor = conn.execute(
                """INSERT INTO epics
                   (project_id, title, description, status, priority, created_by)
                   VALUES (?, ?, ?, 'open', ?, ?)""",
                (project_id, title, description, priority, created_by),
            )
            conn.commit()
            return cursor.lastrowid

        try:
            epic_id = execute_with_retry(_create)
        except Exception as e:
            return self._error(f"Failed to create epic: {e}")

        self._log_tool_usage(f"Created epic #{epic_id}: {title}")
        return self._success({
            "epic_id": epic_id,
            "title": title,
            "status": "open",
            "priority": priority,
        })
