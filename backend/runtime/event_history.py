"""Canonical committed event pages for owner HTTP reads and resumable live delivery."""

import json
from contextlib import closing

from backend.db.connection import connect
from backend.runtime.contracts import identity


class EventHistory:
    """Read one project in ID order and expose known retention gaps instead of hiding them."""

    def __init__(self, database):
        """Bind an existing migrated database without creating storage or execution authority."""
        self.database = str(database)

    def page(self, project_id, *, after_id=0, limit=100):
        """Return a bounded ascending snapshot or an explicit cursor reset requirement.

        Decimal string IDs preserve SQLite integer precision in browsers. Deletion
        tracking starts with migration59; earlier removals cannot be reconstructed.
        """
        identity(project_id)
        if type(after_id) is not int or not 0 <= after_id <= 9223372036854775807:
            raise ValueError("Invalid event cursor")
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("Invalid event page size")
        with closing(connect(self.database, existing_only=True)) as conn, conn:
            conn.execute("BEGIN")
            retained = conn.execute("SELECT pruned_through FROM event_retention WHERE project_id=?", (project_id,)).fetchone()
            floor = retained[0] if retained else 0
            high = max(floor, conn.execute("SELECT COALESCE(MAX(id),0) FROM events_log WHERE project_id=?", (project_id,)).fetchone()[0])
            reset = after_id < floor or after_id > high
            result = {"type": "events.page", "project_id": project_id, "after_id": str(after_id),
                      "next_after_id": str(after_id), "has_more": False, "events": [],
                      "reset_required": reset, "resume_after_id": str(floor) if reset else None,
                      "reset_reason": ("retention" if after_id < floor else "cursor_ahead") if reset else None}
            if reset:
                return result
            rows = conn.execute("SELECT * FROM events_log WHERE project_id=? AND id>? ORDER BY id ASC LIMIT ?", (project_id, after_id, limit + 1)).fetchall()
        events = []
        for row in rows[:limit]:
            try:
                data = json.loads(row["event_data_json"])
            except (ValueError, TypeError):
                data = None
            events.append({"event_id": str(row["id"]), "type": row["event_type"],
                           "project_id": project_id, "source": row["event_source"],
                           "entity_type": row["entity_type"], "entity_id": row["entity_id"],
                           "data": data if isinstance(data, dict) else None,
                           "data_unavailable": not isinstance(data, dict), "timestamp": row["created_at"]})
        result.update(events=events, has_more=len(rows) > limit,
                      next_after_id=events[-1]["event_id"] if events else str(after_id))
        return result
