"""Review a retained synthetic finding on installed HTTP without launching a generative model.

Only the untouched synthetic evaluation produced by evidence_pages.py is accepted.
The reviewer decision is a domain fixture, explicitly not model-generated. The
browser recovers an existing exact owner admission and closes that original run.
"""

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from uuid import uuid4

from evidence_pages import observe
from host_smoke import start, stop

ROOT = Path(__file__).resolve().parents[2]


def prepare_review(host, ids):
    """Admit and close a distinct synthetic reviewer over the actual saved subject and citation."""
    from backend.api.routes.runs import StartFindingReview
    from backend.research.models import REVIEW_PERMISSIONS, EvidenceReference, ReviewCheck, ReviewDecision, ReviewTarget
    from backend.research.sqlite_store import SQLiteResearchStore
    from backend.runtime.contracts import RunSpec
    from backend.runtime.peer_registry import AttemptPeers
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.runtime.workspaces import WorkspaceRegistry

    project, original = ids['alpha'], ids['draft']
    runs = SQLiteRunStore(host / 'source.db')
    research = SQLiteResearchStore(host / 'source.db')
    state = runs.finding_review_state(project, original['finding'])
    if not state['reviewable'] or state['active_review'] or state['reviews']['items']:
        raise ValueError('The original synthetic finding must be reviewable with no prior reviewer')
    key = 'review-' + str(uuid4())
    spec = RunSpec(project, original['task'], 'research-reviewer', state['context_version'], key, StartFindingReview.model_fields['request'].default, 'codex')
    target = ReviewTarget(original['finding'], state['subject_sha256'])
    binding = WorkspaceRegistry(host / 'source.db', host / 'sources').bind(project, 11)
    run = runs.admit(spec, binding=binding, review=target)
    lease, peers = AttemptPeers.claim(runs, project, run.run_id, 'synthetic-reviewer-never-launched-owner')
    try:
        runs.bind_native(lease, thread_id='synthetic-reviewer-never-launched-thread', turn_id='synthetic-reviewer-never-launched-turn')
        token = research.issue_grant(project_id=project, task_id=original['task'], agent_id=spec.actor_id, permissions=set(REVIEW_PERMISSIONS))
        scope = research.authorize(token)
        runs.bind_grant(lease, scope.grant_id)
        research.record_review(scope, 'synthetic-documentary-decision', ReviewDecision(
            'supported', 'Ejemplo sintético: la cita guardada contiene el total declarado. No es una evaluación generada por un modelo.',
            (ReviewCheck('documentary_quote', 'supported', 'La frase citada aparece literalmente en la captura guardada del fixture.'),),
            (EvidenceReference(original['source'], original['quote']),),
            ('No se recontaron las piezas ni se comprobó actualidad del inventario.', 'Decisión sintética para probar la interfaz; no fue generada por un revisor.'),
        ))
        for peer in peers.ids.values():
            peers.registry.close(peer)
        runs.finish(lease, native_status='completed', summary='Synthetic review fixture; no native peer or model was launched.')
    except BaseException:
        for peer in peers.ids.values():
            peers.registry.close(peer)
        runs.cancel(project, run.run_id)
        runs.retire_inference(lease, outcome='cancelled')
        raise
    return {'projectId': project, 'taskId': original['task'], 'findingId': original['finding'], 'operation_key': key, 'context_version': state['context_version'], 'subject_sha256': state['subject_sha256'], 'repository_id': 11}, run.run_id


def main():
    """Guard the retained fixture, own service/browser handles and prove replay creates no new native work."""
    import backend

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluation', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--node', type=Path, required=True)
    parser.add_argument('--prepared-review', type=Path, help='Resume the same closed synthetic reviewer after an evaluator failure that changed no observed domain state')
    args = parser.parse_args()
    if not Path(backend.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError('Use the separately installed product Python')
    original = args.evaluation.resolve(strict=True)
    evidence = json.loads((original / 'result.json').read_text())
    ids = json.loads((original / 'fixture.json').read_text())
    host = original / 'host'
    if (evidence['status'] != 'passed' or evidence.get('synthetic_domain_history') is not True
            or evidence.get('actual_model_turns') != 0 or evidence['before'] != evidence['after']
            or evidence['after']['dispatches'] != 0
            or {row['id'] for row in evidence['after']['runs']} != {ids['draft']['run'], ids['accepted']['run']}):
        raise ValueError('Only the untouched successful synthetic evidence installation may be extended')
    output = args.output.resolve()
    output.mkdir(mode=0o700)
    if args.prepared_review is None:
        if observe(host) != evidence['after']:
            raise ValueError('The original fixture changed; do not create another reviewer')
        intent, run_id = prepare_review(host, ids)
    else:
        prior = args.prepared_review.resolve(strict=True)
        previous = json.loads((prior / 'result.json').read_text())
        packet = json.loads((prior / 'fixture.json').read_text())
        if (previous.get('status') != 'failed' or previous.get('synthetic_review_decision') is not True
                or previous['before'] != previous['after'] or observe(host) != previous['before']
                or packet['original'] != ids or previous['existing_owner_admission_replayed'] != packet['run']):
            raise ValueError('Resume only the exact unchanged original reviewer; never recreate uncertain work')
        intent, run_id = packet['intent'], packet['run']
    from backend.runtime.sqlite_runs import SQLiteRunStore
    author = SQLiteRunStore(host / 'source.db').finding_review_state(ids['alpha'], ids['draft']['finding'])['author']
    fixture = output / 'fixture.json'
    fixture.write_text(json.dumps({'original': ids, 'intent': intent, 'run': run_id, 'authorAttempt': author['attempt_id']}, indent=2) + '\n')
    before = observe(host)
    result = {'status': 'running', 'synthetic_review_decision': True, 'actual_generative_turns': 0, 'existing_owner_admission_replayed': run_id, 'before': before}
    with socket.socket() as binding:
        binding.bind(('127.0.0.1', 0))
        port = binding.getsockname()[1]
    process = log = None
    try:
        process, log = start(host, output, port, 3)
        keys = list((host / 'auth').glob('owner-*.key'))
        if len(keys) != 1:
            raise ValueError('Expected one private fixture pairing file')
        env = {**os.environ, 'RESEARCHER_E2E_ORIGIN': f'http://127.0.0.1:{port}', 'RESEARCHER_E2E_OWNER_FILE': str(keys[0]), 'RESEARCHER_E2E_OUTPUT': str(output / 'browser'), 'RESEARCHER_E2E_FIXTURE': str(fixture)}
        with (output / 'browser.log').open('x') as browser_log:
            browser = subprocess.run([str(args.node.resolve(strict=True)), 'tests/finding-review.e2e.mjs'], cwd=ROOT / 'frontend', env=env, stdout=browser_log, stderr=subprocess.STDOUT, check=False)
        result['browser_exit'] = browser.returncode
        assert browser.returncode == 0, 'Inspect the original browser log'
        after = observe(host)
        expected = json.loads(json.dumps(before))
        for run in expected['runs']:
            if run['id'] == run_id:
                run['status'] = 'cancelled'
        assert after == expected, 'Only the original reviewer run may change status; bytes, findings, tasks, peers and run IDs must remain'
        assert after['dispatches'] == 0 and after['native_starts'] == before['native_starts'] == 3
        result['status'] = 'passed'
    except BaseException as error:
        result.update(status='failed', error_type=type(error).__name__)
        raise
    finally:
        if process is not None:
            result['service_exit'] = stop(process, log)
        result['after'] = observe(host)
        (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({'status': result['status'], 'receipt': str(output / 'result.json')}), flush=True)


if __name__ == '__main__':
    main()
