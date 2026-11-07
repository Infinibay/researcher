"""Verify usable recovery metadata and honest snapshot boundaries after new application writes."""

from contextlib import closing
import json
from pathlib import Path
import sqlite3

import pytest

from backend.tests.runtime.test_host_installation import host_assets
from backend.tests.runtime.test_installation_backup import installation


def add_references(root, count=320):
    """Create enough actual attachments and registrations to exceed a configuration-sized relocation receipt."""
    with closing(sqlite3.connect(root/'source.db')) as db, db:
        for index in range(count):
            name=f'historical-{index:04d}-'+('long-name-'*8)+'.txt'
            path=root/'uploads/101/uploads'/name
            path.write_text(f'Original evidence {index}.')
            db.execute('INSERT INTO reference_files(project_id,file_name,file_path,file_size) VALUES(101,?,?,?)',
                       (name,str(path),path.stat().st_size))


def test_large_restoration_receipt_can_enroll_without_losing_any_registration(installation,tmp_path,host_assets):
    """Many retained references must not turn a successful data restore into an unenrollable host."""
    from backend.runtime.installation_backup import backup_installation
    from backend.runtime.installation_restore import restore_installation
    from backend.runtime.restored_enrollment import enroll_restored_host

    original,_=installation
    add_references(original)
    backup_installation(original,tmp_path/'backup')
    target=tmp_path/'restored'
    restored=restore_installation(tmp_path/'backup',target)
    assert len(json.dumps(restored).encode())>65536
    result=enroll_restored_host(target,witness_dir=tmp_path/'new-witness',assets=host_assets)
    assert result['status']=='prepared' and result['old_work_replayed'] is False
    with closing(sqlite3.connect(target/'source.db')) as db:
        rows=db.execute('SELECT file_path FROM reference_files').fetchall()
        assert len(rows)==321
        assert all(Path(row[0]).is_relative_to(target) and Path(row[0]).is_file() for row in rows)
        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]


def test_snapshot_receipts_explain_that_later_writes_are_not_included(installation,tmp_path,host_assets):
    """An old snapshot preserves its boundary and current source; a fresh snapshot preserves post-upgrade writes."""
    from backend.runtime.installation_backup import backup_installation
    from backend.runtime.installation_restore import restore_installation
    from backend.runtime.restored_enrollment import enroll_restored_host
    from backend.tools.base.db import ensure_migrations

    original,_=installation
    historical=tmp_path/'historical.db'
    ensure_migrations(str(historical),target_version=43)
    with closing(sqlite3.connect(original/'source.db')) as source, closing(sqlite3.connect(historical)) as target, target:
        for table in ('projects','tasks','repositories','reference_files','agent_worktrees','artifacts'):
            columns=[row[1] for row in source.execute(f'PRAGMA table_info({table})')]
            rows=source.execute(f'SELECT * FROM {table}').fetchall()
            target.executemany(f'INSERT INTO {table}({",".join(columns)}) VALUES({",".join("?" for _ in columns)})',rows)
    historical.replace(original/'source.db')
    backup_installation(original,tmp_path/'before-upgrade')
    ensure_migrations(str(original/'source.db'),existing_only=True)
    with closing(sqlite3.connect(original/'source.db')) as db, db:
        db.execute("UPDATE tasks SET title='Written after upgrade' WHERE id=1001")
        db.execute("INSERT INTO artifacts(project_id,task_id,type,file_path,content) VALUES(101,1001,'report','new.md','New report after upgrade')")
        db.execute("INSERT INTO runtime_model_settings(scope_key,revision,profile_json,updated_at) VALUES('global',1,NULL,1)")
    (original/'uploads/101/uploads/exact.txt').write_text('New source bytes after upgrade')
    with pytest.raises(RuntimeError,match='downgrade'):
        ensure_migrations(str(original/'source.db'),target_version=43)
    backup_installation(original,tmp_path/'after-upgrade')
    for bundle,expected_title,expected_body,expected_reports in [
        ('before-upgrade','Retained task',b'original evidence\n',1),
        ('after-upgrade','Written after upgrade',b'New source bytes after upgrade',2),
    ]:
        target=tmp_path/bundle.replace('upgrade','restored')
        receipt=restore_installation(tmp_path/bundle,target)
        assert receipt['data_recovery']['post_snapshot_writes']=='not_included'
        assert receipt['data_recovery']['transparent_downgrade'] is False
        assert receipt['data_recovery']['original_overwritten'] is False
        assert receipt['data_recovery']['original_availability']=='not_checked'
        assert receipt['data_recovery']['comparison_with_current_source']=='not_performed'
        enrolled=enroll_restored_host(target,witness_dir=tmp_path/(bundle+'-witness'),assets=host_assets)
        assert enrolled['data_recovery']==receipt['data_recovery']
        with closing(sqlite3.connect(target/'source.db')) as db:
            assert db.execute('SELECT title FROM tasks WHERE id=1001').fetchone()==(expected_title,)
            assert db.execute('SELECT count(*) FROM artifacts').fetchone()==(expected_reports,)
            assert db.execute('SELECT count(*) FROM runtime_model_settings').fetchone()==(expected_reports-1,)
        assert (target/'uploads/101/uploads/exact.txt').read_bytes()==expected_body
    with closing(sqlite3.connect(original/'source.db')) as db:
        assert db.execute('SELECT title FROM tasks WHERE id=1001').fetchone()==('Written after upgrade',)
        assert db.execute('SELECT count(*) FROM artifacts').fetchone()==(2,)


@pytest.mark.parametrize('damage', ['missing','same_size_change','oversize','symlink_leaf','symlink_parent','path_escape','identity','unsupported'])
def test_damaged_restoration_evidence_never_creates_authority(installation,tmp_path,host_assets,damage):
    """Missing, changed or redirected metadata cannot cross the fresh-enrollment boundary."""
    from backend.runtime.installation_backup import backup_installation
    from backend.runtime.installation_restore import restore_installation
    from backend.runtime.restored_enrollment import enroll_restored_host
    from backend.runtime.recovery_receipt import DETAILS_LIMIT

    original,_=installation
    backup_installation(original,tmp_path/'backup')
    target=tmp_path/'restored';restore_installation(tmp_path/'backup',target)
    marker=json.loads((target/'installation.json').read_text())
    receipt_path=target/marker['restoration']
    receipt=json.loads(receipt_path.read_text())
    assert receipt['format']==2 and receipt_path.stat().st_size<65536
    details=target/receipt['details']['path']
    if damage=='missing':details.unlink()
    elif damage=='same_size_change':
        raw=details.read_bytes();details.write_bytes(b' '+raw[1:])
    elif damage=='symlink_leaf':
        outside=tmp_path/'external-details';details.rename(outside);details.symlink_to(outside)
    elif damage=='symlink_parent':
        outside=tmp_path/'external-parent';details.parent.rename(outside);details.parent.symlink_to(outside,target_is_directory=True)
    else:
        if damage=='oversize':receipt['details']['bytes']=DETAILS_LIMIT+1
        elif damage=='path_escape':receipt['details']['path']='../external-details'
        elif damage=='identity':receipt['snapshot_id']='different-snapshot'
        else:receipt['format']=999
        receipt_path.write_text(json.dumps(receipt))
    with pytest.raises((OSError,ValueError)):
        enroll_restored_host(target,witness_dir=tmp_path/'new-witness',assets=host_assets)
    assert not (target/'authority').exists() and not (tmp_path/'new-witness').exists()
    assert json.loads((target/'installation.json').read_text())['status']=='restored_pending_enrollment'
    with closing(sqlite3.connect(target/'source.db')) as db:
        assert db.execute('SELECT title FROM tasks WHERE id=1001').fetchone()==('Retained task',)


def test_original_format1_restoration_receipt_remains_usable(installation,tmp_path,host_assets):
    """Previously completed small receipts still enroll, gaining an explicit snapshot limitation in the result."""
    from backend.runtime.installation_backup import backup_installation
    from backend.runtime.installation_restore import restore_installation
    from backend.runtime.restored_enrollment import enroll_restored_host

    original,_=installation
    backup_installation(original,tmp_path/'backup')
    target=tmp_path/'restored';receipt=restore_installation(tmp_path/'backup',target)
    receipt.pop('data_recovery')
    marker=json.loads((target/'installation.json').read_text())
    (target/marker['restoration']).write_text(json.dumps(receipt))
    result=enroll_restored_host(target,witness_dir=tmp_path/'new-witness',assets=host_assets)
    assert result['status']=='prepared'
    assert result['data_recovery']['post_snapshot_writes']=='not_included'


def test_abrupt_exit_after_details_keeps_partial_restore_inactive(installation,tmp_path):
    """A real child dies between metadata files; recovery preserves that path and uses another verified restore."""
    import subprocess
    import sys
    from backend.runtime.installation_backup import backup_installation,verify_backup
    from backend.runtime.installation_restore import restore_installation

    original,_=installation
    backup_installation(original,tmp_path/'backup')
    target=tmp_path/'interrupted'
    program='''import os,sys
from backend.runtime import recovery_receipt
from backend.runtime.installation_restore import restore_installation
write=recovery_receipt._write_new
def interrupt(path,value):
    """Exit this owned child only after complete restoration details reached disk."""
    write(path,value)
    if path.name=='details.json':os._exit(95)
recovery_receipt._write_new=interrupt
restore_installation(sys.argv[1],sys.argv[2])
'''
    child=subprocess.run([sys.executable,'-c',program,str(tmp_path/'backup'),str(target)],capture_output=True,timeout=20,check=False)
    assert child.returncode==95,child.stderr.decode()
    assert list(target.glob('.restorations/*/details.json'))
    assert not list(target.glob('.restorations/*/restoration.json'))
    assert not (target/'installation.json').exists()
    assert verify_backup(tmp_path/'backup')['status']=='complete'
    assert restore_installation(tmp_path/'backup',tmp_path/'recovered')['status']=='pending_enrollment'


def test_public_restore_output_discloses_snapshot_limits(installation,tmp_path):
    """The actual admin command exposes the loss boundary instead of requiring operators to read internal files."""
    from backend.runtime.installation_backup import backup_installation
    from backend.tests.cli.test_bootstrap import cli

    original,_=installation
    backup_installation(original,tmp_path/'backup')
    result=cli('restore-host','--backup',tmp_path/'backup','--destination',tmp_path/'restored')
    assert result.returncode==0,result.stderr
    receipt=json.loads(result.stdout)
    assert receipt['data_recovery']['post_snapshot_writes']=='not_included'
    assert 'escrituras posteriores' in receipt['data_recovery']['detail']


def test_snapshot_restoration_does_not_claim_original_host_still_exists(installation,tmp_path):
    """A portable backup remains restorable when its original path is absent, without inventing its availability."""
    from backend.runtime.installation_backup import backup_installation
    from backend.runtime.installation_restore import restore_installation

    original,_=installation
    backup_installation(original,tmp_path/'backup')
    original.rename(tmp_path/'retained-but-unavailable-at-old-path')
    receipt=restore_installation(tmp_path/'backup',tmp_path/'restored')
    assert receipt['data_recovery']['original_availability']=='not_checked'
    assert receipt['data_recovery']['original_overwritten'] is False
    assert 'original_preserved' not in receipt['data_recovery']

