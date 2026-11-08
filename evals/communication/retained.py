"""Capture retained real outcomes and recoverable read failures without admitting model work.

This reader accepts only closed synthetic evaluation installations. Original rows
and fields are compared across any declared product schema upgrade; the
browser permits reads and local pairing, never product mutations.
"""

import argparse
import hashlib
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def observe(host, columns=None):
    """Hash original logical fields and rows while recording added tables separately."""
    with sqlite3.connect((host / 'source.db').as_uri() + '?mode=ro', uri=True) as db:
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        result = {}
        for name in tables:
            quoted = '"' + name.replace('"', '""') + '"'
            selected = columns[name]['columns'] if columns and name in columns else [r[1] for r in db.execute('PRAGMA table_info(' + quoted + ')')]
            fields = ','.join('"' + c.replace('"', '""') + '"' for c in selected)
            rows = db.execute('SELECT ' + fields + ' FROM ' + quoted).fetchall()
            result[name] = {'columns': selected, 'count': len(rows),
                            'hash': hashlib.sha256(json.dumps(sorted(rows, key=str), default=str, sort_keys=True).encode()).hexdigest()}
        return result


def run(args):
    """Own the installed server/browser handles and preserve the exact failure or success of this read-only journey."""
    import backend

    if not Path(backend.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError('Use installed product Python with -I')
    sys.path.insert(0, str(ROOT))
    from evals.operation.host_smoke import start, stop

    host = args.host.resolve(strict=True)
    output = args.output.resolve()
    allowed = ROOT / '.researcher/evaluations'
    if not host.is_relative_to(allowed) or not output.is_relative_to(allowed):
        raise ValueError('Use only private synthetic evaluation installations and output')
    with sqlite3.connect((host / 'source.db').as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("SELECT COUNT(*) FROM runtime_peers WHERE state!='closed'").fetchone()[0] or db.execute('SELECT COUNT(*) FROM tool_grants WHERE revoked_at IS NULL').fetchone()[0]:
            raise ValueError('Inspect original live handles before opening a retained reader')
        if db.execute("SELECT COUNT(*) FROM runtime_runs WHERE status IN ('queued','running','cancelling','reconciling')").fetchone()[0]:
            raise ValueError('This reader accepts closed attempts only')
        title, task_type = db.execute('SELECT title,type FROM tasks WHERE id=1001 AND project_id=101').fetchone()
        if task_type != ('code' if args.kind == 'code_review' else 'plan'):
            raise ValueError('Wrong retained communication case')
        run_id = db.execute('SELECT id FROM runtime_runs WHERE project_id=101 AND task_id=1001 ORDER BY created_at DESC LIMIT 1').fetchone()[0]
    output.mkdir(mode=0o700)
    fixture = {'title': title, 'kind': args.kind, 'run': run_id if args.kind == 'partial' else None,
               'proposal': 'Exportación CSV del registro local de observaciones'}
    (output / 'fixture.json').write_text(json.dumps(fixture) + '\n')
    started = time.monotonic()
    evidence = {'status': 'running', 'kind': args.kind, 'started_at': datetime.now(timezone.utc).isoformat(),
                'new_model_admissions': 0, 'before': observe(host)}
    process = log = None
    with socket.socket() as binding:
        binding.bind(('127.0.0.1', 0))
        port = binding.getsockname()[1]
    try:
        process, log = start(host, output, port, 1)
        keys = list((host / 'auth').glob('owner-*.key'))
        if len(keys) != 1:
            raise RuntimeError('Expected one original pairing file')
        env = {**os.environ, 'RESEARCHER_E2E_ORIGIN': f'http://127.0.0.1:{port}',
               'RESEARCHER_E2E_OUTPUT': str(output / 'browser'), 'RESEARCHER_E2E_OWNER_FILE': str(keys[0]),
               'RESEARCHER_E2E_FIXTURE': str(output / 'fixture.json')}
        with (output / 'browser.log').open('x') as stream:
            browser = subprocess.run([str(args.node.resolve(strict=True)), 'tests/communication-baseline.mjs'],
                                     cwd=ROOT / 'frontend', env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=180)
        evidence['browser_exit'] = browser.returncode
        evidence['after'] = observe(host, evidence['before'])
        evidence['changed_original_tables'] = [n for n, row in evidence['before'].items()
                                                if n != 'schema_migrations' and evidence['after'].get(n) != row]
        evidence['new_tables'] = {n: row['count'] for n, row in evidence['after'].items() if n not in evidence['before']}
        if browser.returncode or evidence['changed_original_tables']:
            raise RuntimeError('Browser failed or original data changed; inspect retained evidence')
        evidence['status'] = 'passed'
    except BaseException as error:
        evidence.update(status='failed', error_type=type(error).__name__)
        raise
    finally:
        if process is not None:
            evidence['service_exit'] = stop(process, log)
            evidence['owned_backend_terminal'] = True
        evidence['seconds'] = round(time.monotonic() - started, 3)
        (output / 'result.json').write_text(json.dumps(evidence, indent=2) + '\n')
        print({k: v for k, v in evidence.items() if k not in ('before', 'after')})


def main():
    """Select one known retained flow, never a production database or an automatic model retry."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--kind', choices=['code_review', 'partial'], required=True)
    parser.add_argument('--node', type=Path, required=True)
    run(parser.parse_args())


if __name__ == '__main__':
    main()
