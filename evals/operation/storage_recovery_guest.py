"""Exercise failed SQLite writes, service closure and fresh bounded restore across two disposable guest boots.

Only synthetic fixture filler files are removed. The evidence disk remains
separate from the deliberately exhausted product volume; no model is called.
"""

import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import sqlite3
import sys
import time

import httpx

ROOT = Path('/bounded/installation')
REPORT = Path('/state/storage-result.json')
FILLERS = ('sources/host-smoke/.ken','control/development/unfinished',
           'control/native-state/retained','uploads/filler')


def helpers():
    """Read the copied fixture helper while product imports keep using the installed package."""
    spec=importlib.util.spec_from_file_location('storage_guest',Path(__file__).with_name('storage_guest.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module,module.helper()


def assets():
    """Select only synthetic account and pre-copied public executables with explicit storage policy."""
    value=json.loads(Path('/state/assets.json').read_text())
    value['storage']={'mount':'/bounded','max_bytes':128*1024**2,'admission_free_bytes':4*1024**2}
    return value


def save(value):
    """Persist evaluation observations on the separate evidence disk, including failures on the product disk."""
    with REPORT.open('w') as stream:
        json.dump(value,stream,indent=2);stream.flush();os.fsync(stream.fileno())


def fill_tail():
    """Exhaust remaining individual filesystem blocks after the larger concurrent fixture writes."""
    with (ROOT/'fixture-tail').open('ab',buffering=0) as stream:
        try:
            while True:
                stream.write(b'x'*4096);os.fsync(stream.fileno())
        except OSError as error:
            if error.errno!=errno.ENOSPC:raise


def fill_volume():
    """Run four real filesystem writers in one owned group, retaining their ENOSPC observations and reaping them."""
    from backend.runtime.execution_domain import ExecutionDomain

    storage,_=helpers();group=Path(assets()['cgroup_parent'])/'storage-failure-writers'
    group.mkdir(mode=0o700);data=bytearray()
    with ExecutionDomain.open(group) as domain:
        domain.limit(pids=16,memory_bytes=256*1024**2,cpu_millis=500)
        child=domain.spawn([sys.executable,'-I','-S','-c',storage.WRITER,str(ROOT)])
        child.stdin.close()
        try:
            deadline=time.monotonic()+30
            while data.count(b'\n')<4:
                if time.monotonic()>=deadline:raise TimeoutError('Original fixture writers did not report exhaustion')
                if select.select([child.stdout],[],[],.25)[0]:
                    chunk=os.read(child.stdout.fileno(),4096)
                    if not chunk:raise RuntimeError('Original writers exited before exhaustion receipts')
                    data.extend(chunk)
            rows=[list(map(int,line.split(b':'))) for line in data.splitlines()]
            assert len(rows)==4 and all(row[0]==errno.ENOSPC for row in rows)
        finally:
            closure=domain.retire(timeout=5);child.wait(timeout=5);child.close_handles()
    fill_tail()
    return {'writer_receipts':rows,'domain_removed_while_full':closure.removed}


def inspect_http(smoke,root,port):
    """Read the original synthetic project through a fresh owner session without dispatching work."""
    with httpx.Client(base_url=f'http://127.0.0.1:{port}',trust_env=False,timeout=5) as client:
        smoke.pair(client,root)
        response=client.get('/api/projects/101');response.raise_for_status()
        return response.json()['name']


def before():
    """Keep an API live while a product transaction runs out of disk, then preserve its uncertain receipt before reboot."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.host_installation import initialize_host
    from backend.runtime.peer_process import boot_id
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.runtime.storage_volume import configured_storage

    _,smoke=helpers();initialize_host(ROOT,witness_dir='/bounded/witness',assets=assets());smoke.seed(ROOT)
    code=ROOT/'control/useful-uncommitted.py';code.write_text('"""Retained synthetic work."""\nanswer = 200\n')
    config=json.loads((ROOT/'runtime.json').read_text())
    process,log=smoke.start(ROOT,Path('/state'),8765,'full-disk')
    result={'first_boot_id':boot_id(),'model_turns':0,'retained_sha256':hashlib.sha256(code.read_bytes()).hexdigest()}
    try:
        result['original_project_name']=inspect_http(smoke,ROOT,8765)
        result['service_group']=json.loads((ROOT/'service/service-resources.json').read_text())['domain_path']
        try:
            with SQLiteRunStore(ROOT/'source.db')._transaction(write=True) as db:
                db.execute("UPDATE projects SET name='UNCOMMITTED FULL-DISK CHANGE' WHERE id=101")
                result['transaction_small_write_completed']=True
                result.update(fill_volume())
                db.execute("INSERT INTO events_log(event_type,event_source,event_data_json) VALUES('fixture.full_disk','fixture',?)",('"'+'x'*(8*1024**2)+'"',))
        except sqlite3.DatabaseError as error:
            assert error.sqlite_errorcode & 0xff == sqlite3.SQLITE_FULL
            result['sqlite_failure']=error.sqlite_errorname
        else:raise AssertionError('Full-disk transaction unexpectedly committed')
        with sqlite3.connect((ROOT/'source.db').as_uri()+'?mode=ro',uri=True) as db:
            assert db.execute('SELECT name FROM projects WHERE id=101').fetchone()[0]==result['original_project_name']
            assert db.execute("SELECT COUNT(*) FROM events_log WHERE event_type='fixture.full_disk'").fetchone()==(0,)
            assert db.execute('PRAGMA integrity_check').fetchone()==('ok',)
        result['failed_transaction_rolled_back']=True
        fill_tail()
        try:configured_storage(config,[ROOT,'/bounded/witness'],admission=True)
        except RunConflict:result['new_work_refused']=True
        else:raise AssertionError('Full storage admitted new work')
    finally:
        result['original_launcher_exit']=smoke.stop(process,log)
    assert not Path(result['service_group']).exists()
    result['service_group_removed']=True
    receipt=ROOT/'service/service-resources.json'
    result['original_service_receipt']=json.loads(receipt.read_text())
    result['original_service_receipt_sha256']=hashlib.sha256(receipt.read_bytes()).hexdigest()
    result['service_closure_recorded']=result['original_service_receipt']['status']=='closed'
    assert result['original_launcher_exit']==(143 if result['service_closure_recorded'] else 1)
    result['before_reboot']=smoke.snapshot(ROOT/'source.db');save(result)


def remove_fixture_fillers():
    """Free only the disposable test's exact known filler files, never product cleanup or operator data."""
    removed=0
    for relative in FILLERS:
        for path in (ROOT/relative).iterdir():
            assert path.name.isdigit() and path.is_file() and not path.is_symlink()
            path.unlink();removed+=1
    (ROOT/'fixture-tail').unlink()
    return removed


def after():
    """Archive verified prior-kernel state, restore to another path and enroll the selected real bounded volume."""
    from backend.runtime.installation_backup import backup_installation
    from backend.runtime.installation_restore import restore_installation
    from backend.runtime.restored_enrollment import enroll_restored_host
    from backend.runtime.peer_process import boot_id

    _,smoke=helpers();result=json.loads(REPORT.read_text())
    result['second_boot_id']=boot_id();assert result['second_boot_id']!=result['first_boot_id']
    result['fixture_files_removed_explicitly']=remove_fixture_fillers()
    bundle=Path('/state/recovery-backup')
    backup_installation(ROOT,bundle,after_reboot=True)
    backup=json.loads((bundle/'manifest.json').read_text())
    restored=Path('/bounded/restored');restore_installation(bundle,restored)
    enrollment=enroll_restored_host(restored,witness_dir='/bounded/restored-witness',assets=assets())
    assert enrollment['storage']['enforced'] is True
    config=json.loads((restored/'runtime.json').read_text())
    assert config['storage_receipt']['policy']==assets()['storage']
    result['fresh_storage_receipt']=config['storage_receipt']
    process,log=smoke.start(restored,Path('/state'),8766,'restored-after-full-disk')
    try:
        assert inspect_http(smoke,restored,8766)==result['original_project_name']
        result['restored_http_read']=True
        result['restored_database']=smoke.snapshot(restored/'source.db')
        assert not result['restored_database']['runs'] and not result['restored_database']['dispatches']
        assert result['restored_database']['integrity']=='ok'
        assert hashlib.sha256((restored/'control/useful-uncommitted.py').read_bytes()).hexdigest()==result['retained_sha256']
    finally:
        result['restored_launcher_exit']=smoke.stop(process,log)
    assert result['restored_launcher_exit']==143
    receipt=json.loads((restored/'service/service-resources.json').read_text())
    assert receipt['status']=='closed' and receipt['domain_removed'] is True and not Path(receipt['domain_path']).exists()
    assert hashlib.sha256((ROOT/'service/service-resources.json').read_bytes()).hexdigest()==result['original_service_receipt_sha256']
    result.update(recovered=True,old_work_replayed=False,original_service_receipt_preserved=True,
                  backup_reboot_evidence=backup['reboot_evidence'],restored_group_removed=True,
                  original_data_preserved=True,status='passed')
    save(result)


if __name__=='__main__':
    if os.getuid()!=1000 or not Path('/RESEARCHER_DISPOSABLE_VM').is_file():
        raise RuntimeError('Storage recovery requires its unprivileged disposable guest')
    {'before':before,'after':after}[sys.argv[1]]()
