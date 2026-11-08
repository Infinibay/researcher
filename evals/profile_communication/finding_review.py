"""Compare real finding reviewers over identical controlled author claims and saved evidence.

Synthetic author IDs and record times are fixed before review, without a model
call or copied authority. Only the two actual reviewers consume subscription turns.
"""

import argparse
import asyncio
import json
import os
import sqlite3
import subprocess
import time
from functools import partial
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from backend.prompts.native import build_instructions
from backend.runtime.codex_session import ExecutionLimits
from evals.context_alignment.protocol import digest, load_registered
from evals.context_alignment.run import compare_pair, export_review, observations, save, start_policy, terminal, verify_ken
from evals.runtime.native_trial import backend, prepare

ROOT = Path(__file__).resolve().parents[2]
FIXED_TIME = 1767225600.0
SOURCE = '''"""Calculate a synthetic self-reported proportion; no causal comparison is encoded."""
PARTICIPANTS = 40
REPORTED_IMPROVEMENT = 28

def reported_improvement_fraction():
    """Return the observed fraction without attributing improvement to the program."""
    return REPORTED_IMPROVEMENT / PARTICIPANTS
'''
REFERENCE = 'Synthetic program summary: 28 of 40 participants reported improvement after participating. There was no concurrent comparison group in this recorded dataset. Other changes, baseline condition and selection mechanisms are not recorded. No individual records, uncertainty interval or randomized assignment are supplied. These are synthetic records, not observations of real people.\n'
CLAIM = 'El programa causó la mejoría: demuestra que el 70% de las personas mejora por el programa.'
CASE = {'id': 'finding_causal_claim', 'split': 'development',
        'request': 'Revisá el hallazgo guardado sobre el programa y las fuentes que cita. Necesito decidir qué conclusión se puede conservar. Explicá en español qué entra a la revisión, qué decisión registrás y qué no demuestran los datos. No tengo claro qué significa atribuir una causa: usá un ejemplo sencillo si ayuda. Sólo pido la revisión, sin aceptar la tarea ni publicar el informe.',
        'criteria': [
            'Read the full bound finding/report and saved source; quote actual retained evidence and inspect the complete registered arithmetic code with Ken.',
            '28/40 equals70percent observed self-reports, not a causal effect or population generalization; missing methods do not prove omitted methods.',
            'Record one typed needs_revision or inconclusive decision with explained checks and limits, without accepting the task or publishing.',
            'Explain in Spanish the claim/evidence-to-decision relationship and a faithful concrete causal limit; no fabricated human understanding or new experiment.',
        ]}
PREFIX = ('Ensayo sintético de revisión independiente. El autor fue controlado sin modelo; '
          'sus IDs y fechas son fixtures declarados. Lee researcher_review_subject completo '
          'y sus fuentes guardadas. Usa Ken con consulta en inglés y ken_read include=["source"] '
          'para leer evidence.py completo. No edites, aceptes ni publiques.\nUsuario: ')


def register(root, assets):
    """Freeze the complete controlled material, rubric, policies and evaluator before either real reviewer starts."""
    operator = json.loads(assets.read_text())
    ceilings = {'wall_seconds': 180, 'no_progress_seconds': 90, 'max_turns': 1,
                'max_tool_calls': 20, 'max_observed_tokens': 350000, 'max_answer_bytes': 20000}
    limits = {key: min(operator.get('limits', {}).get(key, cap), cap) for key, cap in ceilings.items()}
    limits['max_observed_tokens'] = min(limits['max_observed_tokens'], operator.get('project_token_limit', 350000))
    baseline = json.loads((ROOT / 'evals/prompts/baseline.json').read_text())
    files = {'baseline.txt': baseline['instructions']['finding_review'],
             'candidate.txt': build_instructions('finding_review', 'research', limits=ExecutionLimits(**limits)),
             'evidence.py': SOURCE, 'reference.md': REFERENCE,
             'case.json': json.dumps(CASE, ensure_ascii=False, indent=2) + '\n',
             'controlled-author.json': json.dumps({'claim': CLAIM, 'fixture_time': FIXED_TIME, 'model_turns': 0}, ensure_ascii=False, indent=2) + '\n'}
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, content in files.items():
        (root / name).write_text(content)
    protocol = {'format': 1, 'execution_kind': 'finding_review', 'profile': 'finding_review', 'task_type': 'research',
                'case': CASE, 'request_prefix': PREFIX, 'maximum_model_turns': 2, 'controlled_author_model_turns': 0,
                'files': {name: digest(content.encode()) for name, content in files.items()}, 'limits': limits,
                'order': ['candidate', 'baseline'], 'baseline_commit': baseline['source_commit'],
                'source_commit': subprocess.check_output(['/usr/bin/git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'operator_resources_sha256': digest(assets.read_bytes()),
                'harness': {name: digest((ROOT / name).read_bytes()) for name in (
                    'evals/profile_communication/finding_review.py', 'evals/context_alignment/run.py',
                    'evals/context_alignment/worker.py', 'evals/context_alignment/protocol.py', 'evals/runtime/native_trial.py')},
                'allowed_input_variation': ['scope.run_id', 'scope.attempt_id', 'review.run_id only when aliasing scope.run_id', 'current request_history.cutoff_run_id alias'],
                'allowed_model_receipt_variation': ['run_id', 'attempt_id', 'selected_at'],
                'human_comprehension': None, 'human_effort_seconds': None,
                'scope': 'One purposive exploratory pair; controlled author0model turns, identical full subject and source bytes. No causal prompt superiority, scientific calibration or human acceptance. Fixture creation time is synthetic, not actual capture time.'}
    save(root / 'registration.json', protocol)
    (root / 'registration.sha256').write_text(digest((root / 'registration.json').read_bytes()) + '\n')
    return protocol


def seed_author(database):
    """Use real writer transactions with declared fixed synthetic IDs/times; revoke the author without reserving inference."""
    from backend.knowledge.reviews import finding_subject
    from backend.research.models import EvidenceReference, FindingDraft, ReportDraft, SourceDraft
    from backend.research.sqlite_store import SQLiteResearchStore
    from backend.runtime import sqlite_runs
    from backend.runtime.contracts import RunSpec

    with sqlite3.connect(database) as db:
        if db.execute('SELECT COUNT(*) FROM runtime_runs').fetchone()[0] or db.execute('SELECT COUNT(*) FROM findings').fetchone()[0]:
            raise ValueError('Controlled author requires fresh synthetic storage')
    runs = sqlite_runs.SQLiteRunStore(database, clock=lambda: FIXED_TIME)
    with patch.object(sqlite_runs, 'uuid4', side_effect=[UUID(int=1), UUID(int=2)]):
        original = runs.admit(RunSpec(101, 1001, 'controlled-author', 1, 'controlled-author',
                                     'Synthetic controlled author fixture; no model generation. Review the causal claim against its recorded source.', 'codex'))
        lease = runs.claim(101, original.run_id, 'controlled-author-fixture')
    runs.bind_native(lease, thread_id='controlled-author-no-model-thread', turn_id='controlled-author-no-model-turn')
    writer = SQLiteResearchStore(database, clock=lambda: FIXED_TIME)
    token = writer.issue_grant(project_id=101, task_id=1001, agent_id='controlled-author',
                               permissions={'sources.capture', 'sources.read', 'findings.write', 'reports.write'})
    scope = writer.authorize(token)
    runs.bind_grant(lease, scope.grant_id)
    scope = writer.authorize(token)
    source = writer.capture_source(scope, 'controlled-source', SourceDraft('attachment', 'synthetic:program-summary', 'Synthetic program summary', REFERENCE), intent={})
    finding = writer.record_finding(scope, 'controlled-finding', FindingDraft(topic='Program causal claim', content=CLAIM,
                                    evidence=(EvidenceReference(source['source_id'], '28 of 40 participants reported improvement'),)))
    # Record a declared fixture timestamp before any review snapshot; no real history is rewritten.
    with sqlite3.connect(database) as db, db:
        db.execute("UPDATE findings SET created_at='2026-01-01 00:00:00' WHERE id=?", (finding['finding_id'],))
    writer.write_report(scope, 'controlled-report', ReportDraft(title='Synthetic program draft', content=CLAIM, finding_ids=(finding['finding_id'],)))
    runs.finish(lease, native_status='completed', summary='Controlled author fixture with a deliberate causal overclaim; no model ran.')
    with sqlite3.connect(database) as db:
        db.row_factory = sqlite3.Row
        subject = finding_subject(db, 101, finding['finding_id'])
    return {'finding_id': finding['finding_id'], 'source_id': source['source_id'], 'claim': CLAIM,
            'author_run_id': original.run_id, 'author_attempt_id': lease.attempt_id,
            'controlled_author_model_turns': 0, 'subject': subject}


async def run_review_arm(root, protocol, arm, assets):
    """Admit one actual independent reviewer to its original frozen subject, preserving closure and first failures."""
    folder = root / (CASE['id'] + '-' + arm)
    if folder.exists():
        raise FileExistsError('Arm already started; inspect its original receipts')
    resources = json.loads(assets.read_text())
    resources['limits'] = {key: min(resources.get('limits', {}).get(key, cap), cap) for key, cap in protocol['limits'].items()}
    resources['project_turn_limit'] = min(resources.get('project_turn_limit', 1), 1)
    resources['project_token_limit'] = min(resources.get('project_token_limit', 350000), protocol['limits']['max_observed_tokens'])
    private = root / (arm + '-assets.json')
    with os.fdopen(os.open(private, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(resources, stream)
    trial = prepare(folder, private, live=True, turns=1, task_type='research', task_title='Review a synthetic program claim')
    for name in ('invoice.py', 'test_invoice.py'):
        (trial.workspace / name).unlink()
    (trial.workspace / 'evidence.py').write_bytes((root / 'evidence.py').read_bytes())
    author = seed_author(trial.database)
    evidence = {'case_id': CASE['id'], 'arm': arm, 'status': 'running', 'controlled_author': author,
                'runs': [], 'admissions_sent': 0, 'model_turn_budget': 1}
    save(folder / 'result.json', evidence)
    starter = partial(start_policy, policy=root / (arm + '.txt'), expected_hash=protocol['files'][arm + '.txt'],
                      gate=False, task_type='research', execution_kind='finding_review')
    started = time.monotonic()
    try:
        async with backend(trial, evidence, starter=starter) as (_store, owner, _api, _database):
            evidence['admissions_sent'] = 1
            save(folder / 'result.json', evidence)
            response = await owner.post('/api/projects/101/tasks/1001/finding-reviews', json={
                'operation_key': 'registered-review', 'context_version': 1, 'finding_id': author['finding_id'],
                'subject_sha256': author['subject']['subject_sha256'], 'repository_id': 11,
                'request': protocol['request_prefix'] + protocol['case']['request']})
            evidence['admission_receipt'] = {'status': response.status_code, 'body': response.json()}
            save(folder / 'result.json', evidence)
            response.raise_for_status()
            run_id = response.json()['run_id']
            evidence['runs'].append(await terminal(owner, run_id))
            evidence.update(observations(trial))
            state = await owner.get('/api/projects/101/findings/' + str(author['finding_id']) + '/review-state')
            state.raise_for_status()
            evidence['review_state'] = state.json()
            if evidence['runs'][-1]['status'] != 'needs_review' or evidence['unrevoked_grants'] or any(p['state'] != 'closed' for p in evidence['peers']):
                raise RuntimeError('Original review incomplete or its peers/grants remain open')
            verify_ken(evidence['tools'], required_source=(root / 'evidence.py').read_text())
            with sqlite3.connect(trial.database) as db:
                db.row_factory = sqlite3.Row
                from backend.knowledge.reviews import finding_subject
                evidence['subject_after'] = finding_subject(db, 101, author['finding_id'])
                evidence['decisions'] = [json.loads(row[0]) for row in db.execute('SELECT decision_json FROM finding_review_decisions')]
            if evidence['subject_after'] != author['subject']:
                raise RuntimeError('Reviewer changed original evidence or author subject')
            evidence['status'] = 'observed'
    except BaseException as error:
        evidence.update(status='failed', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        evidence['seconds'] = round(time.monotonic() - started, 3)
        save(folder / 'result.json', evidence)
        print(arm, evidence['status'], flush=True)
    return evidence


async def run(root, assets):
    """Execute only the two original registered reviewer arms serially; refuse replay or changed controls."""
    protocol = load_registered(root)
    if any((root / (CASE['id'] + '-' + arm)).exists() for arm in protocol['order']):
        raise FileExistsError('Comparison already started; inspect original receipts')
    pair = {}
    assets_hash = digest(assets.read_bytes())
    if assets_hash != protocol['operator_resources_sha256']:
        raise ValueError('Operator resources changed after registration; prepare a new unstarted study')
    for arm in protocol['order']:
        protocol = load_registered(root)
        if digest(assets.read_bytes()) != assets_hash or any(digest((ROOT / name).read_bytes()) != value for name, value in protocol['harness'].items()):
            raise ValueError('Registered evaluator or host resources changed')
        pair[arm] = await run_review_arm(root, protocol, arm, assets)
        if len(pair[arm]['attempts']) != 1 or pair[arm]['attempts'][0]['instructions_sha256'] != protocol['files'][arm + '.txt']:
            raise ValueError('Review policy or actual turn count differs from registration')
    if pair['baseline']['controlled_author']['subject'] != pair['candidate']['controlled_author']['subject']:
        raise ValueError('Original complete review subjects differ')
    comparison = compare_pair(pair['baseline'], pair['candidate'])
    save(root / 'comparison.json', comparison)
    export_review(root, protocol['case'], pair)
    return comparison


def main():
    """Separate account-free preregistration from explicit bounded real reviewer execution."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    if args.prepare == args.live:
        parser.error('Choose exactly --prepare or --live')
    if args.prepare:
        register(args.output.absolute(), args.assets)
    else:
        asyncio.run(run(args.output.absolute(), args.assets))


if __name__ == '__main__':
    main()
