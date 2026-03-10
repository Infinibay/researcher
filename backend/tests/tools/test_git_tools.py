"""Tests for Git tools (using mocked subprocess)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.tools.git import (
    GitBranchTool,
    GitCommitTool,
    GitDiffTool,
    GitStatusTool,
)


class TestGitStatusTool:
    @patch("backend.tools.git.status.subprocess.run")
    def test_clean_status(self, mock_run, agent_context):
        # Mock git status --porcelain (empty = clean)
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),  # status
            MagicMock(returncode=0, stdout="main\n", stderr=""),  # branch
        ]
        tool = GitStatusTool()
        result = json.loads(tool._run())
        assert result["clean"] is True
        assert result["branch"] == "main"

    @patch("backend.tools.git.status.subprocess.run")
    def test_modified_files(self, mock_run, agent_context):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=" M src/main.py\n?? new_file.txt\n", stderr=""),
            MagicMock(returncode=0, stdout="feature\n", stderr=""),
        ]
        tool = GitStatusTool()
        result = json.loads(tool._run())
        assert result["clean"] is False
        assert len(result["modified"]) == 1
        assert len(result["untracked"]) == 1


class TestGitDiffTool:
    @patch("backend.tools.git.diff.subprocess.run")
    def test_diff_output(self, mock_run, agent_context):
        diff_text = "diff --git a/foo.py b/foo.py\n-old\n+new"
        mock_run.return_value = MagicMock(returncode=0, stdout=diff_text, stderr="")

        tool = GitDiffTool()
        result = tool._run()
        assert "diff --git" in result

    @patch("backend.tools.git.diff.subprocess.run")
    def test_no_changes(self, mock_run, agent_context):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        tool = GitDiffTool()
        result = tool._run()
        assert "no differences" in result.lower()


class TestGitBranchTool:
    @patch("backend.tools.git.branch.subprocess.run")
    @patch("backend.tools.git.branch.execute_with_retry")
    def test_create_branch(self, mock_retry, mock_run, agent_context):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="http://localhost:3000/infinibay/test.git", stderr=""),  # remote get-url
            MagicMock(returncode=0, stdout="", stderr=""),  # fetch
            MagicMock(returncode=0, stdout="", stderr=""),  # checkout -b
        ]
        mock_retry.return_value = None

        tool = GitBranchTool()
        result = json.loads(tool._run(branch_name="feature/test"))
        assert result["action"] == "created"
        assert result["branch"] == "feature/test"

    def test_invalid_branch_name(self, agent_context):
        tool = GitBranchTool()
        result = tool._run(branch_name="bad branch name!")
        assert "error" in result


class TestGitCommitTool:
    @patch("backend.tools.git.commit.subprocess.run")
    @patch("backend.tools.git.commit.execute_with_retry")
    def test_commit_all(self, mock_retry, mock_run, agent_context):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=" M file.py\n", stderr=""),  # status
            MagicMock(returncode=0, stdout="", stderr=""),  # add -A
            MagicMock(returncode=0, stdout="", stderr=""),  # commit
            MagicMock(returncode=0, stdout="abc123\n", stderr=""),  # rev-parse HEAD
            MagicMock(returncode=0, stdout="main\n", stderr=""),  # rev-parse branch
        ]
        mock_retry.return_value = None

        tool = GitCommitTool()
        result = json.loads(tool._run(message="Test commit"))
        assert result["commit_hash"] == "abc123"
        assert result["message"] == "Test commit"

    @patch("backend.tools.git.commit.subprocess.run")
    def test_no_changes_to_commit(self, mock_run, agent_context):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        tool = GitCommitTool()
        result = tool._run(message="Empty")
        assert "error" in result
        assert "no changes" in result.lower()
