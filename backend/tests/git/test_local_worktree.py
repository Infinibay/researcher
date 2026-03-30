"""Tests for backend.git.local_worktree.LocalWorktreeManager."""

import subprocess
from pathlib import Path

import pytest

from backend.git.local_worktree import LocalWorktreeManager


@pytest.fixture
def git_repo(tmp_path):
    """Create a bare-minimum git repository for testing."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo, capture_output=True, check=True,
    )
    # Need at least one commit for worktrees to work
    (repo / "README.md").write_text("init")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo, capture_output=True, check=True,
    )
    return repo


@pytest.fixture
def manager(git_repo):
    return LocalWorktreeManager(str(git_repo))


class TestEnsureBaseDir:
    def test_creates_directory(self, manager, git_repo):
        manager.ensure_base_dir()
        assert manager.worktree_base.is_dir()

    def test_idempotent(self, manager):
        manager.ensure_base_dir()
        manager.ensure_base_dir()
        assert manager.worktree_base.is_dir()


class TestListWorktrees:
    def test_empty_initially(self, manager):
        result = manager.list_worktrees()
        # Only lists worktrees under .researcher/worktrees, not the main repo
        assert result == []


class TestCreateWorktree:
    def test_creates_worktree(self, manager, git_repo):
        path = manager.create_worktree("agent-1")
        assert Path(path).is_dir()
        # Should contain the same README.md from the commit
        assert (Path(path) / "README.md").exists()

    def test_returns_path(self, manager):
        path = manager.create_worktree("agent-2")
        assert "agent-2" in path

    def test_idempotent(self, manager):
        path1 = manager.create_worktree("agent-3")
        path2 = manager.create_worktree("agent-3")
        assert path1 == path2

    def test_custom_branch_name(self, manager):
        path = manager.create_worktree("agent-4", branch_name="feature/test")
        assert Path(path).is_dir()


class TestGetWorktreePath:
    def test_returns_path_when_exists(self, manager):
        created = manager.create_worktree("agent-5")
        found = manager.get_worktree_path("agent-5")
        assert found == created

    def test_returns_none_when_missing(self, manager):
        assert manager.get_worktree_path("nonexistent") is None


class TestRemoveWorktree:
    def test_removes_worktree(self, manager):
        manager.create_worktree("agent-6")
        assert manager.get_worktree_path("agent-6") is not None

        result = manager.remove_worktree("agent-6")
        assert result is True
        assert manager.get_worktree_path("agent-6") is None

    def test_returns_false_for_nonexistent(self, manager):
        assert manager.remove_worktree("nonexistent") is False


class TestCleanupWorktrees:
    def test_removes_all(self, manager):
        manager.create_worktree("agent-a")
        manager.create_worktree("agent-b")

        count = manager.cleanup_worktrees()
        assert count == 2
        assert manager.list_worktrees() == []

    def test_returns_zero_when_empty(self, manager):
        assert manager.cleanup_worktrees() == 0


class TestSetupForAgents:
    def test_creates_multiple_worktrees(self, manager):
        paths = manager.setup_for_agents(["dev-1", "dev-2", "dev-3"])
        assert len(paths) == 3
        assert all(Path(p).is_dir() for p in paths.values())
        assert "dev-1" in paths
        assert "dev-2" in paths
        assert "dev-3" in paths
