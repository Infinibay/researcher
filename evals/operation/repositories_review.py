"""Review lost registration receipts and project changes on a retained completed synthetic repository installation."""

import argparse
import hashlib
import json
import os
import socket
import sqlite3
import subprocess
from pathlib import Path

from host_smoke import start, stop
from repositories_workspace import inspect


def original_operations(host):
    """Bind original administrative history before complementary registration, without treating general project metadata as immutable."""
    with sqlite3.connect(host / 'source.db') as db:
        values = [json.loads(row[0] or '{}').get('owner_repository_operations_v1', {}) for row in db.execute('SELECT metadata_json FROM projects ORDER BY id')]
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def main():
    """Require a passed synthetic original, retain its exact source operations, and close the new service by its actual handle."""
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--node', type=Path, required=True)
    args = parser.parse_args()
    original = args.original.resolve(strict=True)
    receipt = json.loads((original / 'result.json').read_text())
    assert receipt['status'] == 'passed' and receipt['model_turns'] == 0
    assert receipt['scope'].startswith('Installed owner HTTP/SQLite/filesystem and real TLS smart Git')
    host = original / 'host'; before = original_operations(host)
    assert inspect(host)['runs'] == inspect(host)['dispatches'] == 0
    output = args.output.absolute(); output.mkdir(mode=0o700)
    late = host / 'sources/late-existing'
    if late.exists():
        assert late.is_dir() and not late.is_symlink() and (late / 'nota.txt').read_text() == 'Registro tardío; no debe cambiar la selección actual.\n'
    else:
        late.mkdir()
        (late / 'nota.txt').write_text('Registro tardío; no debe cambiar la selección actual.\n')
    with socket.socket() as binding:
        binding.bind(('127.0.0.1', 0)); port = binding.getsockname()[1]
    result = {'status': 'running', 'model_turns': 0, 'scope': 'Complementary actual owner registration and lost/late receipts; no original setup replay or external server request'}
    process = log = None
    try:
        process, log = start(host, output, port, 2)
        keys = list((host / 'auth').glob('owner-*.key')); assert len(keys) == 1
        env = {**os.environ, 'RESEARCHER_E2E_ORIGIN': f'http://127.0.0.1:{port}', 'RESEARCHER_E2E_OWNER_FILE': str(keys[0]),
               'RESEARCHER_E2E_OUTPUT': str(output / 'browser'), 'RESEARCHER_E2E_REPOSITORY_FIXTURE': str(original / 'fixture.json'),
               'RESEARCHER_E2E_REPOSITORY_RECEIPT': str(original / 'browser/evidence.json')}
        with (output / 'browser.log').open('x') as stream:
            browser = subprocess.run([str(args.node.resolve(strict=True)), 'tests/repositories-review.e2e.mjs'], cwd=root / 'frontend', env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=240)
        result['browser_exit'] = browser.returncode
        assert browser.returncode == 0
        result['status'] = 'passed'
    except BaseException as error:
        result.update(status='failed', error_type=type(error).__name__)
        raise
    finally:
        if process is not None: result['service_exit'] = stop(process, log)
        result['storage'] = inspect(host)
        result['original_operations_unchanged'] = original_operations(host) == before
        (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        assert result['original_operations_unchanged']
        print(json.dumps({'status': result['status'], 'receipt': str(output / 'result.json')}))


if __name__ == '__main__':
    main()
