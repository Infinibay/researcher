"""Verify installed recovery across two actual guest boots without inference or real credentials."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys

import httpx


def save(path, value):
    """Persist one original phase receipt before the guest kernel is restarted."""
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def helper():
    """Load only the copied evaluation helper; keep backend imports in the installed environment."""
    spec = importlib.util.spec_from_file_location('host_smoke', Path(__file__).with_name('host_smoke.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def authority_bytes(config):
    """Hash the three original authority files without recording credentials or mutable service logs."""
    return {key:hashlib.sha256(Path(config['authority'][key]).read_bytes()).hexdigest()
            for key in ('database','witness','mutex')}


def before(root, assets):
    """Prepare synthetic retained data and a real old-kernel registration, then leave it pending."""
    from backend.runtime.host_installation import initialize_host
    from backend.runtime.authority_journal import WitnessedAuthorityJournal
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.runtime.contracts import RunSpec
    from backend.runtime.peer_registry import PeerRegistry
    from backend.runtime.peer_process import boot_id, observer_namespace

    result = initialize_host(root/'original', witness_dir=root/'original-witness', assets=assets)
    helper().seed(root/'original')
    store = SQLiteRunStore(root/'original/source.db')
    run = store.admit(RunSpec(101,1001,'vm-fixture',1,'original-before-reboot','Retain this original intent','codex'))
    lease = store.claim(101,run.run_id,'original-guest')
    peer = PeerRegistry(store).prepare(lease,'native')
    config = json.loads((root/'original/runtime.json').read_text())
    with WitnessedAuthorityJournal(**config['authority']) as journal:
        journal.commit(journal.load(),transition_id='fixture-before-reboot',puts={'broker:active':'original-guest'})
    receipt = {'boot_id':boot_id(), 'observer_namespace':observer_namespace(),
               'authority_id':result['authority_id'], 'authority_hashes':authority_bytes(config),
               'run_id':run.run_id, 'peer_id':peer, 'resource_observations':result['resource_observations'],
               'model_turns':0, 'peer_state':'prepared', 'native_child_started':False}
    save(root/'before.json',receipt)


def command(*args):
    """Invoke one public installed administrative command once and retain its failure output."""
    result = subprocess.run([sys.executable,'-I','-m','backend.cli.bootstrap',*map(str,args)],
                            capture_output=True,text=True,timeout=60,check=False)
    if result.returncode:
        print(result.stderr, file=sys.stderr, flush=True)
        raise RuntimeError(f'Guest administrative command failed: {args[0]}')
    return json.loads(result.stdout)


def after(root, assets):
    """Observe another boot, restore as fresh authority and read retained data through the native API."""
    from backend.runtime.authority_journal import AuthorityUncertain, WitnessedAuthorityJournal
    from backend.runtime.host_installation import inspect_host
    from backend.runtime.peer_process import boot_id

    previous = json.loads((root/'before.json').read_text())
    assert boot_id() != previous['boot_id']
    original = root/'original'
    config = json.loads((original/'runtime.json').read_text())
    try:
        with WitnessedAuthorityJournal(**config['authority']) as journal:
            journal.load()
    except AuthorityUncertain:
        pass
    else:
        raise AssertionError('Normal authority accepted the prior kernel')
    command('backup-host','--directory',original,'--destination',root/'backup','--after-reboot')
    manifest = command('verify-backup','--backup',root/'backup')
    restored = root/'restored'
    command('restore-host','--backup',root/'backup','--destination',restored)
    enrolled = command('enroll-restored-host','--directory',restored,'--witness-dir',root/'fresh-witness','--assets',root/'assets.json')
    assert enrolled['authority_id'] != previous['authority_id']
    assert authority_bytes(config) == previous['authority_hashes']
    for database in (original/'source.db',restored/'source.db'):
        with sqlite3.connect(database) as db:
            assert db.execute('SELECT state,boot_id FROM runtime_peers WHERE id=?',(previous['peer_id'],)).fetchone() == ('prepared',previous['boot_id'])
            assert db.execute('SELECT COUNT(*) FROM runtime_inference_dispatches').fetchone() == (0,)
    with sqlite3.connect(restored/'source.db') as db:
        assert db.execute('SELECT peer_id,original_state FROM runtime_peer_archives').fetchall() == [(previous['peer_id'],'prepared')]
        assert db.execute('SELECT status FROM runtime_runs').fetchone() == ('superseded',)
        assert db.execute('SELECT status,ended_at,native_result_json FROM runtime_attempts').fetchone() == ('reconciling',None,None)
    probe = inspect_host(restored,probe=True)
    smoke = helper()
    with socket.socket() as binding:
        binding.bind(('127.0.0.1',0))
        port = binding.getsockname()[1]
    process,log = smoke.start(restored,root,port,1)
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',trust_env=False,timeout=15) as client:
            smoke.pair(client,restored)
            response = client.get('/api/tasks?project_id=101')
            response.raise_for_status()
            assert 'Explain the synthetic total' in response.text
            attachment = client.get('/api/files/7/download?project_id=101')
            attachment.raise_for_status()
            assert '137 units and 63 units' in attachment.text
    finally:
        service_exit = smoke.stop(process,log)
    with sqlite3.connect(restored/'source.db') as db:
        assert db.execute('SELECT COUNT(*) FROM runtime_runs').fetchone() == (1,)
        assert db.execute('SELECT COUNT(*) FROM runtime_inference_dispatches').fetchone() == (0,)
        assert db.execute('SELECT COUNT(*) FROM runtime_peers WHERE state!=\'closed\' AND id NOT IN (SELECT peer_id FROM runtime_peer_archives)').fetchone() == (0,)
    result = {'status':'passed','source_boot_id':previous['boot_id'],'observed_boot_id':boot_id(),
              'original_authority_unchanged':True,'normal_old_authority_refused':True,
              'old_peer_state_preserved':'prepared','archival_history_retained':True,
              'new_authority_id':enrolled['authority_id'],'kernel_probe':probe['kernel_probe'],
              'source_authority_id':previous['authority_id'],'resources':probe['resource_observations'],
              'snapshot_id':manifest['snapshot_id'],'schema_version':enrolled['schema_version'],
              'service_exit':service_exit,'installed_backend':True,'http_retained_data_verified':True,
              'model_turns':0,'real_credentials_copied':False,'old_work_replayed':False,
              'limits':'Controlled VM kernel restart and synthetic data. No power-loss, model inference, original-actor closure proof or historical user-data migration.'}
    save(root/'result.json',result)
    print('RESEARCHER-REBOOT-RESULT:'+json.dumps(result),flush=True)


def main():
    """Accept the fixed disposable guest paths and execute exactly the phase selected by PID1."""
    root = Path('/state')
    if not Path('/RESEARCHER_DISPOSABLE_VM').is_file() or os.getuid() != 1000:
        raise RuntimeError('This evaluator is only for the unprivileged disposable guest')
    import backend
    assert Path(backend.__file__).is_relative_to(root/'env')
    assets = json.loads((root/'assets.json').read_text())
    {'before':before,'after':after}[sys.argv[1]](root,assets)


if __name__ == '__main__':
    main()
