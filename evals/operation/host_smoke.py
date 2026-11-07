"""Exercise a fresh prepared host through installed CLI/HTTP, optionally one live turn.

Only empty synthetic installations are accepted. Admission is sent once; failures
retain the original installation and receipt instead of replaying uncertain work.
"""

import argparse
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path
from uuid import uuid4

import httpx


def snapshot(database):
    """Read bounded outcome metadata without retaining model text or credentials."""
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
        return {'runs': db.execute('SELECT id,status FROM runtime_runs').fetchall(),
                'dispatches': db.execute('SELECT model,status,native_status FROM runtime_inference_dispatches').fetchall(),
                'reports': db.execute('SELECT artifact_id,status FROM research_reports').fetchall(),
                'findings': db.execute('SELECT id,status FROM findings').fetchall(),
                'peers': db.execute('SELECT kind,state FROM runtime_peers').fetchall(),
                'integrity': db.execute('PRAGMA integrity_check').fetchone()[0]}


def start(root, output, port, ordinal):
    """Start the installed supervisor and wait for its actual HTTP readiness."""
    log = (output / f'service-{ordinal}.log').open('w')
    process = subprocess.Popen([sys.executable, '-I', '-m', 'backend.cli.launcher', '--installation', str(root), '--port', str(port)],
                               cwd=root / 'service', stdout=log, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 30
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=1) as client:
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f'Installed service exited with {process.returncode}; inspect its private log')
                try:
                    ready = client.get('/api/health/ready')
                    if ready.status_code == 200 and ready.json() == {'ready': True}:
                        return process, log
                except httpx.TransportError:
                    pass
                time.sleep(.1)
        raise TimeoutError('Installed service did not become ready')
    except BaseException:
        stop(process, log)
        raise


def stop(process, log):
    """Observe closure of the original supervisor handle without PID-file recovery."""
    try:
        if process.poll() is None:
            process.terminate()
        return process.wait(timeout=25)
    finally:
        log.close()


def pair(client, root):
    """Pair with this synthetic service without recording the secret or session."""
    keys = list((root / 'auth').glob('owner-*.key'))
    if len(keys) != 1:
        raise RuntimeError('Expected one pairing file for this synthetic service')
    response = client.post('/api/session', json={'code': keys[0].read_text().strip()}, headers={'X-Researcher-Client': 'web'})
    response.raise_for_status()
    client.headers['X-Researcher-CSRF'] = response.json()['csrf_token']
    client.headers['X-Researcher-Endpoint'] = response.json()['endpoint_id']


def seed(root, *, stored_root=None):
    """Populate an empty synthetic installation, optionally storing its container-visible paths."""
    visible = root if stored_root is None else Path(stored_root)
    database = root / 'source.db'
    with closing(sqlite3.connect(database)) as db, db:
        if any(db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in ('projects', 'runtime_runs')):
            raise ValueError('Host smoke requires an empty synthetic installation; never reuse operator data')
        workspace = root / 'sources' / 'host-smoke'
        workspace.mkdir(mode=0o700)
        (workspace / 'units.py').write_text('"""Synthetic unit total for host installation verification."""\n\ndef total_units():\n    """Return the total of two observed synthetic batches."""\n    return 137 + 63\n')
        folder = root / 'uploads' / '101/uploads'
        folder.mkdir(parents=True, mode=0o700)
        attachment = folder / 'units.txt'
        attachment.write_text('Synthetic batches contain 137 units and 63 units. Their total is 200 units.\n')
        db.execute("INSERT INTO projects(id,name) VALUES(101,'Synthetic prepared-host smoke')")
        db.execute("INSERT INTO tasks(id,project_id,type,title,status) VALUES(1001,101,'research','Explain the synthetic total with evidence','in_progress')")
        db.execute("INSERT INTO repositories(id,project_id,name,local_path) VALUES(11,101,'host-smoke',?)", (str(visible / "sources" / "host-smoke"),))
        db.execute("INSERT INTO reference_files(id,project_id,file_name,file_path,file_size,file_type) VALUES(7,101,'units.txt',?,?,'text/plain')", (str(visible / "uploads" / "101/uploads/units.txt"), attachment.stat().st_size))


def admit_live(client, root, result, *, checkpoint=None):
    """Send one bounded admission, optionally persisting its original identity before any HTTP attempt."""
    from backend.runtime.sqlite_runs import SQLiteRunStore

    version = SQLiteRunStore(root / 'source.db').context_snapshot(101, 1001)['context_version']
    key = 'host-installation-' + uuid4().hex
    request = (f'Ensayo sintético autorizado. Usa ken_find con consulta en inglés para localizar total_units y ken_read para leer units.py. '
               f'Lista adjuntos y captura la referencia7 con operation_key {key}-capture; lee la fuente capturada. '
               f'Usa researcher_python una vez con operation_key {key}-calc para calcular 137+63; consulta el job hasta confirmar salida200 y exit_code0. '
               f'Registra UN finding provisional, con clave {key}-finding y cita exacta de la fuente. Guarda UN informe draft con clave {key}-report enlazado al finding y léelo. '
               'Explica el resultado brevemente en español, con un ejemplo simple, separando inspección de código y cálculo ejecutado. '
               'No edites archivos, no instales paquetes, no publiques ni aceptes resultados. Un único turno; termina indicando informe y límites de la prueba.')
    result['operation_key'] = key
    result['admissions_sent'] = 1
    if checkpoint is not None:
        checkpoint(result)
    response = client.post('/api/projects/101/tasks/1001/runs', json={'operation_key': key, 'context_version': version, 'repository_id': 11, 'request': request})
    response.raise_for_status()
    run_id = response.json()['run_id']
    result['run_id'] = run_id
    if checkpoint is not None:
        checkpoint(result)
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        response = client.get(f'/api/projects/101/runs/{run_id}')
        response.raise_for_status()
        view = response.json()
        if view['status'] in {'needs_review', 'failed', 'cancelled', 'reconciling'}:
            break
        time.sleep(.3)
    result['before_restart'] = snapshot(root / 'source.db')
    assert view['status'] == 'needs_review', view['status']
    assert len(result['before_restart']['reports']) == 1
    assert len(result['before_restart']['findings']) == 1
    assert len(result['before_restart']['dispatches']) == 1


def main():
    """Run two observed starts and at most one explicit subscription admission."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installation', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--live', action='store_true', help='Authorize exactly one bounded synthetic subscription turn')
    args = parser.parse_args()
    root = args.installation.resolve(strict=True)
    output = args.output.absolute()
    output.mkdir(mode=0o700)
    seed(root)
    with socket.socket() as binding:
        binding.bind(('127.0.0.1', 0))
        port = binding.getsockname()[1]
    result = {'status': 'running', 'admissions_sent': 0, 'service_exits': [], 'live_requested': args.live}
    process = log = None
    try:
        process, log = start(root, output, port, 1)
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=15) as client:
            assert client.get('/').status_code == 200
            pair(client, root)
            if args.live:
                admit_live(client, root, result)
            else:
                result['before_restart'] = snapshot(root / 'source.db')
        result['service_exits'].append(stop(process, log))
        process = log = None
        process, log = start(root, output, port, 2)
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=15) as client:
            pair(client, root)
            result['after_restart'] = snapshot(root / 'source.db')
            assert result['after_restart'] == result['before_restart']
        result['status'] = 'passed'
    except BaseException as error:
        result.update(status='failed', error_type=type(error).__name__)
        result['observed'] = snapshot(root / 'source.db')
        raise
    finally:
        try:
            if process is not None:
                result['service_exits'].append(stop(process, log))
        finally:
            (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'admissions_sent': result['admissions_sent'], 'receipt': str(output / 'result.json')}))


if __name__ == '__main__':
    main()
