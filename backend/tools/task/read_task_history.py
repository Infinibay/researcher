"""Tool for reading the full history/timeline of a task."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


class ReadTaskHistoryInput(BaseModel):
    task_id: int = Field(..., description="ID of the task to read history for")
    limit: int = Field(
        default=50,
        description="Maximum number of timeline entries to return",
    )


class ReadTaskHistoryTool(PabadaBaseTool):
    name: str = "read_task_history"
    description: str = (
        "Read the full timeline of a task: status changes, events, and "
        "comments in chronological order. Useful for understanding what "
        "happened with a task (rejections, feedback, who worked on it)."
    )
    args_schema: Type[BaseModel] = ReadTaskHistoryInput

    def _run(self, task_id: int, limit: int = 50) -> str:
        def _query(conn: sqlite3.Connection) -> dict:
            # Get events for this task
            events = conn.execute(
                """\
                SELECT event_type, event_source, event_data_json, created_at
                FROM events_log
                WHERE entity_type = 'task' AND entity_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (task_id, limit),
            ).fetchall()

            # Get comments for this task
            comments = conn.execute(
                """\
                SELECT author, comment_type, content, created_at
                FROM task_comments
                WHERE task_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (task_id, limit),
            ).fetchall()

            # Merge into chronological timeline
            timeline = []
            for e in events:
                timeline.append({
                    "type": "event",
                    "event_type": e["event_type"],
                    "source": e["event_source"],
                    "data": e["event_data_json"],
                    "timestamp": e["created_at"],
                })
            for c in comments:
                content = c["content"] or ""
                if len(content) > 300:
                    content = content[:297] + "..."
                timeline.append({
                    "type": "comment",
                    "author": c["author"],
                    "comment_type": c["comment_type"],
                    "content": content,
                    "timestamp": c["created_at"],
                })

            # Sort by timestamp
            timeline.sort(key=lambda x: x["timestamp"] or "")

            # Trim to limit
            timeline = timeline[:limit]

            return {
                "task_id": task_id,
                "timeline": timeline,
                "count": len(timeline),
            }

        result = execute_with_retry(_query)
        self._log_tool_usage(
            f"Read history for task #{task_id} ({result['count']} entries)"
        )
        return self._success(result)
