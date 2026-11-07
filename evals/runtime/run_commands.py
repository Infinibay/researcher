"""Exercise current broker commands, containment, cancellation and lost RPC; zero model turns."""

import argparse
import asyncio
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


def waiting_child(marker, gate):
    """Create a detached child whose next observable output requires an explicit host-controlled input."""
    child = (
        "from pathlib import Path;import time\n"
        f"print({marker!r},flush=True)\n"
        f"while not Path({gate!r}).exists():time.sleep(.01)\n"
        "print('FORBIDDEN_LATE_EFFECT',flush=True)\n"
    )
    return ("import subprocess,sys,time\n"
            f"subprocess.Popen([sys.executable,'-I','-S','-c',{child!r}],start_new_session=True)\n"
            "time.sleep(30)")


def receipt(key, job):
    """Retain the actual terminal command result without confusing closure with a successful exit."""
    return {'key': key, 'job_id': job.job_id, 'status': job.status,
            'exit_code': job.exit_code, 'cancel_requested': job.cancel_requested,
            'local_execution_closed': job.local_execution_closed,
            'stdout': job.stdout.decode(errors='replace'), 'stderr': job.stderr.decode(errors='replace')}


async def database_contention(root, args):
    """Close a detached command before releasing its locked source database, using its own attempt."""
    from backend.runtime.contracts import CommandSpec
    from evals.runtime.kernel_trial import prepare, pin_peer, wait_closed, wait_empty, wait_output

    trial = prepare(root / 'database-contention', args.codex_binary, args.cgroup_parent)
    python = str(Path(sys.executable).resolve())
    result = {}
    async with trial.open(), trial.commands() as worker:
        handle = await worker.start(trial.lease, 'busy-database', CommandSpec(
            (python, '-I', '-S', '-c', waiting_child('BUSY_READY', 'release-busy')), '.', 30, 4096))
        await wait_output(worker, handle, b'BUSY_READY')
        pinned = pin_peer(worker)
        lock = sqlite3.connect(trial.database)
        cancellation = None
        try:
            lock.execute('BEGIN IMMEDIATE')
            cancellation = asyncio.create_task(handle.cancel())
            await wait_closed(pinned, timeout=5)
            await wait_empty(trial.domain_path)
            assert not (trial.domain_path / 'cgroup.procs').read_text().strip()
            result.update(namespace_closed_before_database_unlock=True,
                                               domain_empty_before_database_unlock=True)
        finally:
            lock.rollback()
            lock.close()
            os.close(pinned)
        stopped = await asyncio.wait_for(cancellation, 10)
        assert stopped.local_execution_closed and stopped.cancel_requested and stopped.exit_code != 0
        (trial.workspace / 'release-busy').touch()
        assert b'FORBIDDEN_LATE_EFFECT' not in stopped.stdout
        result['job'] = receipt('busy-database', stopped)
    result['lifecycle'] = json.loads((trial.root / 'lifecycle.json').read_text())
    assert result['lifecycle']['domain_removed'] and result['lifecycle']['all_peers_closed']
    return result


async def main(args):
    """Run two independently provisioned owners so stopping one must preserve the other's active work."""
    from backend.runtime.contracts import CommandSpec
    from evals.runtime.kernel_trial import prepare, pin_peer, wait_closed, wait_output

    root = REPO / '.researcher/evaluations' / ('command-integration-' + uuid4().hex[:8])
    root.mkdir(mode=0o700, parents=True)
    alpha = prepare(root / 'alpha', args.codex_binary, args.cgroup_parent)
    beta = prepare(root / 'beta', args.codex_binary, args.cgroup_parent, project_id=202, task_id=2002)
    python = str(Path(sys.executable).resolve())
    for trial, marker in ((alpha, 'ALPHA_ONLY'), (beta, 'BETA_ONLY')):
        (trial.workspace / 'private.txt').write_text(marker)
    (alpha.workspace / '.codex').mkdir()
    (alpha.workspace / '.codex/config.toml').write_text(
        '[permissions.researcher_jobs.filesystem]\n' + json.dumps(str(beta.workspace)) +
        '="read"\n[permissions.researcher_jobs.network]\nenabled=true\n')
    results = {'status': 'starting', 'model_turns_submitted': 0, 'commands': [],
               'composition': 'broker_command_executor', 'independent_authorities': True}
    print('Command integration:', root, flush=True)
    try:
        if args.db_contention:
            results['database_contention'] = await database_contention(root, args)
        async with alpha.open(), beta.open(), alpha.commands() as worker_a, beta.commands() as worker_b:
            for worker, trial, key, argv in (
                (worker_a, alpha, 'alpha-inside', ('/bin/cat', 'private.txt')),
                (worker_b, beta, 'beta-inside', ('/bin/cat', 'private.txt')),
                (worker_a, alpha, 'outside', ('/bin/cat', str(beta.workspace / 'private.txt'))),
                (worker_a, alpha, 'network', (python, '-I', '-S', '-c', 'import socket;socket.socket()')),
            ):
                job = await (await worker.start(trial.lease, key, CommandSpec(argv, '.', 5, 4096))).wait()
                results['commands'].append(receipt(key, job))
            assert results['commands'][0]['stdout'] == 'ALPHA_ONLY'
            assert results['commands'][1]['stdout'] == 'BETA_ONLY'
            assert results['commands'][2]['exit_code'] != 0 and 'BETA_ONLY' not in results['commands'][2]['stdout']
            assert results['commands'][3]['exit_code'] != 0 and 'PermissionError' in results['commands'][3]['stderr']


            a = await worker_a.start(alpha.lease, 'cancel-detached', CommandSpec(
                (python, '-I', '-S', '-c', waiting_child('DETACHED_READY', 'release-detached')), '.', 30, 4096))
            other_code = "from pathlib import Path;import time\nprint('OTHER_READY',flush=True)\nwhile not Path('release-other').exists():time.sleep(.01)\nprint('OTHER_COMPLETED',flush=True)"
            b = await worker_b.start(beta.lease, 'other-owner', CommandSpec((python, '-I', '-S', '-c', other_code), '.', 30, 4096))
            await wait_output(worker_a, a, b'DETACHED_READY')
            await wait_output(worker_b, b, b'OTHER_READY')
            pinned = pin_peer(worker_a)
            try:
                started = time.monotonic()
                await asyncio.to_thread(alpha.store.cancel, 101, alpha.run.run_id)
                stopped = await asyncio.wait_for(a.wait(), 10)
                await wait_closed(pinned)
                elapsed = time.monotonic() - started
            finally:
                os.close(pinned)
            assert stopped.local_execution_closed and stopped.cancel_requested and stopped.exit_code != 0
            (alpha.workspace / 'release-detached').touch()
            assert b'FORBIDDEN_LATE_EFFECT' not in stopped.stdout
            assert not worker_b._commands[b.job_id].task.done(), 'Other owner did not survive until its explicit release'
            (beta.workspace / 'release-other').touch()
            untouched = await asyncio.wait_for(b.wait(), 10)
            assert untouched.exit_code == 0 and not untouched.cancel_requested
            assert b'OTHER_COMPLETED' in untouched.stdout
            results['stop'] = {'seconds': elapsed, 'detached_child_observed_ready': True,
                               'original_namespace_closed': True, 'other_owner_survived_until_release': True,
                               'stopped': receipt('cancel-detached', stopped), 'unaffected': receipt('other-owner', untouched)}

            if args.peer_loss:
                from backend.research.models import ResearchForbidden
                from backend.research.sqlite_store import SQLiteResearchStore
                research = SQLiteResearchStore(beta.database)
                token = research.issue_grant(project_id=202, task_id=2002, agent_id='diagnostic',
                                             permissions={'sources.read', 'sources.capture'})
                beta.store.bind_grant(beta.lease, research.authorize(token).grant_id)
                loss = await worker_b.start(beta.lease, 'connection-loss', CommandSpec(
                    (python, '-I', '-S', '-c', waiting_child('LOSS_READY', 'release-loss')), '.', 30, 4096))
                await wait_output(worker_b, loss, b'LOSS_READY')
                pinned = pin_peer(worker_b)
                try:
                    # Break this original RPC read channel; never signal a PID from inside a namespace.
                    worker_b.rpc._endpoint._transports[0].close()
                    uncertain = await asyncio.wait_for(loss.wait(), 10)
                    await wait_closed(pinned)
                finally:
                    os.close(pinned)
                assert uncertain.status == 'unknown' and uncertain.exit_code is None and uncertain.local_execution_closed
                assert beta.store.get(202, beta.run.run_id).status == 'reconciling'
                try:
                    research.authorize(token)
                except ResearchForbidden:
                    pass
                else:
                    raise AssertionError('Lost command RPC retained its business grant')
                (beta.workspace / 'release-loss').touch()
                assert b'FORBIDDEN_LATE_EFFECT' not in uncertain.stdout
                results['peer_loss'] = {'rpc_read_channel_lost': True, 'original_namespace_closed': True,
                                        'business_grant_revoked': True, 'job': receipt('connection-loss', uncertain)}
        for name, trial in (('alpha', alpha), ('beta', beta)):
            lifecycle = json.loads((trial.root / 'lifecycle.json').read_text())
            assert lifecycle['domain_removed'] and lifecycle['all_peers_closed']
            results[name + '_lifecycle'] = lifecycle
        assert (alpha.workspace / 'private.txt').read_text() == 'ALPHA_ONLY'
        assert (beta.workspace / 'private.txt').read_text() == 'BETA_ONLY'
        results['status'] = 'passed'
    except BaseException as error:
        results.update(status='failed', error_type=type(error).__name__)
        raise
    finally:
        (root / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps({'status': results['status'], 'model_turns_submitted': 0}), flush=True)


if __name__ == '__main__':
    from evals.runtime.kernel_trial import arguments

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', required=True, help='Run real local processes; no model calls')
    parser.add_argument('--peer-loss', action='store_true')
    parser.add_argument('--db-contention', action='store_true')
    asyncio.run(main(arguments(parser)))
