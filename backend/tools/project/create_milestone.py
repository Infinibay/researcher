"""Tool for creating milestones."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.base.db import execute_with_retry


class CreateMilestoneInput(BaseModel):
    title: str = Field(..., description="Milestone title")
    description: str = Field(
        ...,
        description=(
            "Milestone description. Must contain two sections: "
            "(1) Objective Verification Criterion — a single, testable condition proving completion; "
            "(2) Incremental Value Delivered — what the team/user gains when this milestone closes."
        ),
    )
    epic_id: int = Field(..., description="Parent epic ID")
    due_date: str | None = Field(
        default=None, description="Due date in YYYY-MM-DD format"
    )


class CreateMilestoneTool(InfinibayBaseTool):
    name: str = "create_milestone"
    description: str = (
        "Create a new milestone within an epic. "
        "Milestones track progress toward epic completion."
    )
    args_schema: Type[BaseModel] = CreateMilestoneInput

    def _run(
        self,
        title: str,
        description: str,
        epic_id: int,
        due_date: str | None = None,
    ) -> str:
        project_id = self._validate_project_context()

        # --- Hard limit on milestones per epic ---
        from backend.config.settings import settings

        def _count_existing(conn: sqlite3.Connection) -> int:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM milestones WHERE epic_id = ?",
                (epic_id,),
            ).fetchone()
            return row["cnt"]

        existing_count = execute_with_retry(_count_existing)
        if existing_count >= settings.MAX_MILESTONES_PER_EPIC:
            return self._error(
                f"Cannot create milestone: epic {epic_id} already has "
                f"{existing_count} milestones (limit: {settings.MAX_MILESTONES_PER_EPIC})."
            )

        # --- Semantic dedup check ---
        def _fetch_existing(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                "SELECT id, title FROM milestones WHERE epic_id = ?",
                (epic_id,),
            ).fetchall()
            return [{"id": r["id"], "title": r["title"]} for r in rows]

        try:
            existing = execute_with_retry(_fetch_existing)
            if existing:
                from backend.config.settings import settings
                from backend.tools.base.dedup import find_semantic_duplicate

                match = find_semantic_duplicate(
                    title, existing, settings.DEDUP_SIMILARITY_THRESHOLD,
                )
                if match:
                    return self._error(
                        f"Semantic duplicate detected: existing milestone "
                        f"'{match['title']}' (ID: {match['id']}) is "
                        f"{match['similarity']:.0%} similar to '{title}'. "
                        f"Use the existing milestone instead of creating a new one."
                    )
        except Exception:
            pass  # dedup is best-effort; don't block creation

        def _create(conn: sqlite3.Connection) -> int:
            # Verify epic exists
            row = conn.execute(
                "SELECT id, project_id FROM epics WHERE id = ?", (epic_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Epic {epic_id} not found")
            if row["project_id"] != project_id:
                raise ValueError(f"Epic {epic_id} does not belong to current project")

            cursor = conn.execute(
                """INSERT INTO milestones
                   (project_id, epic_id, title, description, status, due_date)
                   VALUES (?, ?, ?, ?, 'open', ?)""",
                (project_id, epic_id, title, description, due_date),
            )
            conn.commit()
            return cursor.lastrowid

        try:
            milestone_id = execute_with_retry(_create)
        except ValueError as e:
            return self._error(str(e))
        except Exception as e:
            return self._error(f"Failed to create milestone: {e}")

        self._log_tool_usage(f"Created milestone #{milestone_id}: {title}")
        return self._success({
            "milestone_id": milestone_id,
            "title": title,
            "epic_id": epic_id,
            "status": "open",
            "due_date": due_date,
        })
