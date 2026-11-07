"""Legacy merge cannot mutate an admitted native task or its source through a different task/project alias."""

from dataclasses import replace

import pytest


@pytest.fixture
async def legacy_publication(service_setup):
    """Create two real local commits and historical PR metadata, without an accepted native candidate."""
    from backend.tests.runtime.test_development_workspace import fixture_git

    s = service_setup
    await fixture_git(s.workspace, "init", "-q", "--initial-branch=main")
    await fixture_git(s.workspace, "config", "user.name", "Fixture")
    await fixture_git(s.workspace, "config", "user.email", "fixture@localhost")
    (s.workspace / "value.txt").write_text("137\n")
    await fixture_git(s.workspace, "add", "value.txt")
    await fixture_git(s.workspace, "commit", "-qm", "base")
    await fixture_git(s.workspace, "checkout", "-qb", "unaccepted-candidate")
    (s.workspace / "value.txt").write_text("999\n")
    await fixture_git(s.workspace, "commit", "-qam", "unaccepted change")
    await fixture_git(s.workspace, "checkout", "-q", "main")
    s.c.conn.execute(
        "INSERT INTO branches(project_id,task_id,repo_name,branch_name,status,created_by) VALUES(101,1001,'alpha','unaccepted-candidate','active','fixture')"
    )
    s.c.conn.execute(
        "INSERT INTO code_reviews(id,project_id,task_id,repo_name,branch,status,agent_run_id) VALUES(71,101,1001,'alpha','unaccepted-candidate','approved','historical-fixture')"
    )
    s.c.conn.commit()
    return s


@pytest.mark.parametrize(
    "alias", ["task", "different_task", "different_project", "no_task"]
)
async def test_unaccepted_native_code_cannot_publish_through_legacy_merge(
    legacy_publication, alias
):
    """Actual Git must stay unchanged despite a legacy approved label or a PR with another task/project identity."""
    from backend.git.pr_service import PRService
    from backend.runtime.contracts import RunConflict
    from backend.runtime.workspaces import WorkspaceRegistry
    from backend.tests.runtime.test_development_workspace import fixture_git

    s = legacy_publication
    binding = WorkspaceRegistry(s.c.database, s.root).bind(101, 11)
    s.c.store.admit(s.c.spec, binding=binding)
    if alias == "different_task":
        s.c.conn.execute("UPDATE code_reviews SET task_id=1002 WHERE id=71")
    elif alias == "different_project":
        s.c.conn.execute("INSERT INTO repositories(id,project_id,name,local_path) VALUES(22,202,'alpha','/unavailable/foreign')")
        s.c.conn.execute(
            "UPDATE code_reviews SET project_id=202,task_id=2002,repo_id=22 WHERE id=71"
        )
    elif alias == "no_task":
        s.c.conn.execute("UPDATE code_reviews SET task_id=NULL WHERE id=71")
    s.c.conn.commit()
    before = await fixture_git(s.workspace, "rev-parse", "HEAD")
    with pytest.raises(RunConflict, match="Native-owned"):
        PRService().merge_pr(71, str(s.workspace))
    assert await fixture_git(s.workspace, "rev-parse", "HEAD") == before
    assert (s.workspace / "value.txt").read_text() == "137\n"
    assert (
        s.c.conn.execute("SELECT status FROM code_reviews WHERE id=71").fetchone()[0]
        == "approved"
    )


async def test_native_pr_is_blocked_before_remote_merge(
    legacy_publication, monkeypatch
):
    """An unavailable local clone or an ambient Forgejo setting cannot turn a native task's legacy status into remote authority."""
    from unittest.mock import Mock

    from backend.git.pr_service import PRService
    from backend.runtime.contracts import RunConflict

    s = legacy_publication
    s.c.store.admit(s.c.spec)
    s.c.conn.execute("UPDATE code_reviews SET forgejo_pr_index=9 WHERE id=71")
    s.c.conn.execute(
        "UPDATE repositories SET remote_url='https://forge.example.invalid/org/alpha.git' WHERE id=11"
    )
    s.c.conn.commit()
    monkeypatch.setenv("FORGEJO_API_URL", "https://forge.example.invalid")
    remote = Mock()
    monkeypatch.setattr(PRService, "_forgejo_merge", remote)
    with pytest.raises(RunConflict, match="Native-owned"):
        PRService().merge_pr(71, str(s.workspace / "missing-clone"))
    remote.assert_not_called()


async def test_another_repository_does_not_restore_retired_legacy_merge(
    legacy_publication, tmp_path
):
    """All project publication now requires native owner policy; admission in another source does not revive an old PR approval."""
    from backend.git.pr_service import PRService
    from backend.runtime.contracts import RunConflict
    from backend.runtime.workspaces import WorkspaceRegistry

    s = legacy_publication
    other = s.root / "other"
    other.mkdir()
    s.c.conn.execute(
        "INSERT INTO repositories(id,project_id,name,local_path) VALUES(12,101,'other',?)",
        (str(other),),
    )
    s.c.conn.commit()
    binding = WorkspaceRegistry(s.c.database, s.root).bind(101, 12)
    s.c.store.admit(replace(s.c.spec, task_id=1002), binding=binding)
    with pytest.raises(RunConflict, match="Native-owned"):
        PRService().merge_pr(71, str(s.workspace))
    assert (s.workspace / "value.txt").read_text() == "137\n"
    assert (
        s.c.conn.execute("SELECT status FROM code_reviews WHERE id=71").fetchone()[0]
        == "approved"
    )
