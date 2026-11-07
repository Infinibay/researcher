"""Verify installed recovery across two actual guest boots without inference or real credentials."""

import hashlib
import asyncio
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


def command_identity(namespace_pid, peer):
    """Locate the observed command child inside its exact live private namespace, without signaling it."""
    from backend.runtime.peer_process import start_ticks

    matches = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            namespace = (entry/'ns/pid').stat().st_ino
            ids = next(line.split()[1:] for line in (entry/'status').read_text().splitlines() if line.startswith('NSpid:'))
            if namespace == peer['init_namespace'] and int(ids[-1]) == namespace_pid:
                matches.append({'pid':int(entry.name), 'start_ticks':start_ticks(int(entry.name)),
                                'namespace':namespace})
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    if len(matches) != 1:
        raise RuntimeError('The original command child was not uniquely observed alive')
    return matches[0]


async def before_active(root, assets):
    """Keep a real native command peer alive while PID1 reboots, preserving an earlier completed command."""
    from backend.runtime.authority_journal import WitnessedAuthorityJournal
    from backend.runtime.broker_profile import CodexAsset
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.contracts import CommandSpec, RunSpec
    from backend.runtime.execution_domain import ExecutionDomain
    from backend.runtime.host_installation import initialize_host
    from backend.runtime.native_commands import broker_command_executor
    from backend.runtime.peer_broker import PeerBroker
    from backend.runtime.peer_process import NamespaceIdentity, boot_id, observer_namespace, start_ticks
    from backend.runtime.peer_registry import AttemptPeers
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.runtime.workspaces import WorkspaceRegistry

    original = root/'original'
    initialized = initialize_host(original, witness_dir=root/'original-witness', assets=assets)
    helper().seed(original)
    store = SQLiteRunStore(original/'source.db')
    correction = store.correct_context(project_id=101, task_id=1001, expected_version=1,
        operation_key='owner-context', statement='Conservar el cálculo terminado y no repetir comandos tras el reinicio.',
        source_kind='user_message', source_reference='scripted-owner')
    workspace = original/'sources/host-smoke'
    binding = WorkspaceRegistry(store.database, original/'sources').bind(101, 11)
    run = store.admit(RunSpec(101,1001,'vm-fixture',correction,
        'original-before-reboot','Retain the completed calculation and interrupted command without replay','codex'), binding=binding)
    lease, peers = AttemptPeers.claim(store,101,run.run_id,'original-guest',lease_seconds=120)
    config = json.loads((original/'runtime.json').read_text())
    domain_path = Path(assets['cgroup_parent'])/'active-before-reboot'
    domain_path.mkdir(mode=0o700)
    with ExecutionDomain.open(domain_path) as domain, WitnessedAuthorityJournal(**config['authority']) as journal:
        broker = PeerBroker(journal,domain)
        async with AsyncPeerBroker(broker) as owner:
            async with broker_command_executor(owner=owner, registry=peers.registry,
                    lease=lease, workspace=workspace, asset=CodexAsset.inspect(assets['codex_binary'])) as worker:
                python = str(Path(sys.executable).resolve())
                completed_handle = await worker.start(lease,'completed-calculation',CommandSpec(
                    (python,'-I','-S','-c','print(137+63)'),'.',30,4096))
                completed = await completed_handle.wait()
                assert completed.status == 'exited' and completed.exit_code == 0 and completed.stdout == b'200\n'
                child_code = "import os,time;print('ACTIVE_COMMAND_READY '+str(os.getpid()),flush=True);time.sleep(120)"
                active = await worker.start(lease,'interrupted-command',CommandSpec(
                    (python,'-I','-S','-c',child_code),'.',120,4096))
                async with asyncio.timeout(30):
                    while True:
                        worker._changed.clear()
                        state = worker._commands[active.job_id]
                        lines = bytes(state.stdout).decode().splitlines()
                        ready = [line for line in lines if line.startswith('ACTIVE_COMMAND_READY ')]
                        if ready:
                            break
                        if state.task.done():
                            raise RuntimeError('Native command ended before its active readiness marker')
                        await worker._changed.wait()
                peer = peers.registry.inspect(worker.peer_id)
                assert NamespaceIdentity.capture(peer['init_pid']) == NamespaceIdentity.from_record(peer)
                child = command_identity(int(ready[0].split()[-1]),peer)
                with sqlite3.connect(store.database) as db:
                    states = dict(db.execute('SELECT id,state FROM runtime_peers'))
                    assert db.execute('SELECT count(*) FROM runtime_inference_dispatches').fetchone() == (0,)
                receipt = {'boot_id':boot_id(),'observer_namespace':observer_namespace(),
                    'authority_id':initialized['authority_id'],'authority_hashes':authority_bytes(config),
                    'run_id':run.run_id,'attempt_id':lease.attempt_id,'peer_id':worker.peer_id,
                    'peer_state':'bound','peer_states':states,'peer_identity':peer,
                    'resource_observations':initialized['resource_observations'],
                    'model_turns':0,'native_child_started':True,'active_command':True,
                    'holder':{'pid':os.getpid(),'start_ticks':start_ticks(os.getpid()),'namespace':observer_namespace()},
                    'command_child':child,'completed_job_id':completed.job_id,'active_job_id':active.job_id,
                    'completed_stdout':'200\n','domain_path':str(domain_path),'correction':correction}
                save(root/'before.json',receipt)
                save(root/'active-ready.json',{'ready':True})
                print('RESEARCHER-GUEST-ACTIVE-READY',flush=True)
                # PID1 must restart while this original owner is still alive.
                await active.wait()
                raise RuntimeError('Active command returned instead of being interrupted by the guest reboot')


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
    expected_states = previous.get('peer_states', {previous['peer_id']:previous['peer_state']})
    for database in (original/'source.db',restored/'source.db'):
        with sqlite3.connect(database) as db:
            assert dict(db.execute('SELECT id,state FROM runtime_peers')) == expected_states
            assert {row[0] for row in db.execute('SELECT boot_id FROM runtime_peers')} == {previous['boot_id']}
            assert db.execute('SELECT COUNT(*) FROM runtime_inference_dispatches').fetchone() == (0,)
    with sqlite3.connect(restored/'source.db') as db:
        assert dict(db.execute('SELECT peer_id,original_state FROM runtime_peer_archives')) == expected_states
        assert db.execute('SELECT status FROM runtime_runs').fetchone() == ('superseded',)
        assert db.execute('SELECT status,ended_at,native_result_json FROM runtime_attempts').fetchone() == ('reconciling',None,None)
    active_evidence = None
    if previous.get('active_command'):
        from backend.runtime.sqlite_runs import SQLiteRunStore

        witness = json.loads((root/'init-active-observation.json').read_text())
        assert witness['boot_id'] == previous['boot_id'] and witness['holder_alive'] and witness['command_alive'] and witness['peer_alive']
        old = SQLiteRunStore(original/'source.db')
        new = SQLiteRunStore(restored/'source.db')
        assert new.get_job(101,previous['completed_job_id']) == old.get_job(101,previous['completed_job_id'])
        active_job = new.get_job(101,previous['active_job_id'])
        assert active_job.status == 'unknown' and active_job.exit_code is None and not active_job.local_execution_closed
        assert old.get_job(101,previous['active_job_id']).status == 'dispatching'
        assert new.context_snapshot(101,1001) == old.context_snapshot(101,1001)
        with sqlite3.connect(restored/'source.db') as db:
            assert db.execute('SELECT count(*) FROM runtime_jobs').fetchone() == (2,)
        active_evidence = {'holder_and_native_and_command_observed_alive_at_reboot':True,
            'completed_job_preserved':True,'completed_stdout':previous['completed_stdout'],
            'interrupted_status':active_job.status,'interrupted_exit_code':active_job.exit_code,
            'archived_peer_falsely_marked_closed':False,'context_preserved':True,'commands_replayed':False,
            'init_witness':witness}
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
              'old_peer_state_preserved':previous['peer_state'],'archival_history_retained':True,
              'new_authority_id':enrolled['authority_id'],'kernel_probe':probe['kernel_probe'],
              'source_authority_id':previous['authority_id'],'resources':probe['resource_observations'],
              'snapshot_id':manifest['snapshot_id'],'schema_version':enrolled['schema_version'],
              'service_exit':service_exit,'installed_backend':True,'http_retained_data_verified':True,
              'model_turns':0,'real_credentials_copied':False,'old_work_replayed':False,
              'active_process_evidence':active_evidence,
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
    active = json.loads((root/'eval-mode.json').read_text()).get('active_command',False)
    if sys.argv[1] == 'before' and active:
        asyncio.run(before_active(root,assets))
    else:
        {'before':before,'after':after}[sys.argv[1]](root,assets)


if __name__ == '__main__':
    main()
