"""Retired database worktree effects cannot reset retained branches, copy credentials or erase dirty work."""

import subprocess
from pathlib import Path

import pytest

from backend.git.worktree_manager import WorktreeManager
from backend.runtime.contracts import RunConflict
from backend.tests.runtime.test_installation_backup import git


@pytest.fixture
def retained_worktree(tmp_path):
    """Create a real linked checkout with tracked and untracked owner edits before testing retired entry points."""
    source = tmp_path/'source'; source.mkdir()
    git(source,'init','-b','main')
    (source/'value.txt').write_text('original\n')
    git(source,'add','.'); git(source,'commit','-m','base')
    retained = source/'.worktrees'/'agent'; retained.parent.mkdir()
    git(source,'worktree','add','-b','task/1',str(retained),'main')
    (retained/'value.txt').write_text('useful uncommitted edit\n')
    (retained/'untracked.txt').write_text('owner work\n')
    return source,retained


@pytest.mark.parametrize('operation',['ensure','remove','cleanup'])
def test_retired_database_worktree_calls_preserve_files_and_metadata(retained_worktree, db_conn, seeded_project, monkeypatch, operation):
    """Every historical mutation refuses before any Git process or database callback, leaving real edits and records intact."""
    from backend.tools.base import db
    source,retained = retained_worktree
    db_conn.execute("INSERT INTO repositories(id,project_id,name,local_path) VALUES(11,1,'app',?)",(str(source),))
    db_conn.execute("INSERT INTO agent_worktrees(project_id,repo_id,agent_id,worktree_path,branch_name) VALUES(1,11,'agent',?,'task/1')",(str(retained),))
    db_conn.commit()
    before = [tuple(row) for row in db_conn.execute('SELECT * FROM agent_worktrees')]
    def forbidden(*args, **kwargs):
        """Detect any attempt to reactivate the obsolete process or persistence path."""
        raise AssertionError('Retired worktree entry must not execute or write')
    monkeypatch.setattr(subprocess,'run',forbidden)
    monkeypatch.setattr(db,'execute_with_retry',forbidden)
    manager = WorktreeManager()
    with pytest.raises(RunConflict,match='retired'):
        if operation=='ensure':manager.ensure_worktree(1,'agent',str(source),'main')
        elif operation=='remove':manager.remove_worktree('agent',1)
        else:manager.cleanup_stale_worktrees(1)
    assert (retained/'value.txt').read_text() == 'useful uncommitted edit\n'
    assert (retained/'untracked.txt').read_text() == 'owner work\n'
    assert (source/'value.txt').read_text() == 'original\n'
    assert [tuple(row) for row in db_conn.execute('SELECT * FROM agent_worktrees')] == before
