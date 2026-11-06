"""Retain historical flow observations for owner inspection; these records never resume the native runtime or transfer old approvals."""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from pydantic import BaseModel

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


def _emit_step_changed(
    flow_name: str | None,
    step: str | None,
    project_id: int,
    subflow_name: str | None = None,
    subflow_step: str | None = None,
) -> None:
    """Emit a flow_step_changed event on the global event bus."""
    try:
        from backend.flows.event_bus import FlowEvent, event_bus

        event_bus.emit(FlowEvent(
            event_type="flow_step_changed",
            project_id=project_id,
            entity_type="project",
            entity_id=project_id,
            data={
                "flow_name": flow_name,
                "step": step,
                "subflow_name": subflow_name,
                "subflow_step": subflow_step,
            },
        ))
    except Exception:
        logger.debug("Could not emit flow_step_changed event", exc_info=True)


def save_snapshot(
    project_id: int,
    flow_name: str,
    step: str,
    state: dict[str, Any] | BaseModel,
    subflow_name: str | None = None,
    subflow_step: str | None = None,
) -> None:
    """Preserve a retained controller's last observed state for inspection; this is historical material, not a native resume checkpoint."""
    try:
        state_dict = state.model_dump() if isinstance(state, BaseModel) else state
        state_str = json.dumps(state_dict, default=str)

        def _upsert(conn: sqlite3.Connection) -> None:
            conn.execute(
                """INSERT OR REPLACE INTO flow_snapshots
                   (project_id, flow_name, current_step, state_json,
                    subflow_name, subflow_step, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (project_id, flow_name, step, state_str,
                 subflow_name, subflow_step),
            )
            conn.commit()

        execute_with_retry(_upsert)
        logger.debug("Saved snapshot for project %d (step=%s)", project_id, step)

        _emit_step_changed(flow_name, step, project_id, subflow_name, subflow_step)
    except Exception:
        logger.warning(
            "Failed to save snapshot for project %d", project_id, exc_info=True
        )




def load_snapshot(project_id: int) -> dict[str, Any] | None:
    """Load the most recent snapshot for a project, or None if absent."""

    def _query(conn: sqlite3.Connection) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT * FROM flow_snapshots WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        return dict(row) if row else None

    return execute_with_retry(_query)
