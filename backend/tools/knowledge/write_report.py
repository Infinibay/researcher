"""Tool for writing research reports."""

import os
import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry, get_db_path


class WriteReportInput(BaseModel):
    title: str = Field(..., description="Report title")
    content: str = Field(..., description="Report content (markdown)")
    report_type: str = Field(
        default="research", description="Report type: 'research', 'analysis', 'summary'"
    )


class WriteReportTool(PabadaBaseTool):
    name: str = "write_report"
    description: str = (
        "Write a research report. Saves as an artifact and stores the file "
        "in the artifacts/reports directory."
    )
    args_schema: Type[BaseModel] = WriteReportInput

    def _run(
        self, title: str, content: str, report_type: str = "research"
    ) -> str:
        project_id = self.project_id
        task_id = self.task_id

        # Determine output path
        db_path = get_db_path()
        base_dir = os.path.dirname(db_path)
        reports_dir = os.path.join(base_dir, "artifacts", "reports")
        os.makedirs(reports_dir, exist_ok=True)

        # Generate filename from title
        safe_title = "".join(
            c if c.isalnum() or c in ("-", "_") else "_"
            for c in title.lower().replace(" ", "_")
        )[:80]
        file_path = os.path.join(reports_dir, f"{safe_title}.md")

        # Handle name collisions
        counter = 1
        while os.path.exists(file_path):
            file_path = os.path.join(reports_dir, f"{safe_title}_{counter}.md")
            counter += 1

        # Write file
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# {title}\n\n")
                f.write(content)
        except Exception as e:
            return self._error(f"Failed to write report: {e}")

        # Record in artifacts table
        def _record(conn: sqlite3.Connection) -> int:
            cursor = conn.execute(
                """INSERT INTO artifacts
                   (project_id, task_id, type, file_path, description)
                   VALUES (?, ?, 'report', ?, ?)""",
                (project_id, task_id, file_path, f"{report_type}: {title}"),
            )
            conn.commit()
            return cursor.lastrowid

        try:
            artifact_id = execute_with_retry(_record)
        except Exception:
            artifact_id = None

        self._log_tool_usage(f"Wrote report: {title}")
        return self._success({
            "artifact_id": artifact_id,
            "file_path": file_path,
            "title": title,
            "report_type": report_type,
        })
