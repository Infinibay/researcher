"""Tool for updating project metadata."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry

# Map each allowed field to its pre-built UPDATE statement.
# Using static SQL strings avoids f-string interpolation in queries.
_FIELD_QUERIES = {
    "name": "UPDATE projects SET name = ? WHERE id = ?",
    "description": "UPDATE projects SET description = ? WHERE id = ?",
    "metadata_json": "UPDATE projects SET metadata_json = ? WHERE id = ?",
    "status": "UPDATE projects SET status = ? WHERE id = ?",
}

ALLOWED_FIELDS = set(_FIELD_QUERIES.keys())


class UpdateProjectInput(BaseModel):
    field: str = Field(
        ..., description=f"Field to update: {', '.join(sorted(ALLOWED_FIELDS))}"
    )
    value: str = Field(..., description="New value for the field")


class UpdateProjectTool(PabadaBaseTool):
    name: str = "update_project"
    description: str = (
        "Update a project field (name, description, metadata_json, or status)."
    )
    args_schema: Type[BaseModel] = UpdateProjectInput

    def _run(self, field: str, value: str) -> str:
        query = _FIELD_QUERIES.get(field)
        if query is None:
            return self._error(
                f"Field '{field}' not allowed. "
                f"Allowed fields: {', '.join(sorted(ALLOWED_FIELDS))}"
            )

        project_id = self._validate_project_context()

        def _update(conn: sqlite3.Connection) -> dict:
            row = conn.execute(
                "SELECT id, name FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Project {project_id} not found")

            conn.execute(query, (value, project_id))
            conn.commit()
            return {"name": row["name"]}

        try:
            result = execute_with_retry(_update)
        except ValueError as e:
            return self._error(str(e))

        self._log_tool_usage(f"Updated project {field}")
        return self._success({
            "project_id": project_id,
            "field": field,
            "updated": True,
        })
