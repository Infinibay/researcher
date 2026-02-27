"""Tool for updating project metadata."""

import logging
import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)

# Map each allowed field to its pre-built UPDATE statement.
# Using static SQL strings avoids f-string interpolation in queries.
_FIELD_QUERIES = {
    "name": "UPDATE projects SET name = ? WHERE id = ?",
    "description": "UPDATE projects SET description = ? WHERE id = ?",
    "metadata_json": "UPDATE projects SET metadata_json = ? WHERE id = ?",
    "status": "UPDATE projects SET status = ? WHERE id = ?",
}

ALLOWED_FIELDS = set(_FIELD_QUERIES.keys())

# Minimum word-overlap similarity required when changing description.
# Below this threshold, the update is rejected as a scope deviation.
_MIN_DESCRIPTION_SIMILARITY = 0.30


def _word_overlap_similarity(a: str, b: str) -> float:
    """Compute Jaccard similarity between the word sets of two strings."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


class UpdateProjectInput(BaseModel):
    field: str = Field(
        ..., description=f"Field to update: {', '.join(sorted(ALLOWED_FIELDS))}"
    )
    value: str = Field(..., description="New value for the field")
    force: bool = Field(
        default=False,
        description=(
            "Force the update even if it deviates significantly from the "
            "original project scope. Only use this if you are certain the "
            "change is correct."
        ),
    )


class UpdateProjectTool(PabadaBaseTool):
    name: str = "update_project"
    description: str = (
        "Update a project field (name, description, metadata_json, or status). "
        "For description changes, the new value must be similar to the original "
        "project description (>30% word overlap) unless force=True."
    )
    args_schema: Type[BaseModel] = UpdateProjectInput

    def _run(self, field: str, value: str, force: bool = False) -> str:
        query = _FIELD_QUERIES.get(field)
        if query is None:
            return self._error(
                f"Field '{field}' not allowed. "
                f"Allowed fields: {', '.join(sorted(ALLOWED_FIELDS))}"
            )

        project_id = self._validate_project_context()

        def _update(conn: sqlite3.Connection) -> dict:
            # Check if original_description column exists
            cols = [r[1] for r in conn.execute("PRAGMA table_info(projects)").fetchall()]
            has_original_desc = "original_description" in cols

            if has_original_desc:
                row = conn.execute(
                    "SELECT id, name, description, original_description FROM projects WHERE id = ?",
                    (project_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT id, name, description FROM projects WHERE id = ?",
                    (project_id,),
                ).fetchone()
            if not row:
                raise ValueError(f"Project {project_id} not found")

            old_value = None

            # Guardrail: prevent description/name drift from original scope
            if field in ("description", "name") and not force:
                original_desc = (
                    (row["original_description"] if has_original_desc else None)
                    or row["description"]
                    or ""
                )
                if original_desc and value:
                    similarity = _word_overlap_similarity(original_desc, value)
                    if similarity < _MIN_DESCRIPTION_SIMILARITY:
                        raise ValueError(
                            f"Rejected: new {field} has only {similarity:.0%} word overlap "
                            f"with the original project description (minimum {_MIN_DESCRIPTION_SIMILARITY:.0%}). "
                            f"This looks like a scope deviation. If you are certain this is "
                            f"correct, call again with force=True."
                        )

            # Capture old value for logging
            if field == "description":
                old_value = row["description"]
            elif field == "name":
                old_value = row["name"]

            conn.execute(query, (value, project_id))

            # Set original_description on first description update if not yet set
            if field == "description" and has_original_desc and not row["original_description"]:
                conn.execute(
                    "UPDATE projects SET original_description = ? WHERE id = ?",
                    (value, project_id),
                )

            conn.commit()
            return {"name": row["name"], "old_value": old_value}

        try:
            result = execute_with_retry(_update)
        except ValueError as e:
            return self._error(str(e))

        old_value = result.get("old_value")

        # Log prominent change for description/name
        if field in ("description", "name") and old_value is not None:
            logger.warning(
                "Project %d %s changed: '%s' → '%s' (by agent %s, force=%s)",
                project_id, field,
                (old_value[:100] + "...") if len(old_value or "") > 100 else old_value,
                (value[:100] + "...") if len(value) > 100 else value,
                self.agent_id, force,
            )

        # Emit event for activity feed
        try:
            from backend.flows.event_listeners import FlowEvent, event_bus

            event_bus.emit(FlowEvent(
                event_type="project_metadata_changed",
                project_id=project_id,
                entity_type="project",
                entity_id=project_id,
                data={
                    "field": field,
                    "old_value": (old_value[:500] if old_value else None),
                    "new_value": value[:500],
                    "agent_id": self.agent_id,
                    "forced": force,
                },
            ))
        except Exception:
            pass  # Non-critical

        self._log_tool_usage(f"Updated project {field}")
        return self._success({
            "project_id": project_id,
            "field": field,
            "updated": True,
        })
