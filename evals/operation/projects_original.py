"""Inspect the retained failed planning attempt in the installed UI without admitting work or rewriting its historical issue."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals/operation'))
from host_smoke import start, stop
from web_workspace import observe as original_projection

RUN = 'dff92343-be0a-4bad-93ad-8bc8aa2ef2de'
PROJECT = 5
TASK = 6


def observe(host):
    """Hash all original logical rows and source bytes while separating schema history from business effects."""
    with closing(sqlite3.connect((host / 'source.db').resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        hashes = {}
        counts = {}
        for name in tables:
            rows = [dict(row) for row in db.execute('SELECT * FROM "' + name.replace('"', '""') + '"')]
            counts[name] = len(rows)
            rows.sort(key=lambda row: json.dumps(row, sort_keys=True, default=str))
            hashes[name] = hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()
        repos = [Path(r[0]) for r in db.execute('SELECT local_path FROM repositories ORDER BY id')]
        sources = {str(p / 'observations.py'): hashlib.sha256((p / 'observations.py').read_bytes()).hexdigest() for p in repos}
        run = dict(db.execute('SELECT id,project_id,task_id,current_attempt_id,status,context_version,issue_json FROM runtime_runs WHERE id=?', (RUN,)).fetchone())
        return {'hashes': hashes, 'counts': counts, 'sources': sources, 'run': run,
                'schema': db.execute('SELECT max(version) FROM schema_migrations').fetchone()[0],
                'open_peers': db.execute("SELECT count(*) FROM runtime_peers WHERE state!='closed'").fetchone()[0],
                'open_grants': db.execute('SELECT count(*) FROM tool_grants WHERE revoked_at IS NULL').fetchone()[0],
                'integrity': db.execute('PRAGMA integrity_check').fetchone()[0],
                'foreign_keys': [tuple(r) for r in db.execute('PRAGMA foreign_key_check')]}


def preserved(before, after):
    """Permit only the declared 68-to-71 schema transition, preserving original rows and requiring new tables to remain empty."""
    assert after['schema'] == 71 and before['schema'] in (68, 71)
    assert before['sources'] == after['sources'] and before['run'] == after['run']
    for name, digest in before['hashes'].items():
        if name != 'schema_migrations':
            assert after['hashes'][name] == digest, name
    for name in set(after['counts']) - set(before['counts']):
        assert after['counts'][name] == 0, name
    assert after['open_peers'] == after['open_grants'] == 0
    assert after['integrity'] == 'ok' and not after['foreign_keys']


def main():
    """Validate retained evidence before owning one installed service/browser lifetime; always retain the actual continuation and closure."""
    import backend

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--node', type=Path, required=True)
    args = parser.parse_args()
    started_at = datetime.now(timezone.utc).isoformat()
    clock = time.monotonic()
    assert Path(backend.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    original = args.original.resolve(strict=True)
    host = original / 'host'
    retained = json.loads((original / 'language-regression/result.json').read_text())
    before = observe(host)
    projection = original_projection(host / 'source.db')
    for key, value in retained['storage'].items():
        assert projection[key] == value, key
    assert before['run']['project_id'] == PROJECT and before['run']['task_id'] == TASK
    assert before['run']['status'] == 'failed' and before['open_peers'] == before['open_grants'] == 0
    assert before['counts']['runtime_runs'] == before['counts']['runtime_attempts'] == 4
    assert before['counts']['runtime_inference_dispatches'] == 1
    issue = json.loads(before['run']['issue_json'])
    output = args.output.resolve()
    output.mkdir(mode=0o700)
    fixture = output / 'fixture.json'
    fixture.write_text(json.dumps({'project': PROJECT, 'task': TASK, 'run': RUN, 'name': 'Plan CSV en español', 'issue': issue}) + '\n')
    config = json.loads((host / 'runtime.json').read_text())
    static = Path(config['static_dir']) / 'index.html'
    result = {'status': 'running', 'scope': 'Original failed planning history; pairing and declared schema migration only, zero new owner work or model admissions.',
              'base_commit': 'd8ddcf8', 'started_at': started_at, 'closure_confirmed': False, 'continuation_start': before,
              'current_frontend_sha256': hashlib.sha256(static.read_bytes()).hexdigest()}
    process = log = None
    with socket.socket() as binding:
        binding.bind(('127.0.0.1', 0))
        port = binding.getsockname()[1]
    try:
        process, log = start(host, output, port, 1)
        result['after_start'] = observe(host)
        preserved(before, result['after_start'])
        keys = list((host / 'auth').glob('owner-*.key'))
        assert len(keys) == 1
        env = {**os.environ, 'RESEARCHER_E2E_ORIGIN': f'http://127.0.0.1:{port}',
               'RESEARCHER_E2E_OWNER_FILE': str(keys[0]), 'RESEARCHER_E2E_OUTPUT': str(output / 'browser'),
               'RESEARCHER_E2E_FIXTURE': str(fixture)}
        with (output / 'browser.log').open('x') as stream:
            browser = subprocess.run([str(args.node.resolve(strict=True)), 'tests/projects-original.e2e.mjs'], cwd=ROOT / 'frontend', env=env,
                                     stdout=stream, stderr=subprocess.STDOUT, check=False, timeout=150)
        result['browser_exit'] = browser.returncode
        assert browser.returncode == 0
        result['after_browser'] = observe(host)
        preserved(before, result['after_browser'])
        result['status'] = 'passed'
    except BaseException as error:
        result.update(status='failed', error_type=type(error).__name__)
        raise
    finally:
        try:
            if process is not None:
                result['service_exit'] = stop(process, log)
                result['closure_confirmed'] = True
            result['after'] = observe(host)
            preserved(before, result['after'])
        except BaseException as error:
            result.update(status='failed', error_type=type(error).__name__)
            raise
        finally:
            result['finished_at'] = datetime.now(timezone.utc).isoformat()
            result['seconds'] = round(time.monotonic() - clock, 3)
            (output / 'result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
            print(json.dumps({'status': result['status'], 'service_exit': result.get('service_exit')}), flush=True)


if __name__ == '__main__':
    main()
