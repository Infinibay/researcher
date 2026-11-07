"""Exercise real question/answer and active-correction continuity with fresh installed Codex/Ken hosts.

Four turns maximum, synthetic data and scripted owner input. This functional
regression does not reuse a held-out label or claim human comprehension.
"""

import argparse
import asyncio
from contextlib import closing
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from evals.context_alignment.run import observations, save, start_policy, terminal
from evals.runtime.native_trial import backend, prepare

PREFIX = ('Caso sintético. Usa ken_find con una consulta en inglés y ken_read para leer evidence.py antes de responder. '
          'Responde en español; no edites, crees informes, aceptes ni publiques.\nUsuario: ')
SCENARIOS = {
    'question_answer': {
        'request': 'Tengo 7,5 de duración de una prueba y quiero expresarlo en segundos. La unidad original no está documentada. Ayudame a resolver la conversión y explicarla.',
        'answer': 'La duración original es 7,5 minutos. El destino solicitado es segundos, sin redondeo adicional.',
        'followup': 'Usá mi respuesta registrada para completar la conversión que pedí. Explicá con un ejemplo sencillo qué dato faltaba y cómo lo usaste.',
        'expected': '450 seconds; acknowledge the owner-supplied minutes rather than an assumed unit',
    },
    'active_correction': {
        'request': 'Calculá el recargo y el total para base500 y tasa0.07 después de leer evidence.py.',
        'correction': 'Corrección: usar base80 y tasa0.15. Explicar recargo y total por separado; no publicar.',
        'followup': 'Aplicá la corrección vigente. Leé evidence.py con Ken y explicá el recargo, el total y qué cambió respecto del pedido original.',
        'expected': 'Current charge12/gross92; prior requested charge35/gross535; prior values are historical, not current instructions',
    },
}
FIXTURE = '''"""Pure arithmetic accepts explicit units and separates a charge from its total; no observed input values."""
def seconds(value, unit):
    """Convert only a confirmed seconds/minutes/hours unit; never infer one from the number."""
    return value * {"seconds": 1, "minutes": 60, "hours": 3600}[unit]

def charge(base, fraction):
    """Return the proportional charge without including its base."""
    return base * fraction

def total(base, fraction):
    """Add the base once to its charge."""
    return base + charge(base, fraction)
'''


def question_rows(database):
    """Read actual persisted questions/answers without inventing a receipt from model prose."""
    with closing(sqlite3.connect(database)) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(
            'SELECT q.request_id,q.question_set_json,q.context_version,u.status,u.response '
            'FROM runtime_question_links q JOIN user_requests u ON u.id=q.request_id ORDER BY q.request_id')]


def verify_observations(observed, case, policy_hash):
    """Check this scenario's actual source and frozen inputs, independently of inference or response wording."""
    if observed['unrevoked_grants'] or any(p['state'] != 'closed' for p in observed['peers']):
        raise RuntimeError('Original peers or grants remain open')
    successful = [row for row in observed['tools'] if row['response'].get('success') is True]
    if not {'ken_find', 'ken_read'} <= {row['tool'] for row in successful}:
        raise RuntimeError('Required successful actual Ken calls absent')
    reads = '\n'.join(item.get('text', '') for row in successful
                      if row['tool'] == 'ken_read' and row['arguments'].get('path') == 'evidence.py'
                      for item in row['response'].get('contentItems', []))
    if not all(line in reads for line in FIXTURE.splitlines() if line.strip()):
        raise RuntimeError('Ken did not return the complete registered communication source')
    if len(observed['attempts']) != 2:
        raise RuntimeError('Unexpected inference count')
    for attempt in observed['attempts']:
        if attempt['instructions_sha256'] != policy_hash:
            raise RuntimeError('Delivered policy differs from the frozen current catalog')
    resumed = observed['attempts'][-1]['input']
    requests = resumed['request_history']['requests']
    if len(requests) != 1 or requests[0]['content'] != PREFIX + case['request']:
        raise RuntimeError('Original request was not delivered exactly to the next admission')
    if requests[0]['current_authorization'] is not False or requests[0]['source_context_version'] != 1:
        raise RuntimeError('Historical request acquired current authority or lost provenance')
    if resumed['context_version'] != 2:
        raise RuntimeError('Continuation did not receive the new context')


async def scenario(root, name, case, assets, policy, policy_hash):
    """Submit each intent once and retain original process, admission, snapshot and physical-closure evidence."""
    folder = root / name
    resources = json.loads(assets.read_text())
    resources['limits'] = {**resources.get('limits', {}), 'max_observed_tokens': 120000}
    resources['project_turn_limit'] = 2
    resources['project_token_limit'] = min(resources.get('project_token_limit', 240000), 240000)
    private_assets = root / (name + '-assets.json')
    fd = os.open(private_assets, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(resources, stream)
    trial = prepare(folder, private_assets, live=True, turns=2, task_type='investigation', task_title='Communication continuity')
    (trial.workspace / 'evidence.py').write_text(FIXTURE)
    evidence = {'scenario': name, 'status': 'running', 'runs': [], 'admissions_sent': 0,
                'scripted_owner_input': True, 'human_comprehension': None}
    started = time.monotonic()
    starter = partial(start_policy, policy=policy, expected_hash=policy_hash, gate='correction' in case)
    try:
        async with backend(trial, evidence, starter=starter) as (_store, owner, _api, _database):
            async def admit(request, version, key):
                """Persist intent before POST and never retry an uncertain admission automatically."""
                evidence['admissions_sent'] += 1
                save(folder / 'result.json', evidence)
                response = await owner.post('/api/projects/101/tasks/1001/runs', json={
                    'operation_key': key, 'context_version': version, 'request': PREFIX + request})
                evidence.setdefault('admission_receipts', []).append({'status': response.status_code, 'body': response.json()})
                save(folder / 'result.json', evidence)
                response.raise_for_status()
                return response.json()['run_id']

            first = await admit(case['request'], 1, 'initial')
            if 'correction' in case:
                async with asyncio.timeout(180):
                    while not (folder / 'correction-ready').exists():
                        await asyncio.sleep(.05)
                current = await owner.get('/api/projects/101/runs/' + first)
                current.raise_for_status()
                if current.json()['status'] != 'running':
                    raise RuntimeError('Original run was not active at correction')
                try:
                    response = await owner.post('/api/projects/101/tasks/1001/context-corrections', json={
                        'operation_key': 'correct', 'expected_version': 1,
                        'statement': case['correction'], 'source_kind': 'user_message'})
                    response.raise_for_status()
                    version = response.json()['context_version']
                finally:
                    (folder / 'correction-release').write_text('Release the original response after correction submission.\n')
                prior = await terminal(owner, first)
                evidence['runs'].append(prior)
                if prior['status'] != 'superseded':
                    raise RuntimeError('Corrected original run retained authority')
            else:
                prior = await terminal(owner, first)
                evidence['runs'].append(prior)
                if prior['status'] != 'waiting_input':
                    raise RuntimeError('Material question was not persisted and physically parked')
                records = question_rows(trial.database)
                if len(records) != 1 or records[0]['status'] != 'pending':
                    raise RuntimeError('Expected one actual grouped question request')
                before_answer = observations(trial)
                if before_answer['unrevoked_grants'] or any(p['state'] != 'closed' for p in before_answer['peers']):
                    raise RuntimeError('Question became answerable before original peers closed')
                evidence['before_answer'] = before_answer
                questions = json.loads(records[0]['question_set_json'])
                answers = {item['id']: case['answer'] for item in questions}
                response = await owner.post(f"/api/projects/101/tasks/1001/questions/{records[0]['request_id']}/answers", json={
                    'operation_key': 'answer', 'expected_version': 1, 'answers': answers})
                response.raise_for_status()
                version = response.json()['context_version']
                with closing(sqlite3.connect(trial.database)) as db:
                    if db.execute('SELECT count(*) FROM runtime_runs').fetchone()[0] != 1:
                        raise RuntimeError('Answer unexpectedly started another run')
                evidence['answer_receipt'] = response.json()
                evidence['questions'] = question_rows(trial.database)
            second = await admit(case['followup'], version, 'continue')
            evidence['runs'].append(await terminal(owner, second))
            if evidence['runs'][-1]['status'] != 'needs_review':
                raise RuntimeError('Continuation did not finish its explanation')
            observed = observations(trial)
            evidence.update(observed)
            evidence['question_records'] = question_rows(trial.database)
            verify_observations(observed, case, policy_hash)
            evidence['status'] = 'observed'
    except BaseException as exc:
        evidence.update(status='failed', error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        evidence['seconds'] = round(time.monotonic() - started, 3)
        save(folder / 'result.json', evidence)
        print(name, evidence['status'], flush=True)
    return evidence


async def main():
    """Freeze new functional cases and current policy before at most four authorized real turns."""
    from backend.prompts.native import build_instructions

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', required=True, action='store_true')
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--only', choices=list(SCENARIOS), help='Run only an explicitly selected scenario in a new directory')
    args = parser.parse_args()
    root = args.output.absolute()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    policy = root / 'policy.txt'
    policy.write_text(build_instructions('research', 'investigation'))
    policy_hash = hashlib.sha256(policy.read_bytes()).hexdigest()
    selected = {args.only: SCENARIOS[args.only]} if args.only else SCENARIOS
    save(root / 'registration.json', {'cases': selected, 'fixture': FIXTURE,
        'policy_sha256': policy_hash, 'maximum_turns': 2 * len(selected),
        'scope': 'Functional regression with scripted owner; no held-out, population or human-comprehension claim'})
    result = []
    for name, case in selected.items():
        result.append(await scenario(root, name, case, args.assets, policy, policy_hash))
    save(root / 'results.json', {'scenarios': result, 'human_review': 'pending'})


if __name__ == '__main__':
    asyncio.run(main())
