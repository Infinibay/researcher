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


def require_legacy_git_publication(conn, *, task_id, project_id, repo_name, repo_path):
    """Reject legacy merge of native-owned tasks or registered physical sources, including another task/project alias; no historical approval grants publication authority."""
    from pathlib import Path

    from backend.runtime.contracts import RunConflict

    if task_id is not None:
        try:
            require_legacy_task(conn, task_id)
        except ValueError as error:
            raise RunConflict(str(error)) from error
    if (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='runtime_workspace_bindings'"
        ).fetchone()
        is None
    ):
        return
    registered = conn.execute(
        """SELECT 1 FROM runtime_workspace_bindings b JOIN repositories r ON r.id=b.repository_id
        WHERE r.project_id=? AND r.name=? LIMIT 1""",
        (project_id, repo_name),
    ).fetchone()
    physical = None
    try:
        info = Path(repo_path).stat()
    except OSError:
        # Remote-only historical repositories need not have a local clone.
        # Their actual registered identity and native task are still checked.
        pass
    else:
        physical = conn.execute(
            "SELECT 1 FROM runtime_workspace_bindings WHERE device=? AND inode=? LIMIT 1",
            (info.st_dev, info.st_ino),
        ).fetchone()
    if registered or physical:
        raise RunConflict(
            "Native-owned repository requires publication of its exact accepted candidate; legacy PR status is not authority"
        )


def require_legacy_flow(task_id):
    """Reject mixed ownership before a legacy flow selects agents or spends a model turn."""
    from backend.tools.base.db import execute_with_retry

    return execute_with_retry(lambda conn: require_legacy_task(conn, task_id))
