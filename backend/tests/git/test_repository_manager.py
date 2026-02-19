"""Tests for RepositoryManager in backend/git/repository_manager.py."""

from unittest.mock import MagicMock, patch, call

import pytest

from backend.git.repository_manager import RepositoryManager


@pytest.fixture()
def manager():
    return RepositoryManager()


class TestInitRepo:
    @patch("backend.git.repository_manager.subprocess.run")
    def test_init_repo_runs_git_init(self, mock_run, seeded_project, manager, db_conn):
        mock_run.return_value = MagicMock(returncode=0)

        repo = manager.init_repo(
            project_id=1,
            name="my-repo",
            local_path="/tmp/my-repo",
            default_branch="main",
        )

        mock_run.assert_called_once_with(
            ["git", "init", "-b", "main", "/tmp/my-repo"],
            check=True,
            capture_output=True,
            text=True,
        )

        # Verify DB row
        row = db_conn.execute(
            "SELECT * FROM repositories WHERE project_id = 1 AND name = 'my-repo'"
        ).fetchone()
        assert row is not None
        assert row["local_path"] == "/tmp/my-repo"
        assert row["default_branch"] == "main"
        assert row["status"] == "active"

    @patch("backend.git.repository_manager.subprocess.run")
    def test_init_repo_with_remote_delegates_to_clone(self, mock_run, seeded_project, manager):
        # When remote_url is provided, clone path is taken
        mock_run.return_value = MagicMock(returncode=0, stdout="main\n")

        repo = manager.init_repo(
            project_id=1,
            name="cloned-repo",
            local_path="/tmp/cloned-repo",
            remote_url="https://github.com/example/repo.git",
        )

        # Should have called git clone first, then git rev-parse
        calls = mock_run.call_args_list
        assert any("clone" in str(c) for c in calls)
        assert repo["remote_url"] == "https://github.com/example/repo.git"


class TestCloneRepo:
    @patch("backend.git.repository_manager.subprocess.run")
    def test_clone_repo_inserts_db_record(self, mock_run, seeded_project, manager, db_conn):
        mock_run.return_value = MagicMock(returncode=0, stdout="develop\n")

        repo = manager.clone_repo(
            project_id=1,
            name="cloned",
            remote_url="https://github.com/example/repo.git",
            local_path="/tmp/cloned",
        )

        row = db_conn.execute(
            "SELECT * FROM repositories WHERE project_id = 1 AND name = 'cloned'"
        ).fetchone()
        assert row is not None
        assert row["remote_url"] == "https://github.com/example/repo.git"
        assert row["default_branch"] == "develop"


class TestListRepos:
    @patch("backend.git.repository_manager.subprocess.run")
    def test_list_repos_returns_active_only(self, mock_run, seeded_project, manager, db_conn):
        mock_run.return_value = MagicMock(returncode=0)

        # Create two repos
        manager.init_repo(project_id=1, name="active-repo", local_path="/tmp/active")
        manager.init_repo(project_id=1, name="archived-repo", local_path="/tmp/archived")

        # Archive one
        manager.archive_repo(project_id=1, name="archived-repo")

        repos = manager.list_repos(project_id=1)
        names = [r["name"] for r in repos]
        assert "active-repo" in names
        assert "archived-repo" not in names


class TestGetRepo:
    def test_get_repo_returns_none_for_missing(self, seeded_project, manager):
        result = manager.get_repo(project_id=1, name="nonexistent")
        assert result is None


class TestArchiveRepo:
    @patch("backend.git.repository_manager.subprocess.run")
    def test_archive_repo_sets_status(self, mock_run, seeded_project, manager, db_conn):
        mock_run.return_value = MagicMock(returncode=0)
        manager.init_repo(project_id=1, name="to-archive", local_path="/tmp/to-archive")

        result = manager.archive_repo(project_id=1, name="to-archive")
        assert result is True

        row = db_conn.execute(
            "SELECT status FROM repositories WHERE project_id = 1 AND name = 'to-archive'"
        ).fetchone()
        assert row["status"] == "archived"

    def test_archive_repo_returns_false_for_missing(self, seeded_project, manager):
        result = manager.archive_repo(project_id=1, name="ghost")
        assert result is False


class TestConfigureGit:
    @patch("backend.git.repository_manager.subprocess.run")
    def test_configure_git_calls_subprocess(self, mock_run, manager):
        mock_run.return_value = MagicMock(returncode=0)

        manager.configure_git(
            local_path="/tmp/repo",
            user_name="Test User",
            user_email="test@example.com",
        )

        assert mock_run.call_count == 2
        calls = mock_run.call_args_list

        assert calls[0] == call(
            ["git", "config", "user.name", "Test User"],
            cwd="/tmp/repo",
            check=True,
            capture_output=True,
            text=True,
        )
        assert calls[1] == call(
            ["git", "config", "user.email", "test@example.com"],
            cwd="/tmp/repo",
            check=True,
            capture_output=True,
            text=True,
        )
