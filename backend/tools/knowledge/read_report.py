"""Tool for reading research reports."""

import os
import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


class ReadReportInput(BaseModel):
    report_id: int | None = Field(
        default=None, description="Artifact ID of the report"
    )
    file_path: str | None = Field(
        default=None, description="Direct file path to the report"
    )


class ReadReportTool(PabadaBaseTool):
    name: str = "read_report"
    description: str = (
        "Read a research report by artifact ID or file path."
    )
    args_schema: Type[BaseModel] = ReadReportInput

    def _run(
        self, report_id: int | None = None, file_path: str | None = None
    ) -> str:
        if report_id is None and file_path is None:
            return self._error("Provide either report_id or file_path")

        # Resolve file path from report_id if needed
        if file_path is None and report_id is not None:
            def _get_path(conn: sqlite3.Connection) -> str | None:
                row = conn.execute(
                    "SELECT file_path FROM artifacts WHERE id = ? AND type = 'report'",
                    (report_id,),
                ).fetchone()
                return row["file_path"] if row else None

            try:
                file_path = execute_with_retry(_get_path)
            except Exception as e:
                return self._error(f"Failed to lookup report: {e}")

            if file_path is None:
                return self._error(f"Report with ID {report_id} not found")

        # Read file
        if not os.path.exists(file_path):
            return self._error(f"Report file not found: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return self._error(f"Failed to read report: {e}")

        return content
