"""Keep historical Git labels separate from native publication authority; retired effects cannot infer approval, identity or safe cleanup from old records."""

from typing import NoReturn

from backend.runtime.contracts import RunConflict, RunNotFound


def retired_git_effect(operation: str) -> NoReturn:
    """Refuse an obsolete effect before process/network/state changes; this is native-only policy, not evidence of previous admission or physical closure."""
    raise RunConflict(
        f"Native-owned publication is required; legacy {operation} is retired. "
        "Keep the old branch and PR as history. Inspect its material in the task workspace, "
        "then use fresh development, checks, independent review and explicit owner "
        "acceptance/publication. A historical approved or merged label is not authority."
    )


def pr_owner_entry(conn, pr_id: int) -> dict:
    """Correlate historical PR/task/repository/worktree labels without reading Git, inferring byte availability or transferring old approval to native work."""
    from backend.runtime.legacy_handoff import project_owner_entry
    from backend.runtime.task_profiles import DEVELOPMENT_TASK_TYPES

    pr = conn.execute("SELECT * FROM code_reviews WHERE id=?", (pr_id,)).fetchone()
    if pr is None:
        raise RunNotFound("Historical PR not found")
    project = conn.execute("SELECT id FROM projects WHERE id=?", (pr['project_id'],)).fetchone()
    task = conn.execute(
        "SELECT id,type,title FROM tasks WHERE project_id=? AND id=?", (pr['project_id'], pr['task_id'])
    ).fetchone()
    repo = conn.execute(
        "SELECT id FROM repositories WHERE project_id=? AND id=?", (pr['project_id'], pr['repo_id'])
    ).fetchone()
    branch = conn.execute(
        'SELECT id FROM branches WHERE project_id=? AND repo_id=? AND branch_name=?',
        (pr['project_id'], repo['id'], pr['branch']),
    ).fetchone() if repo is not None else None
    worktrees = []
    if repo is not None:
        worktrees = [
            {'source_kind': 'legacy_worktree', 'source_id': str(row['id']),
             'repository_id': repo['id'], 'label': row['agent_id'],
             'recorded_status': row['status'], 'availability': 'not_inspected'}
            for row in conn.execute(
                "SELECT id,agent_id,status FROM agent_worktrees WHERE project_id=? AND repo_id=? AND branch_name=? ORDER BY id",
                (pr['project_id'], repo['id'], pr['branch']),
            )
        ]
    owner = project_owner_entry(conn, project['id']) if project is not None else None
    return {
        'delivery': 'historical_git_owner_entry', 'pr_id': pr['id'],
        'project_id': project['id'] if project is not None else None,
        'recorded_project_id': pr['project_id'], 'recorded_task_id': pr['task_id'],
        'task': dict(task) if task is not None else None,
        'task_relation': 'recorded_in_project' if task is not None else 'missing_or_foreign',
        'task_type_accepts_code_input': task is not None and task['type'] in DEVELOPMENT_TASK_TYPES,
        'repository_id': repo['id'] if repo is not None else None,
        'recorded_repository_name': pr['repo_name'], 'recorded_branch': pr['branch'],
        'historical_status': pr['status'],
        'native_admission_run_id': owner['native_admission_run_id'] if owner else None,
        'recorded_worktrees': worktrees, 'branch_id': branch['id'] if branch is not None else None,
        'branch_snapshot_import': 'requires_owned_preparation' if branch is not None else 'requires_branch_record',
        'original_context': 'unknown', 'acceptance': 'not_conferred_by_history',
        'publication': 'not_conferred_by_history', 'inference_started': False,
        'explanation': 'This is historical PR metadata. Recorded worktrees can be inspected as selected file data; a recorded branch can be selected with a full immutable commit for original owned acquisition before a fresh author turn. Availability and original author/context are not verified by this read. Old approval/merged labels confer no native acceptance or publication authority.',
    }
