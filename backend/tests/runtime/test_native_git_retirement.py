"""Historical Git records remain data; every publication uses the native accepted-candidate path, even before first admission."""

from importlib import import_module
from types import SimpleNamespace

import pytest

from backend.tests.runtime.test_legacy_code_publication import legacy_publication  # noqa: F401


@pytest.mark.parametrize("remote", [False, True])
async def test_preadmission_pr_without_task_cannot_merge_or_call_remote(legacy_publication, monkeypatch, remote):
    """An approved label without a task or registered source cannot bypass fresh author/check/review/owner acceptance."""
    from backend.git.pr_service import PRService
    from backend.runtime.contracts import RunConflict
    from backend.tests.runtime.test_development_workspace import fixture_git

    s = legacy_publication
    s.c.conn.execute("UPDATE code_reviews SET task_id=NULL,forgejo_pr_index=9 WHERE id=71")
    s.c.conn.execute("UPDATE repositories SET remote_url='https://forge.example.invalid/org/alpha.git' WHERE id=11")
    s.c.conn.commit()
    monkeypatch.setenv("FORGEJO_API_URL", "https://forge.example.invalid" if remote else "")
    effects = []
    monkeypatch.setattr(PRService, "_forgejo_merge", lambda *a, **kw: effects.append("remote"))
    with pytest.raises(RunConflict, match="Native-owned"):
        PRService().merge_pr(71, str(s.workspace))
    assert not effects
    assert (s.workspace / "value.txt").read_text() == "137\n"
    assert (await fixture_git(s.workspace, "show", "unaccepted-candidate:value.txt")).strip() == b"999"
    assert s.c.conn.execute("SELECT status FROM code_reviews WHERE id=71").fetchone()[0] == "approved"
    assert s.c.conn.execute("SELECT COUNT(*) FROM runtime_runs").fetchone()[0] == 0


async def test_old_branch_creation_refuses_before_git_or_status_changes(legacy_publication, monkeypatch):
    """Native task protection must happen before git branch, not after the source has already been changed."""
    from backend.git.branch_service import BranchService
    from backend.runtime.contracts import RunConflict

    s = legacy_publication
    effects = []
    monkeypatch.setattr(import_module("backend.git.branch_service"), "subprocess", SimpleNamespace(run=lambda *a, **kw: effects.append("git")), raising=False)
    before = [tuple(row) for row in s.c.conn.execute("SELECT * FROM branches")]
    with pytest.raises(RunConflict, match="Native-owned"):
        BranchService().create_branch_for_task(1001, str(s.workspace), repo_name="alpha")
    assert not effects
    assert [tuple(row) for row in s.c.conn.execute("SELECT * FROM branches")] == before


@pytest.mark.parametrize("operation", ["delete_local_branch", "delete_remote_branch", "cleanup_merged_branches", "cleanup_stale_branches", "schedule_periodic_cleanup"])
async def test_retired_cleanup_preserves_git_and_history_without_threads(legacy_publication, monkeypatch, operation):
    """Old merged/stale labels cannot authorize destruction of retained material or start another autonomous cleanup worker."""
    from backend.git.cleanup import BranchCleanupService
    from backend.git import cleanup as cleanup_module
    from backend.runtime.contracts import RunConflict

    s = legacy_publication
    service = BranchCleanupService()
    effects = []
    monkeypatch.setattr(cleanup_module, "subprocess", SimpleNamespace(run=lambda *a, **kw: effects.append("git")), raising=False)
    monkeypatch.setattr(cleanup_module, "threading", SimpleNamespace(Thread=lambda *a, **kw: effects.append("thread")), raising=False)
    before = [tuple(row) for row in s.c.conn.execute("SELECT * FROM branches")]
    args = ("unaccepted-candidate", str(s.workspace)) if operation.startswith("delete_") else (() if operation == "schedule_periodic_cleanup" else (101,))
    with pytest.raises(RunConflict, match="Native-owned"):
        getattr(service, operation)(*args)
    assert not effects and not service._running
    assert [tuple(row) for row in s.c.conn.execute("SELECT * FROM branches")] == before


async def test_pr_owner_entry_correlates_real_project_repository_and_task_without_claiming_bytes(legacy_publication):
    """Recorded branch/worktree labels guide explicit file selection, but do not prove availability, original context or native approval."""
    from backend.git.pr_service import PRService

    s = legacy_publication
    s.c.conn.execute("INSERT INTO agent_worktrees(id,project_id,repo_id,agent_id,worktree_path,branch_name) VALUES(7,101,11,'old-developer','/unavailable/old-developer','unaccepted-candidate')")
    s.c.conn.execute("INSERT INTO repositories(id,project_id,name,local_path) VALUES(12,101,'other','/unavailable/other')")
    s.c.conn.execute("INSERT INTO agent_worktrees(id,project_id,repo_id,agent_id,worktree_path,branch_name) VALUES(8,101,12,'other-developer','/unavailable/other-developer','unaccepted-candidate')")
    s.c.conn.commit()
    entry = PRService().owner_entry(71)
    assert entry['project_id'] == 101 and entry['task']['id'] == 1001
    assert entry['native_admission_run_id'] is None
    assert entry['historical_status'] == 'approved'
    assert entry['acceptance'] == entry['publication'] == 'not_conferred_by_history'
    assert [item['source_id'] for item in entry['recorded_worktrees']] == ['7']
    assert entry['recorded_worktrees'][0]['availability'] == 'not_inspected'
    assert entry['branch_snapshot_import'] == 'pending'
    assert entry['original_context'] == 'unknown'
    assert s.c.conn.execute('SELECT COUNT(*) FROM runtime_runs').fetchone()[0] == 0


async def test_pr_owner_entry_does_not_follow_a_foreign_recorded_task(legacy_publication):
    """A legacy FK or role label cannot silently move owner navigation or retained data to another project."""
    from backend.git.pr_service import PRService

    s = legacy_publication
    s.c.conn.execute('UPDATE code_reviews SET task_id=2002 WHERE id=71')
    s.c.conn.commit()
    entry = PRService().owner_entry(71)
    assert entry['project_id'] == 101 and entry['recorded_task_id'] == 2002
    assert entry['task'] is None and entry['task_relation'] == 'missing_or_foreign'


async def test_owner_http_reads_history_bridge_and_refuses_old_effects_before_path_resolution(legacy_publication):
    """The actual owner API preserves the PR/branch and explains native-only publication even if the historical clone is unavailable."""
    from starlette.testclient import TestClient

    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app

    s = legacy_publication
    s.c.conn.execute("UPDATE repositories SET local_path='/unavailable/repository' WHERE id=11")
    s.c.conn.commit()
    key = 'synthetic-git-owner-pairing-key-at-least32'
    client = TestClient(create_app(access=LocalAccess(pairing_key=key)), base_url='http://localhost')
    paired = client.post('/api/session', json={'code': key}, headers={'X-Researcher-Client': 'web'})
    assert paired.status_code == 200, paired.text
    client.headers['X-Researcher-CSRF'] = paired.json()['csrf_token']
    history = client.get('/api/git/prs/71/owner-entry')
    assert history.status_code == 200, history.text
    assert history.json()['native_admission_run_id'] is None
    for path, body in [('/api/git/prs/71/merge', {}), ('/api/git/cleanup', {'project_id': 101, 'repo_path': '/unavailable/repository'}), ('/api/git/branches', {'task_id': 1001, 'repo_name': 'alpha'})]:
        response = client.post(path, json=body)
        assert response.status_code == 409, response.text
        assert 'Native-owned' in response.json()['detail']
    assert s.c.conn.execute('SELECT status FROM code_reviews WHERE id=71').fetchone()[0] == 'approved'
    client.close()
