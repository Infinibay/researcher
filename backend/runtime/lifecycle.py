"""Protect native-owned tasks from legacy approval and mutable scientific validation.

Legacy adapters remain available for tasks without native admission history. Once
admitted, task completion belongs to explicit owner acceptance and finding review
belongs to the versioned independent review protocol, regardless of role labels.
"""


def require_legacy_task(conn, task_id):
    """Refuse legacy mutation or inference for a task with any durable native admission."""
    if (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='runtime_runs'"
        ).fetchone()
        is None
    ):
        # A historical database cannot contain a native admission before that schema exists.
        return
    if conn.execute(
        "SELECT 1 FROM runtime_runs WHERE task_id=? LIMIT 1", (task_id,)
    ).fetchone():
        raise ValueError(
            "Native-owned task requires versioned delivery and explicit owner acceptance; use the task workspace"
        )


def require_legacy_finding(conn, finding_id):
    """Protect all findings of an admitted task without guessing provenance from an actor name."""
    row = conn.execute(
        "SELECT task_id FROM findings WHERE id=?", (finding_id,)
    ).fetchone()
    if row is not None:
        require_legacy_task(conn, row[0])


def require_legacy_flow(task_id):
    """Reject mixed ownership before a legacy flow selects agents or spends a model turn."""
    from backend.tools.base.db import execute_with_retry

    return execute_with_retry(lambda conn: require_legacy_task(conn, task_id))
