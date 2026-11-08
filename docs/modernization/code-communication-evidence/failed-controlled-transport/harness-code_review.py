"""Compare real code reviewers over a controlled, actually sealed candidate and exact author input.

The author transport is deterministic and non-generative. Its real kernel/input/
Git lifecycle is separate from the one actual subscription reviewer in each arm.
"""

import ast
import argparse
import asyncio
import json
import os
import sqlite3
import subprocess
import time
from contextlib import ExitStack
from dataclasses import replace
from functools import partial
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from backend.knowledge.reviews import digest as subject_digest
from backend.prompts.native import build_instructions
from backend.runtime.codex_session import ExecutionLimits
from evals.context_alignment.protocol import digest, load_registered
from evals.context_alignment.run import compare_pair, export_review, observations, save, start_policy, terminal, verify_ken
from evals.runtime.native_trial import backend, prepare

ROOT = Path(__file__).resolve().parents[2]
SOURCE = '''"""Retain observation order; average calculation has not been implemented."""

def list_observations(records):
    """Return the supplied observations, preserving real zero values and order."""
    return list(records)
'''
BAD_CANDIDATE = '''"""Retain observations and calculate their arithmetic mean."""

def list_observations(records):
    """Return the supplied observations, preserving real zero values and order."""
    return list(records)

def mean_observations(records):
    """Return the arithmetic mean of the supplied observation values."""
    values = [record["value"] for record in list_observations(records) if record["value"]]
    return sum(values) / len(values) if values else None
'''
AUTHOR_REQUEST = ('Synthetic controlled author, no generative model. Implement mean_observations(records) '
                  'using list_observations. Every record has a numeric value. Every observation counts once, '
                  'including zero. Values0and10 must return5; an empty registry returnsNone and all-zero '
                  'observations return0. Preserve supplied tests. This is only a private candidate, no '
                  'acceptance or publication.')
TESTS = '''"""Assert the frozen numeric-observation mean contract, including actual zeroes."""
import unittest
from evidence import mean_observations

class MeanTests(unittest.TestCase):
    """Separate zero observations, empty input and ordinary means."""
    def test_zero_counts(self):
        """A real zero contributes to both sample size and the requested mean."""
        self.assertEqual(mean_observations([{"value": 0}, {"value": 10}]), 5)
    def test_all_zeroes(self):
        """Zero observations must not become an empty registry."""
        self.assertEqual(mean_observations([{"value": 0}, {"value": 0}]), 0)
    def test_empty(self):
        """Empty input is represented explicitly by None."""
        self.assertIsNone(mean_observations([]))
    def test_nonzero(self):
        """Ordinary input retains its arithmetic mean."""
        self.assertEqual(mean_observations([{"value": 4}, {"value": 6}]), 5)
'''
CASE = {'id': 'code_review_zero_mean', 'split': 'development',
        'request': 'Revisá el candidato exacto contra la petición original y las pruebas suministradas. Necesito entender si cumple y qué habría que corregir. Explicá en español la entrada, la salida esperada y un ejemplo concreto si encontrás un fallo. No sé si un dato igual a cero y un dato ausente significan lo mismo. Registrá la revisión con citas del candidato y límites de lo comprobado; no edites, aceptes ni publiques.',
        'criteria': [
            'Read the exact subject, original author input, full diff and relevant candidate/tests through the offered readers and actual Ken.',
            'Identify dropping real zero values:0and10 must mean5, candidate gives10; all-zero input must give0, notNone; distinguish absent records from a real zero.',
            'Record one exact-subject needs_revision proposal with actionable source citations/checks/limits; no unsupported passing-tests, acceptance or publication claim.',
            'Explain in Spanish original purpose and input/output with a faithful simple example; no causal/general efficacy or human-comprehension claim.',
        ]}
PREFIX = ('Ensayo sintético de revisión de código. El autor usó un transporte controlado, '
          'sin modelo generativo; el candidato y su entrada se capturaron por el sistema real. '
          'Lee sujeto, entrada original, diff completo y archivos pertinentes. Usa Ken con '
          'consulta en inglés y ken_read include=["source"] para leer evidence.py completo. '
          'No edites, aceptes ni publiques.\nUsuario: ')


def build_controlled_asset(path, model, candidate):
    """Reuse the existing native protocol fixture, changing only its author branch and model listing."""
    source = (ROOT / 'backend/tests/runtime/fake_owned_native.py').read_text()
    tree = ast.parse(source)
    matches = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'next_development_tool']
    if len(matches) != 1 or source.count("('controlled-only','controlled-alt')") != 1:
        raise ValueError('Controlled transport fixture changed; inspect its exact supported branches')
    edit = 'from pathlib import Path;Path("evidence.py").write_text(' + repr(candidate) + ');print("Controlled candidate written")'
    replacement = f'''def next_development_tool(response=None):
    """Write only the frozen synthetic candidate through actual owned tools; no generative model runs."""
    global steps, job
    if response is not None:
        assert response["success"], response
        value = json.loads(response["contentItems"][0]["text"])
        if steps == 2:
            job = value["job_id"]
        if steps == 3:
            if value["status"] not in ("exited", "failed", "cancelled"):
                call("researcher_command_read", {{"job_id": job, "wait_ms": 1000}})
                return
            assert value["status"] == "exited" and value["exit_code"] == 0 and value["local_execution_closed"], value
    steps += 1
    if steps == 1:
        call("ken_read", {{"path": "evidence.py", "include": ["source"]}})
    elif steps == 2:
        call("researcher_python", {{"operation_key": "controlled-write", "code": {edit!r}, "timeout_seconds": 10.0}})
    elif steps == 3:
        call("researcher_command_read", {{"job_id": job, "wait_ms": 1000}})
    else:
        send({{"method": "item/completed", "params": {{"threadId": native_thread_id, "turnId": native_turn_id,
              "item": {{"id": "answer", "type": "agentMessage", "text": "Controlled author transport; no generative model ran."}}}}}})
        send({{"method": "turn/completed", "params": {{"threadId": native_thread_id,
              "turn": {{"id": native_turn_id, "status": "completed", "error": None}}}}}})
'''
    node = matches[0]
    lines = source.splitlines(keepends=True)
    source = ''.join(lines[:node.lineno - 1]) + replacement + ''.join(lines[node.end_lineno:])
    source = source.replace("('controlled-only','controlled-alt')", repr((model,)), 1)
    compile(source, str(path), 'exec')
    path.write_text('#!/usr/bin/python3\n' + source)
    path.chmod(0o700)
    return digest(path.read_bytes())


def compare_code_pair(first, second):
    """Verify raw author packets and aliases before normalizing only production capture head identities."""
    normalized = []
    subjects = []
    inputs = []
    for original in (first, second):
        item = json.loads(json.dumps(original))
        author = item['controlled_author']
        packet = author['packet']
        snapshot = packet['snapshot']
        if subject_digest(snapshot) != packet['subject_sha256']:
            raise ValueError('Raw review subject does not match its packet hash')
        text = author['input_text']
        if digest(text.encode()) != snapshot['author_input']['input_sha256'] or len(text.encode()) != snapshot['author_input']['bytes']:
            raise ValueError('Original author input differs from its frozen packet')
        inputs.append(text)
        head = snapshot['candidate']['head_sha']
        if head != author['candidate']['head_sha']:
            raise ValueError('Author head differs from actual captured head')
        snapshot['candidate']['head_sha'] = 'verified-capture-head'
        subjects.append(snapshot)
        for attempt in item['attempts']:
            value = attempt['input']
            if value['execution']['head_sha'] != head:
                raise ValueError('Reviewer head is not its actual candidate head')
            if value['execution']['subject_sha256'] != packet['subject_sha256'] or value['review']['subject_sha256'] != packet['subject_sha256']:
                raise ValueError('Reviewer subject references another packet')
            value['execution']['head_sha'] = 'verified-capture-head'
            value['execution']['subject_sha256'] = 'verified-subject-digest'
            value['review']['subject_sha256'] = 'verified-subject-digest'
        normalized.append(item)
    if inputs[0] != inputs[1] or subjects[0] != subjects[1]:
        raise ValueError('Original author input or substantive review packet differs')
    result = compare_pair(*normalized)
    result['verified_capture_identity_variation'] = ['candidate.head_sha', 'derived subject_sha256 references']
    return result


def register(root, assets):
    """Freeze both real-reviewer policies and the separately counted non-generative author reservation."""
    operator = json.loads(assets.read_text())
    if operator.get('project_turn_limit', 1) < 1:
        raise ValueError('Operator permits no generative reviewer turn')
    ceilings = {'wall_seconds': 180, 'no_progress_seconds': 90, 'max_turns': 1,
                'max_tool_calls': 20, 'max_observed_tokens': 350000, 'max_answer_bytes': 20000}
    limits = {key: min(operator.get('limits', {}).get(key, cap), cap) for key, cap in ceilings.items()}
    limits['max_observed_tokens'] = min(limits['max_observed_tokens'], operator.get('project_token_limit', 350000))
    controlled = {**limits, 'max_observed_tokens': min(64000, limits['max_observed_tokens'])}
    baseline = json.loads((ROOT / 'evals/prompts/baseline.json').read_text())
    files = {'baseline.txt': baseline['instructions']['code_review'],
             'candidate.txt': build_instructions('code_review', 'code', limits=ExecutionLimits(**limits)),
             'evidence.py': SOURCE, 'test_evidence.py': TESTS, 'controlled-candidate.py': BAD_CANDIDATE,
             'author-request.txt': AUTHOR_REQUEST, 'case.json': json.dumps(CASE, ensure_ascii=False, indent=2) + '\n'}
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, text in files.items():
        (root / name).write_text(text)
    build_controlled_asset(root / 'controlled-native', operator['model'], BAD_CANDIDATE)
    hashes = {name: digest((root / name).read_bytes()) for name in [*files, 'controlled-native']}
    protocol = {'format': 1, 'execution_kind': 'code_review', 'task_type': 'code', 'profile': 'code_review',
                'case': CASE, 'request_prefix': PREFIX, 'files': hashes, 'reviewer_limits': limits,
                'controlled_author_limits': controlled, 'maximum_generative_turns': 2,
                'controlled_author_generative_turns': 0, 'controlled_author_reservations_per_arm': 1,
                'fixture_project_turns': 2,
                'fixture_project_tokens': limits['max_observed_tokens'] + controlled['max_observed_tokens'],
                'fixture_budget_ruling': 'Private fixture adds one non-generative controlled transport reservation. Actual subscription reviewer remains one turn under original operator ceilings. Original resource file unchanged; controlled usage stays separately attributed/unknown, not account expenditure.',
                'workspace_files': ['evidence.py', 'test_evidence.py'],
                'order': ['baseline', 'candidate'], 'operator_resources_sha256': digest(assets.read_bytes()),
                'baseline_commit': baseline['source_commit'],
                'source_commit': subprocess.check_output(['/usr/bin/git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'harness': {name: digest((ROOT / name).read_bytes()) for name in (
                    'evals/profile_communication/code_review.py', 'evals/profile_communication/development.py',
                    'evals/context_alignment/run.py', 'evals/context_alignment/worker.py',
                    'evals/context_alignment/protocol.py', 'evals/runtime/native_trial.py',
                    'backend/tests/runtime/fake_owned_native.py')},
                'allowed_model_receipt_variation': ['run_id', 'attempt_id', 'selected_at'],
                'allowed_capture_variation': ['snapshot.candidate.head_sha and its verified references', 'recomputed subject_sha256 and its verified references'],
                'human_comprehension': None, 'human_effort_seconds': None,
                'scope': 'One purposive exploratory pair; controlled author transport is not native model generation or human authorship. No general efficacy, acceptance or causal superiority claim.'}
    save(root / 'registration.json', protocol)
    (root / 'registration.sha256').write_text(digest((root / 'registration.json').read_bytes()) + '\n')
    return protocol


async def prepare_author(trial, root, protocol):
    """Create and close the original controlled native author through actual ownership, tools and Git capture."""
    from backend.api import config as api_config
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.config.settings import settings
    from backend.research.models import DEVELOPMENT_PERMISSIONS
    from backend.runtime import sqlite_runs
    from backend.runtime.broker_profile import CodexAsset
    from backend.runtime.code_reviews import CodeReviews
    from backend.runtime.contracts import RunSpec
    from backend.runtime.host_installation import host_environment
    from backend.runtime.peer_registry import AttemptPeers

    environment = host_environment(trial.installation)
    with ExitStack() as scope:
        scope.enter_context(patch.dict(os.environ, environment))
        scope.enter_context(patch.object(api_config, 'UPLOAD_DIR', environment['INFINIBAY_UPLOAD_BASE_DIR']))
        if 'INFINIBAY_STATIC_DIR' in environment:
            scope.enter_context(patch.object(api_config, 'STATIC_DIR', environment['INFINIBAY_STATIC_DIR']))
        scope.enter_context(patch.object(settings, 'RETRIEVAL_ASSET_DIR', environment.get('INFINIBAY_RETRIEVAL_ASSET_DIR')))
        app = create_app()
        coordinator = configured_runtime(app.state.live_grants, app=app)
        runtime = replace(coordinator.runtime, asset=CodexAsset.inspect(root / 'controlled-native'))
        store = coordinator.store
        binding = coordinator.workspaces.bind(101, 11)
        version = store.context_snapshot(101, 1001)['context_version']
        with patch.object(sqlite_runs, 'uuid4', side_effect=[UUID(int=1), UUID(int=2)]):
            run = store.admit(RunSpec(101, 1001, 'controlled-author', version, 'controlled-author',
                                     (root / 'author-request.txt').read_text(), 'codex'), binding=binding)
            lease, peers = AttemptPeers.claim(store, 101, run.run_id, 'controlled-author-fixture', lease_seconds=120)
        token = coordinator.research.issue_grant(project_id=101, task_id=1001, agent_id=lease.actor_id, permissions=set(DEVELOPMENT_PERMISSIONS))
        grant = coordinator.research.authorize(token)
        store.bind_grant(lease, grant.grant_id)
        app.state.live_grants.activate(grant.grant_id)

        async def heartbeat():
            """Keep the original bounded lease valid during real preparation and capture, without creating another owner."""
            while True:
                await asyncio.sleep(20)
                await asyncio.to_thread(store.heartbeat, lease, lease_seconds=120)

        async def on_started(thread_id, turn_id):
            """Bind the controlled transport IDs explicitly; they are not evidence of a generative model."""
            await asyncio.to_thread(store.bind_native, lease, thread_id=thread_id, turn_id=turn_id)

        try:
            async with asyncio.TaskGroup() as group:
                renew = group.create_task(heartbeat())
                try:
                    async with runtime.open(workspace=trial.workspace, tool_token=token, peer_owner=peers,
                                            limits=ExecutionLimits(**protocol['controlled_author_limits'])) as session:
                        store.bind_thread(lease, thread_id=session.thread_id)
                        frozen = store.reserve_input(lease, workspace=str(session.execution_workspace),
                            catalog_hash=session.catalog_hash, model=session.model,
                            developer_instructions=session.developer_instructions, catalog=session.catalog,
                            limits=ExecutionLimits(**protocol['controlled_author_limits']),
                            project_turn_limit=protocol['fixture_project_turns'], project_token_limit=protocol['fixture_project_tokens'])
                        if frozen is None:
                            raise RuntimeError('Controlled author input already reserved; do not replay')
                        result = await session.run(frozen.input_text, on_started=on_started)
                        if result.status != 'completed':
                            raise RuntimeError('Controlled transport did not complete; preserve original attempt')
                        candidate = await session.capture_candidate()
                        if candidate['state'] != 'ready':
                            raise RuntimeError('No sealed original candidate')
                finally:
                    renew.cancel()
        finally:
            app.state.live_grants.withdraw(grant.grant_id)
            await asyncio.to_thread(app.state.live_grants.wait_closed, grant.grant_id)
            coordinator.research.revoke_grant(grant.grant_id)
            await peers.aclose()
        if not peers.closed() or not runtime.consume_closure(lease):
            raise RuntimeError('Original author physical closure remains unproven')
        store.settle_inference(lease, observed_tokens=result.observed_tokens, native_status=result.status)
        store.finish(lease, native_status=result.status, summary=result.text)
        packet = CodeReviews(store).subject(101, lease.attempt_id)
        return {'packet': packet, 'candidate': {k: candidate[k] for k in ('attempt_id', 'state', 'base_sha', 'head_sha', 'tree_sha', 'diff_sha256')},
                'input_text': frozen.input_text, 'controlled_transport_asset_sha256': digest((root / 'controlled-native').read_bytes()),
                'generative_model_turns': 0, 'native_transport_reservations': 1,
                'controlled_observed_tokens': result.observed_tokens, 'peers_closed': len(peers._rows())}


async def run_review_arm(root, protocol, arm, assets):
    """Capture one original controlled author, then admit one actual subscription reviewer without replay."""
    from evals.profile_communication.development import prepare_workspace

    folder = root / (CASE['id'] + '-' + arm)
    if folder.exists():
        raise FileExistsError('Arm already started; inspect its original receipts')
    resources = json.loads(assets.read_text())
    if digest(assets.read_bytes()) != protocol['operator_resources_sha256']:
        raise ValueError('Operator resources changed after registration')
    # A separate fixture reservation accommodates the non-generative author transport.
    # The actual reviewer still has exactly the original per-turn/operator ceilings.
    resources.update(limits=protocol['reviewer_limits'], project_turn_limit=protocol['fixture_project_turns'],
                     project_token_limit=protocol['fixture_project_tokens'], development_checks=[])
    private = root / (arm + '-assets.json')
    with os.fdopen(os.open(private, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(resources, stream)
    trial = prepare(folder, private, live=True, turns=2, task_type='code', task_title='Mean of observations including zeroes')
    (trial.workspace / 'evidence.py').write_bytes((root / 'evidence.py').read_bytes())
    base = prepare_workspace(trial, root, protocol)
    evidence = {'case_id': CASE['id'], 'arm': arm, 'status': 'preparing_controlled_author',
                'runs': [], 'admissions_sent': 0, 'actual_reviewer_turn_budget': 1,
                'controlled_author_generative_turns': 0, 'source_base_sha': base}
    save(folder / 'result.json', evidence)
    started = time.monotonic()
    try:
        author = await prepare_author(trial, root, protocol)
        evidence.update(controlled_author=author, status='running_reviewer')
        save(folder / 'result.json', evidence)
        starter = partial(start_policy, policy=root / (arm + '.txt'), expected_hash=protocol['files'][arm + '.txt'],
                          gate=False, task_type='code', execution_kind='code_review')
        async with backend(trial, evidence, starter=starter) as (_store, owner, _api, _database):
            evidence['admissions_sent'] = 1
            save(folder / 'result.json', evidence)
            response = await owner.post('/api/projects/101/tasks/1001/code-reviews', json={
                'operation_key': 'registered-review', 'context_version': 1,
                'attempt_id': author['candidate']['attempt_id'], 'subject_sha256': author['packet']['subject_sha256'],
                'request': protocol['request_prefix'] + protocol['case']['request']})
            evidence['admission_receipt'] = {'status': response.status_code, 'body': response.json()}
            save(folder / 'result.json', evidence)
            response.raise_for_status()
            run_id = response.json()['run_id']
            evidence['runs'].append(await terminal(owner, run_id))
            observed = observations(trial)
            all_attempts = observed.pop('attempts')
            observed['controlled_attempts'] = [a for a in all_attempts if a['input'].get('execution', {}).get('kind') == 'development']
            observed['attempts'] = [a for a in all_attempts if a['input'].get('execution', {}).get('kind') == 'code_review']
            evidence.update(observed)
            state = await owner.get('/api/projects/101/runs/' + author['packet']['snapshot']['author']['run_id'] + '/code-result')
            state.raise_for_status()
            evidence['code_state'] = state.json()
            with sqlite3.connect(trial.database) as db:
                db.row_factory = sqlite3.Row
                evidence['review_records'] = [dict(row) for row in db.execute('SELECT state,proposal_json,result_json FROM runtime_code_review_records')]
            evidence['original_source_unchanged'] = all((trial.workspace / name).read_bytes() == (root / name).read_bytes() for name in protocol['workspace_files'])
            if (evidence['runs'][-1]['status'] != 'needs_review' or evidence['unrevoked_grants']
                    or any(p['state'] != 'closed' for p in evidence['peers']) or not evidence['original_source_unchanged']):
                raise RuntimeError('Review incomplete, original changed or original peers remain open')
            if len(evidence['review_records']) != 1 or evidence['review_records'][0]['state'] != 'confirmed':
                raise RuntimeError('No confirmed original review proposal')
            verify_ken(evidence['tools'], required_source=(root / 'controlled-candidate.py').read_text())
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
    """Run the two preregistered original arms serially; retain all raw identity differences and failures."""
    protocol = load_registered(root)
    if any((root / (CASE['id'] + '-' + arm)).exists() for arm in protocol['order']):
        raise FileExistsError('Comparison already started; inspect original receipts')
    pair = {}
    for arm in protocol['order']:
        protocol = load_registered(root)
        if any(digest((ROOT / name).read_bytes()) != sha for name, sha in protocol['harness'].items()):
            raise ValueError('Registered evaluator changed')
        pair[arm] = await run_review_arm(root, protocol, arm, assets)
        if len(pair[arm]['attempts']) != 1 or pair[arm]['attempts'][0]['instructions_sha256'] != protocol['files'][arm + '.txt']:
            raise ValueError('Actual reviewer policy or generative turn count differs')
    comparison = compare_code_pair(pair['baseline'], pair['candidate'])
    save(root / 'comparison.json', comparison)
    export_review(root, protocol['case'], pair)
    return comparison


def main():
    """Keep account-free registration separate from one real native reviewer per selected arm."""
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
