"""Fresh owner-inspection fixtures retain real closed command receipts without model work."""

import sqlite3
from pathlib import Path

import pytest


async def test_owner_fixture_rejects_an_existing_root(tmp_path, native_asset):
    """An existing directory can never be interpreted as permission to copy or replace its data."""
    from evals.runtime.owner_trial import prepare

    root = tmp_path / 'existing'
    root.mkdir()
    marker = root / 'source.db'
    marker.write_bytes(b'USER_OR_PREVIOUS_DATA')
    with pytest.raises(FileExistsError):
        await prepare(root, native_asset.path, tmp_path / 'missing-cgroup')
    assert marker.read_bytes() == b'USER_OR_PREVIOUS_DATA'


async def test_fresh_owner_fixture_has_real_closed_command_and_no_dispatch(tmp_path, native_asset):
    """Populate both views from a current native command, detect later mutations, and close all actors."""
    from evals.runtime.owner_trial import fingerprint, prepare

    parent = (Path('/sys/fs/cgroup') / Path('/proc/self/cgroup').read_text().strip().split(':', 2)[2].lstrip('/')).parent
    if not {'memory', 'pids'} <= set((parent / 'cgroup.subtree_control').read_text().split()):
        pytest.skip('Requires a delegated parent')
    trial = await prepare(tmp_path / 'owner', native_asset.path, parent)
    assert trial.expected_stdout.decode().startswith('Resultado local: 137 + 63 = 200')
    assert fingerprint(trial.source_database) == fingerprint(trial.database)
    assert not trial.execution.domain_path.exists() and trial.execution.peers.closed()
    with sqlite3.connect(trial.database) as db:
        assert db.execute('SELECT COUNT(*) FROM runtime_jobs').fetchone() == (1,)
        assert db.execute('SELECT COUNT(*) FROM runtime_inference_dispatches').fetchone() == (0,)
        assert db.execute('SELECT status,exit_code FROM runtime_jobs').fetchone() == ('exited', 0)
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        db.execute("UPDATE tasks SET title='Changed copy only' WHERE id=1001")
    assert fingerprint(trial.source_database) != fingerprint(trial.database)
    assert not (trial.root / 'authority').exists()
