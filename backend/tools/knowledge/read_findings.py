"""Tool for reading/searching research findings."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


class ReadFindingsInput(BaseModel):
    query: str | None = Field(
        default=None, description="Full-text search query across findings"
    )
    min_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Minimum confidence filter"
    )
    finding_type: str | None = Field(
        default=None, description="Filter by finding type"
    )
    limit: int = Field(default=50, ge=1, le=200, description="Max results")


class ReadFindingsTool(PabadaBaseTool):
    name: str = "read_findings"
    description: str = (
        "Read and search research findings. Supports full-text search "
        "and filtering by confidence and type."
    )
    args_schema: Type[BaseModel] = ReadFindingsInput

    def _run(
        self,
        query: str | None = None,
        min_confidence: float = 0.0,
        finding_type: str | None = None,
        limit: int = 50,
    ) -> str:
        project_id = self.project_id

        def _read(conn: sqlite3.Connection) -> list[dict]:
            if query:
                # Use FTS5 for full-text search
                conditions = ["f.confidence >= ?"]
                params: list = [min_confidence]

                if project_id:
                    conditions.append("f.project_id = ?")
                    params.append(project_id)
                if finding_type:
                    conditions.append("f.finding_type = ?")
                    params.append(finding_type)

                where = " AND ".join(conditions)
                params.append(limit)

                rows = conn.execute(
                    f"""SELECT f.id, f.topic, f.content, f.confidence,
                               f.agent_id, f.status, f.finding_type,
                               f.sources_json, f.validation_method,
                               f.reproducibility_score, f.created_at
                        FROM findings f
                        JOIN findings_fts fts ON f.id = fts.rowid
                        WHERE fts.findings_fts MATCH ?
                          AND {where}
                        ORDER BY f.confidence DESC
                        LIMIT ?""",
                    [query] + params,
                ).fetchall()
            else:
                conditions = ["confidence >= ?"]
                params = [min_confidence]

                if project_id:
                    conditions.append("project_id = ?")
                    params.append(project_id)
                if finding_type:
                    conditions.append("finding_type = ?")
                    params.append(finding_type)

                where = " AND ".join(conditions)
                params.append(limit)

                rows = conn.execute(
                    f"""SELECT id, topic, content, confidence,
                               agent_id, status, finding_type,
                               sources_json, validation_method,
                               reproducibility_score, created_at
                        FROM findings
                        WHERE {where}
                        ORDER BY confidence DESC
                        LIMIT ?""",
                    params,
                ).fetchall()

            return [dict(r) for r in rows]

        try:
            findings = execute_with_retry(_read)
        except Exception as e:
            return self._error(f"Failed to read findings: {e}")

        return self._success({"findings": findings, "count": len(findings)})
