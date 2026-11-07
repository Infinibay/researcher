"""Kill only an original trial holder and recover its broker domain without a source DB writer; zero models."""

import argparse
import asyncio
import json
import os
import signal
import sqlite3
import sys
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


async def holder(root, codex_binary, cgroup_parent):
    """Start one real detached native command and publish readiness only after its stdout barrier."""
    from backend.runtime.contracts import CommandSpec
    from evals.runtime.kernel_trial import prepare, wait_output
    from evals.runtime.run_commands import waiting_child

    trial = prepare(root / 'holder', codex_binary, cgroup_parent)
    async with trial.open(), trial.commands() as worker:
        handle = await worker.start(trial.lease, 'parent-loss', CommandSpec(
            (str(Path(sys.executable).resolve()), '-I', '-S', '-c', waiting_child('DETACHED_READY', 'release-after-loss')),
            '.', 30, 4096))
        await wait_output(worker, handle, b'DETACHED_READY')
        identity = {'run_id': trial.run.run_id, 'job_id': handle.job_id,
                    'peer_id': worker.peer_id, 'grant_id': trial.broker.grant_id,
                    'authority': trial.authority, 'domain_path': str(trial.domain_path),
                    'peer': worker.peers.inspect(worker.peer_id)}
        (root / 'identity.json').write_text(json.dumps(identity, indent=2) + '\n')
        print('READY', flush=True)
        await handle.wait()


def recover_owned(root):
    """Retire only domains attested in this fresh trial after its original holder has been reaped."""
    from backend.runtime.authority_journal import WitnessedAuthorityJournal
    from backend.runtime.execution_domain import DomainIdentity, ExecutionDomain
    from backend.runtime.peer_broker import PeerBroker

    prepared = root / 'holder/preparation.json'
    if not prepared.exists():
        return
    authority = json.loads(prepared.read_text())['authority']
    with WitnessedAuthorityJournal(**authority) as journal:
        grants = [(key.split('broker:grant:', 1)[1], value) for key, value in journal.load().records.items() if key.startswith('broker:grant:')]
        for grant_id, value in grants:
            if value['state'] != 'retired':
                PeerBroker.recover(journal, grant_id)
    domain = root / 'holder/domain.json'
    if domain.exists():
        observed = json.loads(domain.read_text())
        if Path(observed['path']).exists():
            with ExecutionDomain.open(observed['path'], expected=DomainIdentity(**observed['identity'])) as original:
                original.retire()


async def main(args):
    """Observe parent death, global closure under a source writer lock, and honest local reconciliation."""
    from backend.runtime.authority_journal import WitnessedAuthorityJournal
    from backend.runtime.peer_broker import PeerBroker
    from backend.runtime.peer_process import _pidfd, start_ticks
    from backend.runtime.recovery import RunRecovery
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from evals.runtime.kernel_trial import wait_closed

    root = REPO / '.researcher/evaluations' / ('parent-loss-' + uuid4().hex[:8])
    root.mkdir(mode=0o700, parents=True)
    result = {'status': 'starting', 'model_turns_submitted': 0}
    print('Parent loss:', root, flush=True)
    log = (root / 'holder.stderr.log').open('w')
    process = await asyncio.create_subprocess_exec(
        sys.executable, str(Path(__file__).resolve()), '--holder', str(root),
        '--codex-binary', str(args.codex_binary), '--cgroup-parent', str(args.cgroup_parent),
        stdout=asyncio.subprocess.PIPE, stderr=log, start_new_session=True)
    pinned = None
    try:
        async with asyncio.timeout(20):
            assert await process.stdout.readline() == b'READY\n', 'Holder did not observe its detached child readiness'
        identity = json.loads((root / 'identity.json').read_text())
        pinned = _pidfd(identity['peer']['init_pid'])
        assert start_ticks(identity['peer']['init_pid']) == identity['peer']['start_ticks']
        process.kill()
        await process.wait()
        assert process.returncode == -signal.SIGKILL
        database = root / 'holder/source.db'
        with sqlite3.connect(database) as writer:
            writer.execute('BEGIN IMMEDIATE')
            try:
                with WitnessedAuthorityJournal(**identity['authority']) as journal:
                    recovered = PeerBroker.recover(journal, identity['grant_id'])
                assert recovered['state'] == 'retired' and recovered['domain_removed']
                assert not Path(identity['domain_path']).exists()
                await wait_closed(pinned)
                result['global_closed_with_source_writer_locked'] = True
            finally:
                writer.rollback()
        with WitnessedAuthorityJournal(**identity['authority']) as journal:
            projected = PeerBroker.project_recovered(journal, identity['grant_id'])
            assert projected and all(p['state'] == 'closed' for p in projected)
        store = SQLiteRunStore(database)
        store.recover_owners('replacement-evaluation-owner')
        run = store.get(101, identity['run_id'])
        recovery = RunRecovery(store)
        command = dict(project_id=101, run_id=run.run_id, attempt_id=run.attempt_id,
                       expected_fence=run.fence, operation_key='recover-original-holder')
        reconciled = recovery.reconcile(**command)
        assert recovery.reconcile(**command) == reconciled
        job = store.get_job(101, identity['job_id'])
        assert job.status == 'unknown' and job.exit_code is None and job.local_execution_closed
        assert reconciled['status'] == 'failed' and not reconciled['task_accepted'] and not reconciled['inference_started']
        (root / 'holder/sources/workspace/release-after-loss').touch()
        with store._transaction() as db:
            assert db.execute('SELECT COUNT(*) FROM runtime_jobs').fetchone()[0] == 1
            assert db.execute('SELECT COUNT(*) FROM runtime_inference_dispatches').fetchone()[0] == 0
        result.update(status='passed', holder_exit=process.returncode, original_namespace_closed=True,
                      original_domain_removed=True, detached_child_observed_ready=True,
                      job={'status': job.status, 'exit_code': job.exit_code, 'local_execution_closed': job.local_execution_closed},
                      recovery=reconciled, repeated_recovery_same_receipt=True, jobs_not_replayed=True)
    except BaseException as error:
        result.update(status='failed', error_type=type(error).__name__)
        raise
    finally:
        try:
            if process.returncode is None:
                process.kill()
                await process.wait()
            recover_owned(root)
        finally:
            if pinned is not None:
                os.close(pinned)
            log.close()
            (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'model_turns_submitted': 0}), flush=True)


if __name__ == '__main__':
    from evals.runtime.kernel_trial import arguments

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Run and kill only the original local trial holder; no model calls')
    parser.add_argument('--holder', type=Path)
    args = arguments(parser)
    if args.holder and not args.live:
        asyncio.run(holder(args.holder, args.codex_binary, args.cgroup_parent))
    elif args.live and not args.holder:
        asyncio.run(main(args))
    else:
        parser.error('Use --live for a new trial; --holder is the internal owned subprocess entry')
