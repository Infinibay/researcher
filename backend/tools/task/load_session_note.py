"""Tool for loading developer session notes to resume interrupted work."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.base.db import execute_with_retry


class LoadSessionNoteInput(BaseModel):
    task_id: int = Field(..., description="ID of the task to load the session for")


class LoadSessionNoteTool(InfinibayBaseTool):
    name: str = "load_session_note"
    description: str = (
        "Retrieve previously saved session notes for a task so you can "
        "resume interrupted work. Returns the saved phase, notes, and "
        "last file, or indicates no prior session exists."
    )
    args_schema: Type[BaseModel] = LoadSessionNoteInput

    def _run(self, task_id: int) -> str:
        agent_id = self._validate_agent_context()

        def _load(conn: sqlite3.Connection) -> dict | None:
            row = conn.execute(
                """\
                SELECT phase, notes_json, last_file, updated_at
                FROM developer_session_notes
                WHERE task_id = ? AND agent_id = ?
                """,
                (task_id, agent_id),
            ).fetchone()
            if not row:
                return None
            return dict(row)

        result = execute_with_retry(_load)

        if result is None:
            return self._success({
                "found": False,
                "message": "No previous session found for this task. Starting fresh.",
            })

        return self._success({
            "found": True,
            "phase": result["phase"],
            "notes_json": result["notes_json"],
            "last_file": result["last_file"],
            "updated_at": result["updated_at"],
        })
