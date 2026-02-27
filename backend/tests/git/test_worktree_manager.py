"""Tests for WorktreeManager in backend/git/worktree_manager.py.

Uses real git repos in temp directories to exercise actual worktree
creation and removal.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess

import pytest

from backend.git.worktree_manager import WorktreeManager


@pytest.fixture()
def manager():
    return WorktreeManager()


@pytest.fixture()
def git_repo(tmp_path):
    """Create a real git repo with an initial commit."""
    repo = str(tmp_path / "test-repo")
    os.makedirs(repo)
    subprocess.run(["git", "init", "-b", "main", repo], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True, capture_output=True)

    # Create initial commit so main branch exists
    gitkeep = os.path.join(repo, ".gitkeep")
    with open(gitkeep, "w"):
        pass
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    return repo


@pytest.fixture()
def seeded_repo(db_conn, seeded_project, git_repo):
    """Insert a repository record for the seeded project pointing to git_repo."""
    db_conn.execute(
        """INSERT INTO repositories (project_id, name, local_path, default_branch, status)
           VALUES (1, 'test-repo', ?, 'main', 'active')""",
        (git_repo,),
    )
    db_conn.commit()
    return git_repo


class TestEnsureWorktree:
    def test_creates_worktree_directory(self, manager, seeded_repo, db_conn):
        """ensure_worktree should create a directory under .worktrees/."""
        path = manager.ensure_worktree(
            project_id=1,
            agent_id="developer_1_p1",
            repo_local_path=seeded_repo,
            base_branch="main",
        )

        assert os.path.isdir(path)
        assert "/.worktrees/developer_1_p1" in path

        # Verify DB record
        row = db_conn.execute(
            "SELECT * FROM agent_worktrees WHERE agent_id = 'developer_1_p1'"
        ).fetchone()
        assert row is not None
        assert row["status"] == "active"
        assert row["worktree_path"] == path
        assert row["project_id"] == 1

    def test_idempotent_returns_same_path(self, manager, seeded_repo):
        """Calling ensure_worktree twice returns the same path."""
        path1 = manager.ensure_worktree(
            project_id=1,
            agent_id="developer_1_p1",
            repo_local_path=seeded_repo,
        )
        path2 = manager.ensure_worktree(
            project_id=1,
            agent_id="developer_1_p1",
            repo_local_path=seeded_repo,
        )

        assert path1 == path2

    def test_different_agents_get_different_worktrees(self, manager, seeded_repo):
        """Two agents on the same project get distinct worktrees."""
        path1 = manager.ensure_worktree(
            project_id=1,
            agent_id="developer_1_p1",
            repo_local_path=seeded_repo,
        )
        path2 = manager.ensure_worktree(
            project_id=1,
            agent_id="developer_2_p1",
            repo_local_path=seeded_repo,
        )

        assert path1 != path2
        assert os.path.isdir(path1)
        assert os.path.isdir(path2)

    def test_worktree_has_git_checkout(self, manager, seeded_repo):
        """The worktree directory should be a valid git checkout."""
        path = manager.ensure_worktree(
            project_id=1,
            agent_id="developer_1_p1",
            repo_local_path=seeded_repo,
        )

        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=path,
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == "true"

    def test_raises_for_missing_repo_record(self, manager, git_repo, seeded_project):
        """Should raise ValueError when repo is not in the DB."""
        with pytest.raises(ValueError, match="No repository found"):
            manager.ensure_worktree(
                project_id=1,
                agent_id="developer_1_p1",
                repo_local_path=git_repo,
            )

    def test_recovers_from_stale_db_record(self, manager, seeded_repo, db_conn):
        """If DB says active but directory is gone, recreate the worktree."""
        import shutil

        path = manager.ensure_worktree(
            project_id=1,
            agent_id="developer_1_p1",
            repo_local_path=seeded_repo,
        )

        # Manually remove the directory (simulate crash)
        shutil.rmtree(path)
        assert not os.path.exists(path)

        # Should recreate it
        path2 = manager.ensure_worktree(
            project_id=1,
            agent_id="developer_1_p1",
            repo_local_path=seeded_repo,
        )

        assert os.path.isdir(path2)
        assert path == path2  # same canonical path

    def test_copies_git_identity(self, manager, seeded_repo):
        """Worktree should inherit git user.name / user.email from main repo."""
        path = manager.ensure_worktree(
            project_id=1,
            agent_id="developer_1_p1",
            repo_local_path=seeded_repo,
        )

        result = subprocess.run(
            ["git", "config", "user.name"],
            cwd=path,
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == "Test"


class TestRemoveWorktree:
    def test_removes_directory_and_updates_db(self, manager, seeded_repo, db_conn):
        """remove_worktree should delete the dir and mark DB as removed."""
        path = manager.ensure_worktree(
            project_id=1,
            agent_id="developer_1_p1",
            repo_local_path=seeded_repo,
        )
        assert os.path.isdir(path)

        result = manager.remove_worktree("developer_1_p1", project_id=1)
        assert result is True

        # Directory should be gone
        assert not os.path.isdir(path)

        # DB should be marked removed
        row = db_conn.execute(
            "SELECT status, cleaned_up_at FROM agent_worktrees WHERE agent_id = 'developer_1_p1'"
        ).fetchone()
        assert row["status"] == "removed"
        assert row["cleaned_up_at"] is not None

    def test_returns_false_for_nonexistent(self, manager, seeded_project):
        """remove_worktree returns False when no active worktree exists."""
        result = manager.remove_worktree("nonexistent_agent", project_id=1)
        assert result is False

    def test_remove_then_recreate(self, manager, seeded_repo):
        """After removal, ensure_worktree should create a fresh worktree."""
        path1 = manager.ensure_worktree(
            project_id=1,
            agent_id="developer_1_p1",
            repo_local_path=seeded_repo,
        )
        manager.remove_worktree("developer_1_p1", project_id=1)

        path2 = manager.ensure_worktree(
            project_id=1,
            agent_id="developer_1_p1",
            repo_local_path=seeded_repo,
        )

        assert os.path.isdir(path2)
        assert path1 == path2  # same canonical path


class TestCleanupStaleWorktrees:
    def test_removes_worktrees_for_departed_agents(
        self, manager, seeded_repo, db_conn
    ):
        """Cleanup removes worktrees when the agent is no longer in roster."""
        path = manager.ensure_worktree(
            project_id=1,
            agent_id="developer_1_p1",
            repo_local_path=seeded_repo,
        )
        assert os.path.isdir(path)

        # developer_1_p1 is NOT in the seeded roster (only agent-1 and lead-1)
        removed = manager.cleanup_stale_worktrees(project_id=1)
        assert removed == 1

        row = db_conn.execute(
            "SELECT status FROM agent_worktrees WHERE agent_id = 'developer_1_p1'"
        ).fetchone()
        assert row["status"] == "removed"

    def test_keeps_worktrees_for_active_agents(
        self, manager, seeded_repo, db_conn
    ):
        """Cleanup should NOT remove worktrees for agents still in roster."""
        # agent-1 IS in the seeded roster
        path = manager.ensure_worktree(
            project_id=1,
            agent_id="agent-1",
            repo_local_path=seeded_repo,
        )
        assert os.path.isdir(path)

        removed = manager.cleanup_stale_worktrees(project_id=1)
        assert removed == 0

        row = db_conn.execute(
            "SELECT status FROM agent_worktrees WHERE agent_id = 'agent-1'"
        ).fetchone()
        assert row["status"] == "active"

    def test_removes_worktrees_with_missing_directories(
        self, manager, seeded_repo, db_conn
    ):
        """Cleanup should handle worktrees whose directory was already deleted."""
        import shutil

        # agent-1 IS in roster but directory will be gone
        path = manager.ensure_worktree(
            project_id=1,
            agent_id="agent-1",
            repo_local_path=seeded_repo,
        )
        shutil.rmtree(path)

        removed = manager.cleanup_stale_worktrees(project_id=1)
        assert removed == 1

        row = db_conn.execute(
            "SELECT status FROM agent_worktrees WHERE agent_id = 'agent-1'"
        ).fetchone()
        assert row["status"] == "removed"


class TestHelpers:
    def test_repo_path_from_worktree(self, manager):
        """_repo_path_from_worktree extracts the main repo path."""
        path = "/data/projects/1/my-repo/.worktrees/developer_1_p1"
        assert manager._repo_path_from_worktree(path) == "/data/projects/1/my-repo"

    def test_repo_path_from_worktree_returns_none_for_invalid(self, manager):
        """Returns None for paths that don't match the .worktrees pattern."""
        assert manager._repo_path_from_worktree("/some/random/path") is None
