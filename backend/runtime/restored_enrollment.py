"""Enroll a restored installation as a new execution owner while preserving copied evidence.

No original actor or remote effect is adopted or declared closed. Partial failures
remain inactive; recover by restoring the verified backup to another NEW directory.
"""

import fcntl
import json
import os
import sqlite3
import stat
import time
from contextlib import closing, contextmanager
from pathlib import Path

from backend.runtime.bootstrap import initialize_authority, _sync_directory
from backend.runtime.host_installation import _environment, _read_json, _resources, _write_new
from backend.runtime.snapshot_files import relative_name
from backend.runtime.sqlite_runs import SQLiteRunStore
from backend.runtime.recovery_receipt import read_restoration_receipt


@contextmanager
def _exclusive_owner(database):
    """Share the runtime's canonical private lock identity without starting owner recovery or dispatch."""
    fd = os.open(str(database.resolve()) + '.runtime-owner', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError('Runtime owner lock must be private and user-owned')
        fcntl.flock(fd,fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def _retain_as_history(db, database, snapshot_id):
    """Withdraw copied permissions and pause graphs without fabricating physical or remote closure."""
    now = time.time()
    store = SQLiteRunStore(database)
    changes = {'runs': [], 'paused_plans': [], 'expired_questions': []}
    for item in db.execute("SELECT id,project_id FROM runtime_runs WHERE status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review')").fetchall():
        row = store._row(db,item['project_id'],item['id'])
        original = {key:row[key] for key in ('id','project_id','task_id','status','fence','current_attempt_id','attempt_status')}
        store._withdraw(db,row,'superseded')
        store._event(db,row['project_id'],row['task_id'],'run.restored_history', {
            'snapshot_id':snapshot_id,'run_id':row['id'],'original':original,
            'replay':False,'physical_closure_proven':False,
            'detail':'Conservado como historial de la instalación original. No se reanudó aquí; revisa los efectos del host original antes de pedir otra ejecución.',
        })
        changes['runs'].append(original)
    for row in db.execute("SELECT id,project_id FROM runtime_plan_executions WHERE status='active'").fetchall():
        changes['paused_plans'].append(dict(row))
    db.execute("UPDATE runtime_plan_executions SET status='paused',updated_at=? WHERE status='active'",(now,))
    for row in db.execute("SELECT id,project_id,status FROM user_requests WHERE status='pending'").fetchall():
        changes['expired_questions'].append(dict(row))
    db.execute("UPDATE user_requests SET status='expired' WHERE status='pending'")
    db.execute('UPDATE tool_grants SET revoked_at=? WHERE revoked_at IS NULL',(now,))
    db.execute("UPDATE runtime_inference_dispatches SET status='unknown' WHERE status='reserved'")
    db.execute("INSERT INTO events_log(event_type,event_source,event_data_json) VALUES('installation.restored_enrollment','operator',?)",(json.dumps({'snapshot_id':snapshot_id,'historical_work':changes,'old_work_replayed':False,'original_host_closure_proven':False}),))
    return changes


def enroll_restored_host(directory, *, witness_dir, assets):
    """Enable a verified pending restore with fresh assets, authority and pairing; publish activation last.

The original backup remains the recovery source. Existing or partially created
authority is never reset, reused or repaired by retrying this operation.
"""
    root = Path(directory).resolve(strict=True)
    info = root.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Restored installation must be private and owned by the serving user')
    supplied = Path(witness_dir).absolute()
    witness = supplied.parent.resolve(strict=True) / supplied.name
    if root.is_relative_to(witness) or witness.is_relative_to(root):
        raise ValueError('Restored data and independent witness must not overlap')
    database = root/'source.db'
    with _exclusive_owner(database), closing(sqlite3.connect(database.as_uri()+'?mode=rw',uri=True,timeout=0)) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        marker = _read_json(root/'installation.json')
        if marker.get('format') != 1 or marker.get('status') != 'restored_pending_enrollment':
            raise ValueError('Enrollment requires a completed restore with pending enrollment')
        restoration = read_restoration_receipt(root, marker['restoration'])
        if restoration.get('snapshot_id') != marker['snapshot_id'] or restoration.get('restored_root') != str(root):
            raise ValueError('Restoration identity changed; preserve evidence and restore to a NEW path')
        if any(os.path.lexists(p) for p in (root/'authority',witness,root/'enrollment.json',root/'runtime.enrolled.json',root/'installation.enrolled.json')):
            raise FileExistsError('Enrollment requires NEW authority/witness paths; preserve partial state and restore the backup to another NEW directory')
        config, observations = _resources(assets)
        from backend.db.migration_catalog import LATEST_VERSION
        from backend.tools.base.db import ensure_migrations

        schema_before = db.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0]
        if schema_before != LATEST_VERSION:
            ensure_migrations(str(database),existing_only=True)
        db.execute('BEGIN IMMEDIATE')
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('Restored database integrity check failed')
        reboot_peers = []
        if 'reboot_evidence' in restoration:
            from backend.runtime.reboot_authority import prior_kernel_peers

            reboot_peers = prior_kernel_peers(db,restoration['reboot_evidence'])
        else:
            from backend.runtime.reboot_authority import unarchived_peers

            if unarchived_peers(db):
                raise ValueError('Restore contains peers without recorded closure or archival; inspect the original backup')
        authority = initialize_authority(database_dir=root/'authority',witness_dir=witness)
        historical = _retain_as_history(db,database,marker['snapshot_id'])
        if 'reboot_evidence' in restoration:
            from backend.runtime.reboot_authority import archive_prior_peers

            archive_prior_peers(db,reboot_peers,database=database,snapshot_id=marker['snapshot_id'],archived_at=time.time())
            historical['prior_kernel_peers'] = reboot_peers
            historical['reboot_evidence'] = restoration['reboot_evidence']
        db.commit()
        config.update(runtime_profile='owned-codex-v1',workspace_root=str(root/'sources'),
                      control_root=str(root/'control'),authority=authority,max_concurrent=1)
        _write_new(root/'runtime.enrolled.json',config)
        os.replace(root/'runtime.enrolled.json',root/'runtime.json')
        _sync_directory(root)
        result = {'format':1,'status':'prepared','snapshot_id':marker['snapshot_id'],
                  'restoration':marker['restoration'],'environment':_environment(root),
                  'authority_id':authority['authority_id'],'resource_observations':observations,
                  'historical_work':historical,'model_turns':0,'old_work_replayed':False,
                  'schema_before':schema_before,'schema_version':LATEST_VERSION,
                  'data_recovery':restoration['data_recovery'],
                  'original_host_closure_proven':False,
                  'limits':'Fresh local authority only. Copied pending work is history; original actors and remote effects are not adopted or declared closed.'}
        if config.get('static_dir'):
            result['environment']['INFINIBAY_STATIC_DIR'] = config['static_dir']
        _write_new(root/'enrollment.json',result)
        _write_new(root/'installation.enrolled.json',{'format':1,'status':'prepared',
                   'snapshot_id':marker['snapshot_id'],'restoration':marker['restoration'],'enrollment':'enrollment.json'})
        os.replace(root/'installation.enrolled.json',root/'installation.json')
        _sync_directory(root)
        return result
