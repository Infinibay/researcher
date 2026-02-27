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
        "in /artifacts/reports/ (shared across all agents). Also stores "
        "full content in the database for search and cross-agent access."
    )
    args_schema: Type[BaseModel] = WriteReportInput

    def _run(
        self, title: str, content: str, report_type: str = "research"
    ) -> str:
        project_id = self.project_id
        task_id = self.task_id

        # Generate filename from title
        safe_title = "".join(
            c if c.isalnum() or c in ("-", "_") else "_"
            for c in title.lower().replace(" ", "_")
        )[:80]

        # In-pod path (shared /artifacts volume)
        pod_reports_dir = "/artifacts/reports"
        pod_file_path = f"{pod_reports_dir}/{safe_title}.md"

        # Host path — used when sandbox is disabled (local dev)
        db_path = get_db_path()
        host_base = os.path.dirname(os.path.abspath(db_path))
        host_reports_dir = os.path.join(host_base, "artifacts", "reports")
        os.makedirs(host_reports_dir, exist_ok=True)

        host_file_path = os.path.join(host_reports_dir, f"{safe_title}.md")

        # Handle name collisions on host
        counter = 1
        while os.path.exists(host_file_path):
            host_file_path = os.path.join(
                host_reports_dir, f"{safe_title}_{counter}.md"
            )
            pod_file_path = f"{pod_reports_dir}/{safe_title}_{counter}.md"
            counter += 1

        full_content = f"# {title}\n\n{content}"

        # Write file to host (works in both sandbox and non-sandbox mode)
        try:
            with open(host_file_path, "w", encoding="utf-8") as f:
                f.write(full_content)
        except Exception as e:
            return self._error(f"Failed to write report: {e}")

        # Store in DB with the pod path (consistent across all agents)
        # and the full content so other agents can read without filesystem
        def _record(conn: sqlite3.Connection) -> int:
            cursor = conn.execute(
                """INSERT INTO artifacts
                   (project_id, task_id, type, file_path, description, content)
                   VALUES (?, ?, 'report', ?, ?, ?)""",
                (
                    project_id,
                    task_id,
                    pod_file_path,
                    f"{report_type}: {title}",
                    full_content,
                ),
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
            "file_path": pod_file_path,
            "title": title,
            "report_type": report_type,
        })
