"""Protect migrated tasks from legacy claims, approval and mutable validation.

All persisted task types use native owner entry. Historical project-level adapters
remain admission-guarded until their separate cutover; a hint never proves that
old producers have physically stopped.
"""


class NativeOwnerRequired(ValueError):
    """Actual native project ownership excludes competing legacy activation; no physical-closure claim is implied."""


def require_legacy_project(conn, project_id):
    """Refuse a legacy producer for every actual project before or after admission, using stored evidence rather than a role, marker or ambient task."""
    from backend.runtime.legacy_handoff import project_owner_entry

    if project_owner_entry(conn, project_id) is not None:
        raise NativeOwnerRequired(
            "Native-owned project requires its owner workspace; legacy inference or recovery is not authorized"
        )


def require_legacy_execution_project(project_id):
    """Check the explicit project again at an old engine boundary; never choose a project from role, cwd or another thread's context."""
    from backend.tools.base.db import execute_with_retry

    return execute_with_retry(lambda conn: require_legacy_project(conn, project_id))


def require_legacy_task(conn, task_id):
    """Refuse legacy mutation/inference for all migrated task categories and any task with native admission history."""
    from backend.runtime.task_profiles import OWNER_ONLY_LEGACY_TASK_TYPES

    task = conn.execute("SELECT type FROM tasks WHERE id=?", (task_id,)).fetchone()
    if task is not None and task[0] in OWNER_ONLY_LEGACY_TASK_TYPES:
        raise ValueError(
            "Research and investigation require the native owner task workspace"
            if task[0] in ("research", "investigation")
            else "Task execution requires the native owner task workspace"
        )
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

    task = conn.execute(
        "SELECT project_id FROM tasks WHERE id=?", (task_id,)
    ).fetchone()
    if task is not None:
        require_legacy_project(conn, task[0])


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
