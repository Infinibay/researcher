"""Fill a real durable volume through owned processes, retaining installed product data.

Only synthetic fixture paths are used. The report lives on a separate evaluation
disk so it can record ENOSPC without pretending the full product disk was writable.
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

ROOT = Path('/bounded/installation')
REPORT = Path('/state/storage-result.json')

WRITER = '''import errno, os, pathlib, sys, time
root = pathlib.Path(sys.argv[1])
for directory in ('sources/host-smoke/.ken', 'control/development/unfinished', 'control/native-state/retained', 'uploads/filler'):
    if os.fork() == 0:
        target = root/directory
        target.mkdir(parents=True, exist_ok=True)
        count = 0
        try:
            while True:
                with (target/str(count)).open('xb') as stream:
                    stream.write(b'x'*65536)
                    stream.flush()
                    os.fsync(stream.fileno())
                count += 1
        except OSError as error:
            print(str(error.errno) + ':' + str(count), flush=True)
        time.sleep(3600)
        os._exit(0)
os.wait()
'''


def save(value):
    """Persist only evaluation evidence outside the deliberately full product volume."""
    with REPORT.open('w') as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def helper():
    """Import the copied synthetic-data helper while keeping backend imports installed."""
    spec = importlib.util.spec_from_file_location('host_smoke', Path(__file__).with_name('host_smoke.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exercise():
    """Prove aggregate exhaustion across four writable roots and physical Stop without free disk."""
    from backend.api.runtime_dependencies import configured_storage_guard
    from backend.runtime.contracts import RunConflict
    from backend.runtime.execution_domain import ExecutionDomain
    from backend.runtime.host_installation import initialize_host, host_environment, inspect_host
    from backend.runtime.storage_volume import StorageVolume

    assets = json.loads(Path('/state/assets.json').read_text())
    assets['storage'] = {'mount': '/bounded', 'max_bytes': 128*1024**2, 'admission_free_bytes': 4*1024**2}
    prepared = initialize_host(ROOT, witness_dir='/bounded/witness', assets=assets)
    helper().seed(ROOT)
    os.environ.update(prepared['environment'])
    # The module was imported before selecting the host's environment in this fixture.
    from backend.api import config as api_config
    api_config.UPLOAD_DIR = str(ROOT/'uploads')
    guard = configured_storage_guard()
    guard()
    config = json.loads((ROOT/'runtime.json').read_text())
    volume = StorageVolume(config['storage_receipt'])
    code = ROOT/'control/useful-uncommitted.py'
    with code.open('x') as stream:
        stream.write('"""Retained synthetic work."""\nanswer = 200\n')
        stream.flush(); os.fsync(stream.fileno())
    digest = hashlib.sha256(code.read_bytes()).hexdigest()
    probe = inspect_host(ROOT, probe=True)['kernel_probe']
    group = Path(assets['cgroup_parent'])/'storage-writers'
    group.mkdir(mode=0o700)
    observations = bytearray()
    with ExecutionDomain.open(group) as domain:
        domain.limit(pids=16, memory_bytes=256*1024**2, cpu_millis=250)
        child = domain.spawn([sys.executable, '-I', '-S', '-c', WRITER, str(ROOT)])
        child.stdin.close()
        try:
            deadline = time.monotonic()+30
            while observations.count(b'\n') < 4:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Original filesystem writers did not report exhaustion')
                readable, _, _ = select.select([child.stdout], [], [], .25)
                if readable:
                    data = os.read(child.stdout.fileno(), 4096)
                    if not data:
                        raise RuntimeError('Original writers exited before four exhaustion receipts')
                    observations.extend(data)
            rows = [list(map(int, row.split(b':'))) for row in observations.splitlines()]
            assert len(rows) == 4 and all(code == errno.ENOSPC for code, _ in rows), rows
            try:
                guard()
            except RunConflict:
                admission_rejected = True
            else:
                raise AssertionError('New work remained admitted on the full volume')
            observed = volume.check([ROOT, '/bounded/witness'])
            assert host_environment(ROOT)['INFINIBAY_DB'] == str(ROOT/'source.db')
            closure = domain.retire(timeout=5)
            assert closure.removed
            child.wait(timeout=5)
        finally:
            if group.exists():
                domain.retire(timeout=5)
            child.close_handles()
    assert hashlib.sha256(code.read_bytes()).hexdigest() == digest
    with sqlite3.connect(ROOT/'source.db') as db:
        assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
    save({'storage': observed, 'writer_receipts': rows, 'admission_rejected': admission_rejected,
          'domain_removed_while_full': closure.removed, 'resources': closure.resources,
          'retained_sha256': digest, 'kernel_probe': probe, 'integrity_before_remount': 'ok'})


def missing():
    """Reject the unmounted path without creating replacement directories or product state."""
    from backend.runtime.storage_volume import StorageVolume

    previous = json.loads(REPORT.read_text())
    receipt = {key: value for key, value in previous['storage'].items()
               if key not in ('enforced', 'kind', 'available_bytes', 'available_inodes')}
    before = list(Path('/bounded').iterdir())
    try:
        StorageVolume(receipt).check([ROOT])
    except (ValueError, OSError):
        pass
    else:
        raise AssertionError('Missing mount was accepted')
    assert list(Path('/bounded').iterdir()) == before == []
    previous['missing_mount_rejected'] = True
    save(previous)


def retained():
    """Reopen the original full volume and verify useful work and both databases after remount."""
    from backend.runtime.host_installation import host_environment

    previous = json.loads(REPORT.read_text())
    host_environment(ROOT)
    assert hashlib.sha256((ROOT/'control/useful-uncommitted.py').read_bytes()).hexdigest() == previous['retained_sha256']
    config = json.loads((ROOT/'runtime.json').read_text())
    for path in (ROOT/'source.db', Path(config['authority']['database'])):
        with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True) as db:
            assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
            assert db.execute('PRAGMA foreign_key_check').fetchall() == []
    previous['integrity_after_remount'] = 'ok'
    previous['unfinished_work_preserved'] = True
    save(previous)


if __name__ == '__main__':
    if os.getuid() != 1000 or not Path('/RESEARCHER_DISPOSABLE_VM').is_file():
        raise RuntimeError('Storage evaluation requires its unprivileged disposable guest')
    {'exercise': exercise, 'missing': missing, 'retained': retained}[sys.argv[1]]()
