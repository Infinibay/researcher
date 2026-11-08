"""Observe one genuinely active owned command through the web UI, without generative model work.

The controlled native transport still uses the actual coordinator, private
development workspace, Ken and command capsules. A bounded file gate holds the
original command until the browser has inspected its receipt at both widths.
"""

import argparse
import ast
import asyncio
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = '.ui-communication-gate'


def save(path, value):
    """Retain the original outcome in private evidence without credentials or session cookies."""
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def controlled_asset(path, model, candidate):
    """Reuse the native fixture and change only the candidate writer, bounded gate and polling interval."""
    from evals.profile_communication.code_review import build_controlled_asset

    build_controlled_asset(path, model, candidate)
    tree = ast.parse(path.read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'next_development_tool')
    writers = [n for n in ast.walk(function) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == 'call' and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == 'researcher_python']
    if len(writers) != 1:
        raise ValueError('Inspect changed controlled writer before execution')
    code = f'''from pathlib import Path
import time
Path("evidence.py").write_text({candidate!r})
gate = Path({GATE!r})
gate.mkdir()
(gate / "ready").write_text("Original owned command is waiting.\\n")
print("Candidate written; waiting for UI receipt inspection.", flush=True)
try:
    deadline = time.monotonic() + 60
    while not (gate / "release").exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("UI gate was not released within its declared bound")
        time.sleep(.05)
finally:
    for entry in gate.iterdir():
        entry.unlink()
    gate.rmdir()
print("UI inspection finished; original command completed.", flush=True)
'''
    writers[0].args[1] = ast.parse(repr({'operation_key': 'controlled-write', 'code': code, 'timeout_seconds': 80.0}), mode='eval').body
    polls = [n for n in ast.walk(function) if isinstance(n, ast.If) and isinstance(n.test, ast.Compare)
             and isinstance(n.test.left, ast.Subscript) and ast.unparse(n.test.left) == "value['status']"
             and any(isinstance(op, ast.NotIn) for op in n.test.ops)]
    if len(polls) != 1:
        raise ValueError('Inspect changed controlled polling before execution')
    polls[0].body.insert(0, ast.parse('time.sleep(2)').body[0])
    command_timeouts = [keyword for node in ast.walk(tree) if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == 'subprocess' and node.func.attr == 'run'
                        for keyword in node.keywords if keyword.arg == 'timeout'
                        and isinstance(keyword.value, ast.Constant) and keyword.value.value == 8]
    if len(command_timeouts) != 1:
        raise ValueError('Inspect changed native fixture command transport timeout')
    # The original short test fixture would kill the real gated command at8s.
    # Product command80s and project limits remain unchanged; only this copy
    # of the deterministic transport permits the declared operational probe.
    command_timeouts[0].value = ast.Constant(value=90)
    ast.fix_missing_locations(tree)
    path.write_text('#!/usr/bin/python3\n' + ast.unparse(tree) + '\n')
    path.chmod(0o700)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def starter(asset, expected_hash, installation, output, port, ordinal):
    """Own one isolated application process and wait for its original readiness, never replaying an admission."""
    import httpx
    from evals.operation.host_smoke import stop

    log = (output / f'service-{ordinal}.log').open('x')
    process = subprocess.Popen([sys.executable, '-I', str(ROOT / 'evals/communication/wait_worker.py'),
                                '--installation', str(installation), '--asset', str(asset), '--sha256', expected_hash,
                                '--port', str(port)], cwd=installation / 'service', stdout=log, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 30
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=1) as client:
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('Original evaluation service exited; inspect private log')
                try:
                    response = client.get('/api/health/ready')
                    if response.status_code == 200 and response.json() == {'ready': True}:
                        return process, log
                except httpx.TransportError:
                    pass
                time.sleep(.1)
        raise TimeoutError('Evaluation service did not become ready')
    except BaseException:
        stop(process, log)
        raise


def observed(database):
    """Read original run/workspace identities and actual closure metadata without mutating product history."""
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
        return {'runs': db.execute('SELECT id,status FROM runtime_runs ORDER BY created_at').fetchall(),
                'workspaces': db.execute('SELECT run_id,workspace FROM runtime_development_workspaces WHERE workspace IS NOT NULL').fetchall(),
                'dispatches': db.execute('SELECT status,observed_tokens,native_status FROM runtime_inference_dispatches').fetchall(),
                'open_peers': db.execute("SELECT COUNT(*) FROM runtime_peers WHERE state!='closed'").fetchone()[0],
                'open_grants': db.execute('SELECT COUNT(*) FROM tool_grants WHERE revoked_at IS NULL').fetchone()[0],
                'candidates': db.execute('SELECT state FROM runtime_code_candidates').fetchall()}


async def run(args):
    """Send one actual web instruction, inspect its active command, release that command and retain its terminal receipt."""
    from functools import partial
    from evals.profile_communication.code_review import AUTHOR_REQUEST, BAD_CANDIDATE, SOURCE, TESTS
    from evals.profile_communication.development import prepare_workspace
    from evals.runtime.native_trial import backend, prepare

    root = args.output.resolve()
    if not root.is_relative_to(ROOT / '.researcher/evaluations'):
        raise ValueError('Use a new private synthetic evaluation output')
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    resources = json.loads(args.assets.read_text())
    resources['development_checks'] = []
    # Preserve the normal network identity check while isolating this fixture
    # from system resolver/trust replacement after service composition.
    from backend.runtime.native_network import PublicNetworkFile

    network_inputs = {}
    for kind, fallback in (('resolver', '/etc/resolv.conf'), ('ca_bundle', '/etc/ssl/certs/ca-certificates.crt')):
        original = PublicNetworkFile.inspect(resources.get(kind, fallback), kind)
        data = Path(original.path).read_bytes()
        if hashlib.sha256(data).hexdigest() != original.sha256:
            raise ValueError('Public network input changed while freezing the fixture')
        target = root / ('public-' + kind)
        target.write_bytes(data)
        target.chmod(0o600)
        resources[kind] = str(target)
        network_inputs[kind] = {'source': original.path, 'sha256': original.sha256}
    private_assets = root / 'assets.json'
    private_assets.write_text(json.dumps(resources))
    private_assets.chmod(0o600)
    candidate = BAD_CANDIDATE.replace(' for record in list_observations(records) if record["value"]', ' for record in list_observations(records)')
    if candidate == BAD_CANDIDATE:
        raise ValueError('Frozen candidate correction no longer matches')
    (root / 'evidence.py').write_text(SOURCE)
    (root / 'test_evidence.py').write_text(TESTS)
    asset = root / 'controlled-native'
    expected_hash = controlled_asset(asset, resources['model'], candidate)
    registration = {'scope': 'Managed active command and UI receipt, controlled non-generative native transport',
                    'generative_model_turns': 0, 'maximum_native_reservations': 1,
                    'controlled_asset_sha256': expected_hash, 'gate_timeout_seconds': 60,
                    'command_timeout_seconds': 80, 'minimum_browser_wait_seconds': 10,
                    'fixture_command_transport_timeout_seconds': 90,
                    'source_sha256': hashlib.sha256(SOURCE.encode()).hexdigest(),
                    'candidate_sha256': hashlib.sha256(candidate.encode()).hexdigest(),
                    'operator_resources_sha256': hashlib.sha256(args.assets.read_bytes()).hexdigest(),
                    'public_network_inputs': network_inputs,
                    'harness_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                       for name in ('evals/communication/live_wait.py', 'evals/communication/wait_worker.py',
                                                    'frontend/tests/communication-wait.mjs')},
                    'human_comprehension': None, 'request': AUTHOR_REQUEST}
    save(root / 'registration.json', registration)
    trial = prepare(root / 'trial', private_assets, live=True, turns=1, task_type='code', task_title='Comprobar una media durante una espera controlada')
    prepare_workspace(trial, root, {'workspace_files': ['evidence.py', 'test_evidence.py']})
    initial = hashlib.sha256((trial.workspace / 'evidence.py').read_bytes()).hexdigest()
    result = {'status': 'running', 'generative_model_turns': 0}
    process = None
    gate = None
    started = time.monotonic()
    try:
        async with backend(trial, result, starter=partial(starter, asset, expected_hash)) as (_, owner, api, _):
            keys = list((trial.installation / 'auth').glob('owner-*.key'))
            if len(keys) != 1:
                raise RuntimeError('Expected one original service pairing file')
            fixture = {**registration, 'title': 'Comprobar una media durante una espera controlada'}
            save(root / 'browser-fixture.json', fixture)
            environment = {**os.environ, 'RESEARCHER_E2E_ORIGIN': api, 'RESEARCHER_E2E_OUTPUT': str(root / 'browser'),
                           'RESEARCHER_E2E_OWNER_FILE': str(keys[0]), 'RESEARCHER_E2E_FIXTURE': str(root / 'browser-fixture.json'),
                           'RESEARCHER_E2E_COORDINATION': str(root)}
            with (root / 'browser.log').open('x') as log:
                process = subprocess.Popen([str(args.node.resolve(strict=True)), 'tests/communication-wait.mjs'], cwd=ROOT / 'frontend',
                                           env=environment, stdout=log, stderr=subprocess.STDOUT)
                try:
                    async with asyncio.timeout(180):
                        while True:
                            state = observed(trial.database)
                            if any(status in ('failed', 'cancelled', 'reconciling') for _, status in state['runs']):
                                raise RuntimeError('Original managed attempt stopped before the expected gate; inspect its receipts')
                            if process.poll() is not None:
                                raise RuntimeError('Original browser ended before tool readiness')
                            if len(state['workspaces']) == 1:
                                run_id, workspace = state['workspaces'][0]
                                possible = Path(workspace) / GATE
                                if (possible / 'ready').exists():
                                    gate = possible
                                    break
                            await asyncio.sleep(.1)
                        jobs = (await owner.get(f'/api/projects/101/runs/{run_id}/jobs')).json()
                        if jobs['total'] != 1 or jobs['items'][0]['status'] != 'dispatching' or jobs['items'][0]['local_execution_closed']:
                            raise RuntimeError('Expected one actually active original command')
                        result['active_observation'] = {'state': state, 'jobs': jobs}
                        save(root / 'tool-ready.json', {'run_id': run_id, 'job_id': jobs['items'][0]['job_id']})
                        gate_started = time.monotonic()
                        while not (root / 'wait-captured').exists():
                            if process.poll() is not None:
                                raise RuntimeError('Original browser failed during active receipt inspection')
                            await asyncio.sleep(.1)
                        result['observed_gate_seconds'] = round(time.monotonic() - gate_started, 3)
                        (gate / 'release').write_text('Release this same original owned command.\n')
                        while process.poll() is None:
                            await asyncio.sleep(.1)
                        if process.returncode:
                            raise RuntimeError('Browser failed after release; inspect original evidence')
                        result['terminal_jobs'] = (await owner.get(f'/api/projects/101/runs/{run_id}/jobs')).json()
                        receipt = await owner.get(f'/api/projects/101/runs/{run_id}/jobs/{jobs["items"][0]["job_id"]}')
                        result['terminal_receipt'] = receipt.json()
                finally:
                    if gate is not None and gate.exists():
                        (gate / 'release').write_text('Cleanup release of original command.\n')
                    if process is not None and process.poll() is None:
                        process.terminate()
                        process.wait(timeout=10)
        result['after'] = observed(trial.database)
        result['source_unchanged'] = initial == hashlib.sha256((trial.workspace / 'evidence.py').read_bytes()).hexdigest()
        receipt = result['terminal_receipt']
        if (len(result['after']['runs']) != 1 or result['after']['runs'][0][1] != 'needs_review'
                or result['after']['open_peers'] or result['after']['open_grants'] or not result['source_unchanged']
                or result['terminal_jobs']['total'] != 1 or receipt['status'] != 'exited'
                or receipt['exit_code'] != 0 or not receipt['local_execution_closed']):
            raise RuntimeError('Inspect original closure or candidate; do not replay')
        result['status'] = 'passed'
    except BaseException as error:
        result.update(status='failed', error_type=type(error).__name__, after=observed(trial.database))
        raise
    finally:
        result['seconds'] = round(time.monotonic() - started, 3)
        save(root / 'result.json', result)
        print({k: v for k, v in result.items() if k not in ('active_observation', 'terminal_receipt', 'terminal_jobs', 'after')})


def main():
    """Require explicit private paths and installed Python before importing repository evaluation helpers."""
    import backend

    if not Path(backend.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError('Use installed product Python with -I')
    sys.path.insert(0, str(ROOT))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--node', type=Path, required=True)
    asyncio.run(run(parser.parse_args()))


if __name__ == '__main__':
    main()
