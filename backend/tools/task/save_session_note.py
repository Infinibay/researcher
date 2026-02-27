"""Tool for saving developer session notes to persist progress across interruptions."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry

VALID_PHASES = ("thinking", "locating", "implementing", "testing")


class SaveSessionNoteInput(BaseModel):
    task_id: int = Field(..., description="ID of the task being worked on")
    phase: str = Field(
        ...,
        description=f"Current work phase: {', '.join(VALID_PHASES)}",
    )
    notes_json: str = Field(
        ...,
        description="JSON string with the agent's notes (decisions, plan, files reviewed, etc.)",
    )
    last_file: str | None = Field(
        default=None,
        description="The file currently being edited, if any",
    )


class SaveSessionNoteTool(PabadaBaseTool):
    name: str = "save_session_note"
    description: str = (
        "Persist your current progress on a task so work can be resumed "
        "after interruption. Saves phase, notes, and last file as a single "
        "session record per task (upserts on subsequent calls)."
    )
    args_schema: Type[BaseModel] = SaveSessionNoteInput

    def _run(
        self,
        task_id: int,
        phase: str,
        notes_json: str,
        last_file: str | None = None,
    ) -> str:
        if phase not in VALID_PHASES:
            return self._error(
                f"Invalid phase '{phase}'. "
                f"Must be one of: {', '.join(VALID_PHASES)}"
            )

        agent_id = self._validate_agent_context()

        def _save(conn: sqlite3.Connection) -> dict:
            conn.execute(
                """\
                INSERT INTO developer_session_notes
                    (task_id, agent_id, phase, notes_json, last_file)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(task_id, agent_id) DO UPDATE SET
                    phase      = excluded.phase,
                    notes_json = excluded.notes_json,
                    last_file  = excluded.last_file,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (task_id, agent_id, phase, notes_json, last_file),
            )
            conn.commit()
            return {"task_id": task_id, "agent_id": agent_id, "phase": phase}

        result = execute_with_retry(_save)

        self._log_tool_usage(
            f"Saved session note for task #{task_id} (phase={phase})"
        )
        return self._success(result)
