"""The legacy setup entry points cannot mutate sources, configure credentials or create remotes outside original administrative ownership."""

from importlib import import_module

import pytest


@pytest.mark.parametrize('operation', ['init', 'clone', 'identity', 'credential'])
def test_legacy_source_setup_refuses_before_any_effect(service_setup, monkeypatch, operation):
    """A useful existing directory and its recorded source survive every retired setup route without a subprocess, remote call or metadata rewrite."""
    from backend.git.repository_manager import RepositoryManager
    from backend.runtime.contracts import RunConflict

    s = service_setup
    path = s.workspace
    (path/'fact.txt').write_text('137')
    module = import_module('backend.git.repository_manager')

    def forbidden(*_args, **_kwargs):
        """Abort the first unowned process before the legacy implementation can modify even the isolated fixture."""
        raise AssertionError('Unowned Git effect attempted')

    monkeypatch.setattr(module, 'subprocess', type('ForbiddenProcesses', (), {'run':staticmethod(forbidden)}), raising=False)
    from backend.config.settings import settings
    monkeypatch.setattr(settings, 'FORGEJO_API_URL', '')
    before = [tuple(row) for row in s.c.conn.execute('SELECT * FROM repositories')]
    manager = RepositoryManager()
    with pytest.raises(RunConflict, match='Source operations'):
        if operation == 'init':
            manager.init_repo(101, 'replacement', str(path))
        elif operation == 'clone':
            manager.clone_repo(101, 'replacement', 'https://example.invalid/repo.git', str(path))
        elif operation == 'identity':
            manager.configure_git(str(path), 'Replacement', 'replacement@localhost')
        else:
            manager._configure_forgejo_auth(str(path), 'fixture-secret-never-stored')
    assert (path/'fact.txt').read_text() == '137' and not (path/'.git').exists()
    assert [tuple(row) for row in s.c.conn.execute('SELECT * FROM repositories')] == before
