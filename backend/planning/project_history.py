"""Capture bounded project history as attributed planning data, without replaying old snapshots, assignments, approvals or native sessions."""

import hashlib
import json

MAX_SNAPSHOT_BYTES = 128000
MAX_FIELD_BYTES = 64000
MAX_TASKS = 256


def capture_project_history(conn, project_id, planning_task_id, sources, origins):
    """Extend one admission's frozen sources with observed old business fields and task labels; exclusions are explicit and originals remain unchanged."""
    rows = conn.execute(
        "SELECT id,type,status,title FROM tasks WHERE project_id=? AND id<>? ORDER BY id LIMIT ?",
        (project_id, planning_task_id, MAX_TASKS),
    ).fetchall()
    total = conn.execute(
        "SELECT count(*) FROM tasks WHERE project_id=? AND id<>?", (project_id, planning_task_id)
    ).fetchone()[0]
    inventory = json.dumps([dict(row) for row in rows], ensure_ascii=False, sort_keys=True)
    history = {
        "task_inventory": {
            "total": total, "captured": 0, "complete": False,
            "status_authority": "Observed labels are not proof of native acceptance or current execution.",
        },
        "legacy_snapshot": None,
        "limits": [],
    }
    if len(inventory.encode()) <= MAX_SNAPSHOT_BYTES:
        sources["project_tasks"] = inventory
        origins["project_tasks"] = "project_task_inventory"
        history["task_inventory"].update(captured=len(rows), complete=len(rows) == total)
        if len(rows) < total:
            history["limits"].append("Task inventory includes only the first 256 IDs; other work remains unexamined. Do not infer it is absent.")
    else:
        history["limits"].append("Task inventory exceeds 128000 bytes; no task text was captured. Inspect the owner workspace before relying on its absence.")
    row = conn.execute(
        """SELECT id,flow_name,current_step,updated_at,length(CAST(state_json AS BLOB)) AS bytes,
        CASE WHEN length(CAST(state_json AS BLOB))<=? THEN state_json END AS material
        FROM flow_snapshots WHERE project_id=?""", (MAX_SNAPSHOT_BYTES, project_id)
    ).fetchone()
    if row is None:
        return history
    metadata = {key: row[key] for key in ("id", "flow_name", "current_step", "updated_at", "bytes")}
    history["legacy_snapshot"] = metadata
    if row["material"] is None:
        metadata["state"] = "excluded_size_limit"
        history["limits"].append("Stored legacy snapshot exceeds 128000 bytes and was not read; its requirements, plan and ideas remain unknown, not empty.")
        return history
    metadata["sha256"] = hashlib.sha256(row["material"].encode()).hexdigest()
    try:
        state = json.loads(row["material"])
    except (ValueError, RecursionError):
        metadata["state"] = "invalid_json"
        history["limits"].append("Legacy snapshot is unreadable JSON; its contents remain unknown and preserved.")
        return history
    if not isinstance(state, dict):
        metadata["state"] = "invalid_shape"
        history["limits"].append("Legacy snapshot is not an object; no business fields were inferred.")
        return history
    metadata["state"] = "observed"
    metadata["source_keys"] = []
    for field in ("requirements", "plan", "ideas", "consolidated_ideas", "selected_ideas"):
        value = state.get(field)
        if value is None or value == "" or value == []:
            continue
        if not isinstance(value, (str, list, dict)):
            history["limits"].append(f"Legacy field {field} has an unsupported shape and was not interpreted.")
            continue
        content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
        try:
            size = len(content.encode())
        except UnicodeEncodeError:
            history["limits"].append(f"Legacy field {field} contains invalid UTF-8 text; it remains preserved and was not interpreted.")
            continue
        if size > MAX_FIELD_BYTES:
            history["limits"].append(f"Legacy field {field} exceeds 64000 bytes; it remains preserved but was not supplied or truncated.")
            continue
        key = f"legacy_snapshot:{row['id']}:{field}"
        sources[key] = content
        origins[key] = "legacy_snapshot"
        metadata["source_keys"].append(key)
    return history
