"""Accept owner repository setup and immutable reading on a fresh installed host with actual local TLS/Git and controlled provider REST."""

import argparse
import hashlib
import json
import os
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

from host_smoke import start, stop
from repository_fixture import repository_fixture


def inspect(host):
    """Read durable identities independently of browser labels without serializing credentials or full runtime metadata."""
    with sqlite3.connect(host / 'source.db') as db:
        db.row_factory = sqlite3.Row
        operations = [row for project in db.execute('SELECT metadata_json FROM projects')
                      for row in json.loads(project[0] or '{}').get('owner_repository_operations_v1', {}).values()]
        return {'integrity': db.execute('PRAGMA integrity_check').fetchone()[0],
                'runs': db.execute('SELECT COUNT(*) FROM runtime_runs').fetchone()[0],
                'dispatches': db.execute('SELECT COUNT(*) FROM runtime_inference_dispatches').fetchone()[0],
                'unclosed_peers': db.execute("SELECT COUNT(*) FROM runtime_peers WHERE state!='closed'").fetchone()[0],
                'source_operations': [{'operation_id': row['operation_id'], 'status': row['status'],
                                       'closure': row.get('closure'), 'http_client_state': (row.get('http_client') or {}).get('state'),
                                       'unclosed_peers': sum(peer['state'] != 'closed' for peer in row.get('peers', {}).values())}
                                      for row in operations],
                'repositories': [dict(row) for row in db.execute('SELECT id,project_id,name,local_path,default_branch FROM repositories ORDER BY id')]}


def main():
    """Retain the original host on failure and close its actual service handle before retiring owned test servers."""
    import backend
    from backend.runtime.host_installation import initialize_host

    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--node', type=Path, required=True)
    args = parser.parse_args()
    assert Path(backend.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    output = args.output.absolute(); output.mkdir(mode=0o700)
    account = output / 'synthetic-account.json'
    account.write_text(json.dumps({'auth_mode': 'chatgpt', 'tokens': {'access_token': 'synthetic.header.signature', 'account_id': 'synthetic-repositories'}})); account.chmod(0o600)
    assets = json.loads(args.assets.read_text()); assets['token_file'] = str(account)
    assets['static_dir'] = str(root / 'frontend/dist'); assets.pop('storage', None)
    host = output / 'host'
    initialize_host(host, witness_dir=output / 'witness', assets=assets)
    with socket.socket() as binding:
        binding.bind(('127.0.0.1', 0)); port = binding.getsockname()[1]
    result = {'status': 'running', 'model_turns': 0, 'web_index_sha256': hashlib.sha256((root / 'frontend/dist/index.html').read_bytes()).hexdigest(),
              'scope': 'Installed owner HTTP/SQLite/filesystem and real TLS smart Git; controlled Forgejo REST fixture, no user remote or paid inference'}
    try:
        with repository_fixture(output, host) as fixture:
            fixture_path = output / 'fixture.json'; fixture_path.write_text(json.dumps(fixture, indent=2) + '\n')
            process = log = None
            try:
                process, log = start(host, output, port, 1)
                keys = list((host / 'auth').glob('owner-*.key')); assert len(keys) == 1
                env = {**os.environ, 'RESEARCHER_E2E_ORIGIN': f'http://127.0.0.1:{port}', 'RESEARCHER_E2E_OWNER_FILE': str(keys[0]),
                       'RESEARCHER_E2E_OUTPUT': str(output / 'browser'), 'RESEARCHER_E2E_REPOSITORY_FIXTURE': str(fixture_path)}
                with (output / 'browser.log').open('x') as stream:
                    browser = subprocess.run([str(args.node.resolve(strict=True)), 'tests/repositories.e2e.mjs'], cwd=root / 'frontend', env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=450)
                result['browser_exit'] = browser.returncode
                assert browser.returncode == 0, 'Inspect retained original browser evidence; do not replay uncertain operations'
                result['status'] = 'passed'
            finally:
                if process is not None: result['service_exit'] = stop(process, log)
                result['storage'] = inspect(host)
                assert result['storage']['runs'] == result['storage']['dispatches'] == 0
                assert result['storage']['integrity'] == 'ok' and result['storage']['unclosed_peers'] == 0
    except BaseException as error:
        result.update(status='failed', error_type=type(error).__name__)
        raise
    finally:
        (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({'status': result['status'], 'receipt': str(output / 'result.json')}))


if __name__ == '__main__':
    main()
