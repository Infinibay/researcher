"""Observe one explicitly authorized subscription planning turn in the real UI, preserving actual Ken responses and the production prompt policy."""

import argparse
import hashlib
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4


def worker(root, port):
    """Instrument actual tool results without replacing prompts, native generation, authority or the returned response."""
    import uvicorn
    from backend.runtime.business_mediation import ProjectTools
    from backend.runtime.host_installation import host_environment

    os.environ.update(host_environment(root))
    original = ProjectTools.call

    async def recorded(self, params):
        """Append the original mediated result before forwarding it unchanged, retaining tool identity and timing in private evaluation output."""
        started = time.monotonic()
        response = await original(self, params)
        event = {'tool': params.get('tool'), 'arguments': params.get('arguments'),
                 'response': response, 'seconds': time.monotonic() - started}
        with (root.parent / 'tools.jsonl').open('a') as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + '\n')
        return response

    ProjectTools.call = recorded
    uvicorn.run('backend.api.main:create_app', factory=True, host='127.0.0.1', port=port,
                loop='uvloop', log_level='warning', access_log=False)


def supervisor(root, port):
    """Keep the instrumented API inside the unchanged production service guardian and configured resource limits."""
    from backend.runtime.host_installation import host_environment
    from backend.runtime.service_process import run_bounded_services

    os.environ.update(host_environment(root))
    config = json.loads((root / 'runtime.json').read_text())
    raise SystemExit(run_bounded_services([('API-language-evaluation', [sys.executable, '-I', __file__, 'worker', str(root), str(port)], root / 'service')],
                                         cgroup_parent=config['cgroup_parent'], limits=config['service_limits'], state_dir=root / 'service'))


def observe(root):
    """Count durable starts independently and preserve terminal state without loading prompts, credentials or model prose."""
    with sqlite3.connect(root / 'source.db') as db:
        db.row_factory = sqlite3.Row
        return {'runs': [dict(row) for row in db.execute('SELECT id,project_id,status FROM runtime_runs')],
                'dispatches': [dict(row) for row in db.execute('SELECT model,status,native_status FROM runtime_inference_dispatches')],
                'native_starts': db.execute('SELECT COUNT(*) FROM runtime_attempts WHERE turn_id IS NOT NULL').fetchone()[0],
                'unclosed_peers': db.execute("SELECT COUNT(*) FROM runtime_peers WHERE state!='closed'").fetchone()[0],
                'tasks': [dict(row) for row in db.execute('SELECT id,project_id,title,status FROM tasks ORDER BY id')],
                'integrity': db.execute('PRAGMA integrity_check').fetchone()[0]}


def main():
    """Create a fresh synthetic case, admit at most one real planning turn, and retain its original installation on every outcome."""
    import backend
    import httpx
    from backend.runtime.host_installation import initialize_host

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', required=True)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--node', type=Path, required=True)
    args = parser.parse_args()
    assert Path(backend.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    repo = Path(__file__).resolve().parents[2]
    output = args.output.absolute(); output.mkdir(mode=0o700)
    assets = json.loads(args.assets.read_text()); assets.pop('storage', None)
    caps = {'wall_seconds': 180, 'no_progress_seconds': 90, 'max_turns': 1, 'max_tool_calls': 25, 'max_observed_tokens': 350000}
    assets['limits'] = {**assets.get('limits', {}), **{name: min(assets.get('limits', {}).get(name, cap), cap) for name, cap in caps.items()}}
    assets['project_turn_limit'] = min(assets.get('project_turn_limit', 1), 1)
    assets['project_token_limit'] = min(assets.get('project_token_limit', 350000), 350000)
    assets['static_dir'] = str(repo / 'frontend/dist')
    host = output / 'host'; initialize_host(host, witness_dir=output / 'witness', assets=assets)
    source = host / 'sources/observations'; source.mkdir()
    item = source / 'observations.py'
    item.write_text('"""List retained observations without exporting files."""\ndef list_observations(records):\n    """Return original records in order."""\n    return list(records)\n')
    digest = hashlib.sha256(item.read_bytes()).hexdigest()
    (output / 'tools.jsonl').touch(mode=0o600)
    with socket.socket() as binding:
        binding.bind(('127.0.0.1', 0)); port = binding.getsockname()[1]
    result = {'status': 'running', 'maximum_native_turns': 1, 'source_sha256': digest,
              'scope': 'One new authorized subscription plan; unchanged production prompts; actual mediated Ken results; no child task execution',
              'limits': assets['limits'], 'model': assets.get('model')}
    (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    process = None
    with (output / 'service.log').open('x') as service_log:
        try:
            process = subprocess.Popen([sys.executable, '-I', __file__, 'supervisor', str(host), str(port)], cwd=host / 'service', stdout=service_log, stderr=subprocess.STDOUT)
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=5) as client:
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if process.poll() is not None: raise RuntimeError('Original service exited before readiness')
                    try:
                        if client.get('/api/health/ready').status_code == 200: break
                    except httpx.TransportError: pass
                    time.sleep(.1)
                else: raise TimeoutError('Readiness deadline expired')
                keys = list((host / 'auth').glob('owner-*.key')); assert len(keys) == 1
                paired = client.post('/api/session', json={'code': keys[0].read_text().strip()}, headers={'X-Researcher-Client': 'web'}); paired.raise_for_status()
                client.headers.update({'X-Researcher-CSRF': paired.json()['csrf_token'], 'X-Researcher-Endpoint': paired.json()['endpoint_id']})
                created = client.post('/api/projects', json={'name': 'Beta separado', 'description': 'Proyecto sintético independiente.', 'operation_key': uuid4().hex}); created.raise_for_status(); beta = created.json()['id']
            description = ('Sólo prepara dos o tres tareas para añadir exportación CSV a observations.py: columnas id y value, cabecera, UTF-8 y orden original. '
                           'Usa la biblioteca csv estándar y unittest. Reutiliza list_observations. Antes de proponer, usa ken_find con consulta en inglés y ken_read '
                           'incluyendo source y un rango o qualname para comprobar la implementación, no sólo la documentación. Explica qué observaste y qué supones. '
                           'Entrega tareas, criterios y explicación en español. No implementes ni ejecutes el trabajo propuesto; no hacen falta fechas ni elegir otro formato.')
            env = {**os.environ, 'RESEARCHER_E2E_ORIGIN': f'http://127.0.0.1:{port}', 'RESEARCHER_E2E_OWNER_FILE': str(keys[0]),
                   'RESEARCHER_E2E_OUTPUT': str(output / 'browser'), 'RESEARCHER_E2E_PROJECT_SOURCE': str(source),
                   'RESEARCHER_E2E_PROJECT_RESUME': json.dumps({'mode': 'fresh-generation', 'beta': beta}),
                   'RESEARCHER_E2E_PROJECT_NAME': 'Plan CSV en español verificado', 'RESEARCHER_E2E_PROJECT_DESCRIPTION': description}
            with (output / 'browser.log').open('x') as browser_log:
                browser = subprocess.run([str(args.node.resolve(strict=True)), 'tests/projects.e2e.mjs'], cwd=repo / 'frontend', env=env, stdout=browser_log, stderr=subprocess.STDOUT, timeout=360, check=False)
            result['browser_exit'] = browser.returncode
            assert browser.returncode == 0, 'Preserve original run and inspect its receipts; no automatic replay'
            result['status'] = 'observed'
        except BaseException as error:
            result.update(status='failed', error_type=type(error).__name__)
            raise
        finally:
            if process is not None:
                if process.poll() is None: process.terminate()
                result['service_exit'] = process.wait(timeout=30)
            result['storage'] = observe(host)
            result['source_unchanged'] = hashlib.sha256(item.read_bytes()).hexdigest() == digest
            (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
            assert result['storage']['native_starts'] <= 1 and result['source_unchanged']
            print(json.dumps({'status': result['status'], 'native_starts': result['storage']['native_starts'], 'unclosed_peers': result['storage']['unclosed_peers']}))


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'worker': worker(Path(sys.argv[2]), int(sys.argv[3]))
    elif len(sys.argv) > 1 and sys.argv[1] == 'supervisor': supervisor(Path(sys.argv[2]), int(sys.argv[3]))
    else: main()
