"""Tool for recording research findings."""

import json
import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry

FINDING_TYPES = ("observation", "hypothesis", "experiment", "proof", "conclusion")


class RecordFindingInput(BaseModel):
    title: str = Field(..., description="Finding title/topic")
    content: str = Field(..., description="Detailed finding content")
    confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Confidence level (0.0 to 1.0)"
    )
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    finding_type: str = Field(
        default="observation",
        description=f"Finding type: {', '.join(FINDING_TYPES)}",
    )
    sources: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )


class RecordFindingTool(PabadaBaseTool):
    name: str = "record_finding"
    description: str = (
        "Record a research finding with confidence level and sources. "
        "Findings are created as 'provisional' and remain so until the "
        "Research Reviewer validates or rejects them."
    )
    args_schema: Type[BaseModel] = RecordFindingInput

    def _run(
        self,
        title: str,
        content: str,
        confidence: float = 0.5,
        tags: list[str] | None = None,
        finding_type: str = "observation",
        sources: list[str] | None = None,
    ) -> str:
        if tags is None:
            tags = []
        if sources is None:
            sources = []

        if finding_type not in FINDING_TYPES:
            return self._error(
                f"Invalid finding_type '{finding_type}'. "
                f"Must be one of: {', '.join(FINDING_TYPES)}"
            )

        agent_id = self._validate_agent_context()
        project_id = self.project_id
        task_id = self.task_id
        agent_run_id = self.agent_run_id

        if task_id is None:
            return self._error("No task_id in context. Findings must be associated with a task.")

        def _record(conn: sqlite3.Connection) -> int:
            cursor = conn.execute(
                """INSERT INTO findings
                   (project_id, task_id, agent_run_id, topic, content,
                    sources_json, confidence, agent_id, status, finding_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'provisional', ?)""",
                (
                    project_id, task_id, agent_run_id, title, content,
                    json.dumps(sources), confidence, agent_id, finding_type,
                ),
            )
            conn.commit()
            return cursor.lastrowid

        try:
            finding_id = execute_with_retry(_record)
        except Exception as e:
            return self._error(f"Failed to record finding: {e}")

        self._log_tool_usage(
            f"Recorded finding #{finding_id}: {title[:60]} "
            f"(confidence={confidence})"
        )
        return self._success({
            "finding_id": finding_id,
            "title": title,
            "finding_type": finding_type,
            "confidence": confidence,
            "status": "provisional",
        })
