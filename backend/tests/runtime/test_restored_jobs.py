"""Copied active command receipts become honest unknown history without replay or invented closure."""

import json
import sqlite3

import pytest

from backend.tests.runtime.test_host_installation import host_assets
from backend.tests.runtime.test_installation_backup import installation


@pytest.mark.parametrize('pending_state', ['dispatching', 'cancelling', 'unknown'])
def test_restored_jobs_preserve_completed_effects_and_original_uncertainty(installation, host_assets, tmp_path, pending_state):
    """Exercise public backup, restore and enrollment with completed and interrupted command records."""
    from backend.runtime.contracts import CommandSpec, RunSpec
    from backend.runtime.installation_backup import backup_installation
    from backend.runtime.installation_restore import restore_installation
    from backend.runtime.restored_enrollment import enroll_restored_host
    from backend.runtime.sqlite_runs import SQLiteRunStore

    original, _authority = installation
    store = SQLiteRunStore(original / 'source.db')
    run = store.admit(RunSpec(101, 1001, 'fixture', 1, 'original-intent', 'Retain original command effects', 'codex'))
    lease = store.claim(101, run.run_id, 'original-owner')
    specification = CommandSpec(('python', '-c', 'print(200)'), '.', 30, 4096)
    finished = store.reserve_job(lease, operation_key='completed', spec=specification,
                                 workspace=str(original / 'sources'), executor_id='original').job
    store.finish_job(lease, finished.job_id, executor_id='original', exit_code=0,
                     stdout=b'200\n', stderr=b'', output_limited=False, error=None)
    pending = store.reserve_job(lease, operation_key='interrupted', spec=specification,
                                workspace=str(original / 'sources'), executor_id='original').job
    if pending_state == 'cancelling':
        store.cancel_job(lease, pending.job_id)
    elif pending_state == 'unknown':
        store.finish_job(lease, pending.job_id, executor_id='original', exit_code=None,
                         stdout=b'partial observation', stderr=b'', output_limited=False, error='OriginalUnknown')
    prior_complete = store.get_job(101, finished.job_id)
    prior_pending = store.get_job(101, pending.job_id)
    backup_installation(original, tmp_path / 'backup')
    root = tmp_path / 'restored'
    restore_installation(tmp_path / 'backup', root)
    result = enroll_restored_host(root, witness_dir=tmp_path / 'fresh-witness', assets=host_assets)
    restored = SQLiteRunStore(root / 'source.db')
    completed = restored.get_job(101, finished.job_id)
    interrupted = restored.get_job(101, pending.job_id)
    assert completed == prior_complete
    assert interrupted.status == 'unknown'
    assert interrupted.exit_code is None and not interrupted.local_execution_closed
    assert interrupted.stdout == prior_pending.stdout
    assert interrupted.cancel_requested == prior_pending.cancel_requested
    if pending_state == 'unknown':
        assert interrupted.error == 'OriginalUnknown'
    assert result['historical_work']['jobs'][0]['status'] == pending_state
    assert store.get_job(101, pending.job_id) == prior_pending
    with sqlite3.connect(root / 'source.db') as db:
        assert db.execute('SELECT count(*) FROM runtime_jobs').fetchone() == (2,)
        assert db.execute('SELECT count(*) FROM runtime_inference_dispatches').fetchone() == (0,)
        event = json.loads(db.execute("SELECT event_data_json FROM events_log WHERE event_type='installation.restored_enrollment'").fetchone()[0])
        assert event['historical_work']['jobs'] == result['historical_work']['jobs']
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
