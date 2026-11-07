"""Old TUI worktree entry points cannot bypass native target identity, owned execution or retention policy."""

import subprocess

import pytest

from backend.git.local_worktree import LocalWorktreeManager
from backend.runtime.contracts import RunConflict
from backend.tests.git.test_worktree_manager import retained_worktree
from backend.tests.runtime.test_installation_backup import git


@pytest.mark.parametrize('operation',['ensure','create','remove','merge','cleanup','setup','path','list'])
def test_retired_tui_worktree_calls_preserve_retained_work_and_never_start_git(retained_worktree, monkeypatch, operation):
    """Even force cleanup or an explicit merge target refuses before touching a real dirty checkout or launching Git."""
    source,retained = retained_worktree
    target = source/'.researcher/worktrees/agent'
    target.parent.mkdir(parents=True)
    git(source,'worktree','move',str(retained),str(target))
    retained = target
    def forbidden(*args, **kwargs):
        """Detect ambient execution from an obsolete TUI path, regardless of requested destination."""
        raise AssertionError('Retired TUI entry must not execute')
    monkeypatch.setattr(subprocess,'run',forbidden)
    manager = LocalWorktreeManager(str(source))
    with pytest.raises(RunConflict,match='retired'):
        if operation=='ensure':manager.ensure_base_dir()
        elif operation=='create':manager.create_worktree('agent','task/1')
        elif operation=='remove':manager.remove_worktree('agent',force=True)
        elif operation=='merge':manager.merge_worktree('agent',target_branch='different-target')
        elif operation=='cleanup':manager.cleanup_worktrees()
        elif operation=='setup':manager.setup_for_agents(['agent'])
        elif operation=='path':manager.get_worktree_path('agent')
        else:manager.list_worktrees()
    assert (retained/'value.txt').read_text() == 'useful uncommitted edit\n'
    assert (retained/'untracked.txt').read_text() == 'owner work\n'
    assert (source/'value.txt').read_text() == 'original\n'
    assert (retained/'.git').is_file()
