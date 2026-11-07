"""Crash original live Codex/Ken services after durable effects, then recover without replay.

Two independent synthetic scenarios, at most two explicit admissions each. The
original Popen and pinned namespace identities determine what may be killed.
This is a service failure, not a machine reboot or proof of remote cancellation.
"""

import argparse
import asyncio
from contextlib import closing
import json
import os
from pathlib import Path
import select
import signal
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from evals.communication_flow.run import question_rows
from evals.context_alignment.run import observations, save, terminal
from evals.operation.host_smoke import stop
from evals.runtime.kernel_trial import wait_closed
from evals.runtime.native_trial import backend, prepare

PREFIX = ('Caso sintético. Usa ken_find con una consulta en inglés y ken_read para leer invoice.py. '
          'No edites código, crees informes, aceptes ni publiques. Respondé en español.\n')
CASES = {
    'effect': {
        'request': 'Listá los adjuntos de este proyecto y capturá policy.md una sola vez con researcher_capture_reference. Leé la fuente capturada y explicá la tasa del ejemplo.',
        'followup': 'Continuá el pedido original: la captura ya está guardada. Usá la fuente existente, sin volver a capturar, y explicá el ejemplo de la tasa.',
    },
    'question': {
        'request': 'Tengo 7,5 de duración y quiero expresarlo en segundos. La unidad original no está documentada. Ayudame a resolver la conversión y explicarla.',
        'followup': 'Usá mi respuesta registrada para completar el pedido original y explicá con un ejemplo sencillo cómo hiciste la conversión.',
    },
}
IMMUTABLE = ('tool_operations', 'research_sources', 'runtime_context_revisions',
             'runtime_input_snapshots', 'runtime_question_links')


def snapshot(database):
    """Read durable synthetic effects and authority separately from ephemeral HTTP replies."""
    with closing(sqlite3.connect(database)) as db:
        db.row_factory = sqlite3.Row
        result = {table: [dict(row) for row in db.execute(f'SELECT * FROM {table} ORDER BY rowid')]
                  for table in IMMUTABLE}
        result['runs'] = [dict(row) for row in db.execute('SELECT id,status,current_attempt_id,fence FROM runtime_runs ORDER BY rowid')]
        result['dispatches'] = [dict(row) for row in db.execute('SELECT attempt_id,status,observed_tokens FROM runtime_inference_dispatches ORDER BY rowid')]
        result['peers'] = [dict(row) for row in db.execute('SELECT * FROM runtime_peers ORDER BY rowid')]
        result['unrevoked_grants'] = db.execute('SELECT count(*) FROM tool_grants WHERE revoked_at IS NULL').fetchone()[0]
        result['task_status'] = db.execute('SELECT status FROM tasks WHERE id=1001').fetchone()[0]
        return result


def verify_recovery(before, after, receipt, *, question):
    """Reject loss, replay, false success, unsettled physical closure or invented usage settlement."""
    if any(before[key] != after[key] for key in IMMUTABLE):
        raise RuntimeError('Recovery changed a committed effect, context or input snapshot')
    if len(after['runs']) != 1 or len(after['dispatches']) != 1:
        raise RuntimeError('Recovery replayed an admission or dispatch')
    if [row['attempt_id'] for row in before['dispatches']] != [row['attempt_id'] for row in after['dispatches']]:
        raise RuntimeError('Recovery replaced the original dispatch')
    if after['dispatches'][0]['status'] != 'unknown':
        raise RuntimeError('Interrupted remote usage was not preserved as unknown')
    if after['unrevoked_grants'] or not after['peers'] or any(row['state'] != 'closed' for row in after['peers']):
        raise RuntimeError('Original local authority or peers remain open')
    if receipt['status'] != ('waiting_input' if question else 'failed'):
        raise RuntimeError('Recovery derived an incorrect durable outcome')
    if receipt['task_accepted'] or receipt['inference_started'] or after['task_status'] in ('accepted', 'done'):
        raise RuntimeError('Recovery accepted work or started inference')


def pin_native(state):
    """Pin and revalidate the actual live native namespace before killing its original service."""
    from backend.runtime.peer_process import NamespaceIdentity, _pidfd

    candidates = [row for row in state['peers'] if row['kind'] == 'native' and row['init_pid']]
    if len(candidates) != 1:
        raise RuntimeError('Exactly one bound original native namespace is required')
    identity = NamespaceIdentity.from_record(candidates[0])
    fd = _pidfd(identity.init_pid)
    try:
        if NamespaceIdentity.capture(identity.init_pid) != identity:
            raise RuntimeError('Original namespace identity changed')
        poller = select.poll()
        poller.register(fd, select.POLLIN | select.POLLHUP)
        if poller.poll(0):
            raise RuntimeError('Native namespace already exited before the crash')
        return fd
    except BaseException:
        os.close(fd)
        raise


def start_gated(root, output, port, ordinal, *, gate, handles):
    """Own the actual instrumented API Popen through readiness, fault injection and terminal observation."""
    import httpx

    log = (output / 'crashed-service.log').open('w')
    env = {key: value for key, value in os.environ.items()
           if not key.startswith('INFINIBAY_') and not any(word in key for word in ('API_KEY', 'TOKEN', 'SECRET'))
           and key not in ('PYTHONPATH', 'CODEX_HOME')}
    process = subprocess.Popen([sys.executable, '-I', str(Path(__file__).with_name('crash_worker.py')),
                                '--installation', str(root), '--port', str(port), '--gate', gate],
                               cwd=root / 'service', env=env, stdout=log, stderr=subprocess.STDOUT)
    handles.append(process)
    try:
        deadline = time.monotonic() + 30
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=1) as client:
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('Original evaluation service exited before readiness')
                try:
                    if client.get('/api/health/ready').json() == {'ready': True}:
                        return process, log
                except (httpx.TransportError, ValueError):
                    pass
                time.sleep(.1)
        raise TimeoutError('Original evaluation service did not become ready')
    except BaseException:
        stop(process, log)
        raise


def retire_trial_domains(trial):
    """Clean only this fresh installation's witnessed grants after all owned services terminate.

This final cleanup is reported separately and never used to pass public recovery.
"""
    from backend.runtime.authority_journal import WitnessedAuthorityJournal
    from backend.runtime.peer_broker import PeerBroker

    config = json.loads((trial.installation / 'runtime.json').read_text())
    retired = []
    with WitnessedAuthorityJournal(**config['authority']) as journal:
        for key, value in journal.load().records.items():
            if key.startswith('broker:grant:') and value['state'] != 'retired':
                result = PeerBroker.recover(journal, key.removeprefix('broker:grant:'))
                retired.append({'grant_id': key.removeprefix('broker:grant:'),
                                'state': result['state'], 'domain_removed': result.get('domain_removed')})
    return retired


def global_domain_state(trial):
    """Observe concession retirement separately from local peer rows and remote usage."""
    from backend.runtime.authority_journal import WitnessedAuthorityJournal

    config = json.loads((trial.installation / 'runtime.json').read_text())
    with WitnessedAuthorityJournal(**config['authority']) as journal:
        records = journal.load().records
        return {'active_concession': records.get('broker:active') is not None,
                'grants': [{field: value.get(field) for field in ('attempt_id', 'state', 'domain_removed')}
                           for key, value in records.items() if key.startswith('broker:grant:')]}


async def recover_and_continue(trial, evidence, before, run_id, version, pinned, admit):
    """Recover the original recorded crash; only the separately recorded continuation may generate again."""
    name = evidence['scenario']
    lifecycle = {}
    evidence['services'].append(lifecycle)
    async with backend(trial, lifecycle) as (_store, owner, _api, _db):
        response = await owner.get(f'/api/projects/101/runs/{run_id}/recovery')
        response.raise_for_status()
        inspection = response.json()
        evidence['recovery_inspection'] = inspection
        if not inspection['can_reconcile']:
            raise RuntimeError('Restart did not expose recoverable original work')
        command = {'operation_key': 'recover-original', 'attempt_id': inspection['attempt_id'],
                   'expected_fence': inspection['fence']}
        url = f'/api/projects/101/runs/{run_id}/recovery'
        response = await owner.post(url, json=command)
        response.raise_for_status()
        receipt = response.json()
        repeated = await owner.post(url, json=command)
        repeated.raise_for_status()
        if repeated.json() != receipt:
            raise RuntimeError('Repeated recovery changed its exact receipt')
        if pinned is not None:
                await wait_closed(pinned)
        after = snapshot(trial.database)
        evidence.update(recovery_receipt=receipt, after_recovery=after,
                        pinned_original_namespace_closed=True if pinned is not None else None, repeated_recovery_same_receipt=True)
        verify_recovery(before, after, receipt, question=name == 'question')
        global_state = global_domain_state(trial)
        evidence['global_after_recovery'] = global_state
        if global_state['active_concession'] or any(row['state'] != 'retired' or not row['domain_removed'] for row in global_state['grants']):
            raise RuntimeError('Public recovery left the original global concession active')
        if name == 'question':
            records = question_rows(trial.database)
            if len(records) != 1 or records[0]['status'] != 'pending':
                raise RuntimeError('The original question was not recovered as pending')
            questions = json.loads(records[0]['question_set_json'])
            response = await owner.post(f"/api/projects/101/tasks/1001/questions/{records[0]['request_id']}/answers", json={
                'operation_key': 'answer', 'expected_version': version,
                'answers': {item['id']: 'La duración original es 7,5 minutos; el destino es segundos.' for item in questions}})
            response.raise_for_status()
            version = response.json()['context_version']
            evidence['answer_receipt'] = response.json()
            if len(snapshot(trial.database)['dispatches']) != 1:
                raise RuntimeError('Answer unexpectedly dispatched a new turn')
        next_id = await admit(owner, CASES[name]['followup'], version, 'explicit-continuation')
        continued = await terminal(owner, next_id)
        evidence['continuation'] = continued
        observed = observations(trial)
        evidence['observations'] = observed
        if continued['status'] != 'needs_review':
            raise RuntimeError('Explicit continuation did not finish')
        if observed['unrevoked_grants'] or any(row['state'] != 'closed' for row in observed['peers']):
            raise RuntimeError('Continuation retained local authority')
        if len(observed['attempts']) != 2:
            raise RuntimeError('Unexpected inference count after explicit continuation')
        resumed = observed['attempts'][-1]['input']
        if resumed['request_history']['requests'][0]['content'] != PREFIX + CASES[name]['request']:
            raise RuntimeError('Explicit continuation lost the original request')
        final = snapshot(trial.database)
        if before['research_sources'] != final['research_sources'] or before['tool_operations'] != final['tool_operations']:
            raise RuntimeError('Explicit continuation repeated or changed the original effect')
        evidence['status'] = 'passed'


async def scenario(root, name, assets):
    """Crash after one real committed operation, reconcile through HTTP and explicitly continue once."""
    from functools import partial

    folder = root / name
    trial = prepare(folder, assets, live=True, turns=2, task_type='investigation', task_title='Service crash recovery')
    evidence = {'scenario': name, 'status': 'running', 'admissions_sent': 0,
                'services': [], 'scripted_owner': True, 'machine_reboot': False}
    save(folder / 'result.json', evidence)
    handles = []
    pinned = None
    started = time.monotonic()

    async def admit(owner, request, version, key):
        """Persist admission intent before one POST; never retry uncertain submission."""
        evidence['admissions_sent'] += 1
        save(folder / 'result.json', evidence)
        response = await owner.post('/api/projects/101/tasks/1001/runs', json={
            'operation_key': key, 'context_version': version, 'request': PREFIX + request})
        response.raise_for_status()
        return response.json()['run_id']

    try:
        lifecycle = {}
        evidence['services'].append(lifecycle)
        starter = partial(start_gated, gate=name, handles=handles)
        async with backend(trial, lifecycle, starter=starter) as (_store, owner, _api, _db):
            try:
                correction = await owner.post('/api/projects/101/tasks/1001/context-corrections', json={
                    'operation_key': 'initial-context', 'expected_version': 1,
                    'statement': 'Respondé en español con un ejemplo sencillo; no publiques.', 'source_kind': 'user_message'})
                correction.raise_for_status()
                version = correction.json()['context_version']
                run_id = await admit(owner, CASES[name]['request'], version, 'initial')
                async with asyncio.timeout(180):
                    while not (folder / 'gate-ready.json').exists():
                        if handles[0].poll() is not None:
                            raise RuntimeError('Service exited before its committed-effect gate')
                        await asyncio.sleep(.025)
                before = snapshot(trial.database)
                if len(before['dispatches']) != 1 or not before['tool_operations']:
                    raise RuntimeError('Gate has no actual dispatch and committed operation')
                if name == 'effect' and len(before['research_sources']) != 1:
                    raise RuntimeError('Expected exactly one captured source before the crash')
                if name == 'question' and len(before['runtime_question_links']) != 1:
                    raise RuntimeError('Expected exactly one durable question before the crash')
                calls = observations(trial)['tools']
                successful = {row['tool'] for row in calls if row['response'].get('success') is True}
                if not {'ken_find', 'ken_read'} <= successful:
                    raise RuntimeError('Actual successful Ken search and read are required before the crash')
                pinned = pin_native(before)
                evidence['before_crash'] = before
                evidence['gate'] = json.loads((folder / 'gate-ready.json').read_text())
                evidence['native_alive_at_crash'] = True
                save(folder / 'result.json', evidence)
                handles[0].kill()
                await asyncio.to_thread(handles[0].wait, 10)
                if handles[0].returncode != -signal.SIGKILL:
                    raise RuntimeError('Original service did not exit from the injected crash')
            finally:
                if handles[0].poll() is None:
                    handles[0].kill()
                    await asyncio.to_thread(handles[0].wait, 10)

        await recover_and_continue(trial, evidence, before, run_id, version, pinned, admit)
    except BaseException as error:
        evidence.update(status='failed', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        try:
            evidence['cleanup_only_retired_grants'] = retire_trial_domains(trial)
            if evidence['status'] == 'passed' and evidence['cleanup_only_retired_grants']:
                evidence.update(status='failed', error='Residual global grants required evaluation cleanup')
                raise RuntimeError(evidence['error'])
        finally:
            if pinned is not None:
                os.close(pinned)
            evidence['seconds'] = round(time.monotonic() - started, 3)
            save(folder / 'result.json', evidence)
            print(name, evidence['status'], flush=True)
    return evidence


async def main():
    """Register bounded cases before inference and retain every failed original trial."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', required=True)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--only', choices=tuple(CASES))
    args = parser.parse_args()
    root = args.output.absolute()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    resources = json.loads(args.assets.read_text())
    resources['limits'] = {**resources.get('limits', {}), 'max_observed_tokens': 120000}
    resources['project_turn_limit'] = 2
    resources['project_token_limit'] = min(resources.get('project_token_limit', 240000), 240000)
    assets = root / 'assets.json'
    fd = os.open(assets, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(resources, stream)
    selected = (args.only,) if args.only else tuple(CASES)
    save(root / 'registration.json', {'cases': {key: CASES[key] for key in selected},
        'maximum_turns': 2 * len(selected), 'scope': 'Actual service crash; synthetic data, scripted owner, no machine reboot'})
    results = [await scenario(root, name, assets) for name in selected]
    save(root / 'results.json', {'scenarios': results})


if __name__ == '__main__':
    asyncio.run(main())
