"""Reuse installed TLS/Git fixtures for bounded browser source setup without any user server or model credential."""

import hashlib
import json
import sqlite3
import subprocess
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def git(path, *arguments):
    """Inspect or seed only a fixture-owned local repository, with deterministic synthetic commit identity."""
    return subprocess.check_output(['/usr/bin/git', '-C', str(path), '-c', 'user.name=Fixture',
                                    '-c', 'user.email=fixture@localhost', '-c', 'core.hooksPath=/dev/null',
                                    *arguments], text=True, stderr=subprocess.DEVNULL).strip()


def seed(path, text):
    """Create a real small Git history and a separate untracked owner note for preservation checks."""
    path.mkdir()
    git(path, 'init', '-b', 'main')
    (path / 'README.md').write_text('# Exportador de observaciones\n\n' + text + '\n')
    (path / 'src').mkdir()
    (path / 'src/catalog.py').write_text('"""Preserve the original observation order."""\ndef observations(records):\n    """Return the supplied records without sorting."""\n    return list(records)\n')
    git(path, 'add', '.')
    git(path, 'commit', '-m', 'Fixture source')
    git(path, 'branch', 'experimental')
    git(path, 'remote', 'add', 'origin', 'https://example.invalid/preserved.git')
    (path / 'nota-local.txt').write_text('Esta nota local debe conservarse.\n')
    return {'path': str(path), 'head': git(path, 'rev-parse', 'HEAD'),
            'config_sha256': hashlib.sha256((path / '.git/config').read_bytes()).hexdigest(),
            'note': (path / 'nota-local.txt').read_text()}


def verify_repository_files(output, host, fixture):
    """Verify real original/repaired files and credential confinement after the service has closed, without replaying Git effects."""
    sources = host / 'sources'
    for original in (fixture['alpha'], fixture['beta']):
        path = Path(original['path'])
        assert git(path, 'rev-parse', 'HEAD') == original['head']
        assert hashlib.sha256((path / '.git/config').read_bytes()).hexdigest() == original['config_sha256']
        assert (path / 'nota-local.txt').read_text() == original['note']
    config = json.loads((host / 'runtime.json').read_text())
    token = Path(config['remote_publication']['token_file']).read_text().strip()
    for name in ('copia', 'interrumpida'):
        assert git(sources / name, 'rev-parse', 'HEAD') == fixture['remote_head']
        assert git(sources / name, 'remote', 'get-url', 'origin') == fixture['remote_origin'] + '/owner/repo.git'
        assert token not in (sources / name / '.git/config').read_text()
    assert (sources / 'interrumpida/nota-local.txt').read_text() == 'Conservar esta nota durante la reparación.\n'
    for name in ('nueva', 'recuperable'):
        assert git(sources / name, 'rev-list', '--count', 'HEAD') == '1'
        assert git(sources / name, 'remote') == ''
    assert git(output / 'tls-remote/owner/repo.git', 'rev-parse', 'main') == fixture['remote_head']
    assert not (sources / 'sin-git/.git').exists()
    with sqlite3.connect(host / 'source.db') as db:
        assert all(token not in (row[0] or '') for row in db.execute('SELECT metadata_json FROM projects'))
    return {'original_sources': 2, 'exact_cloned_heads': 2, 'single_initial_commits': 2,
            'repaired_note_preserved': True, 'remote_seed_head_unchanged': True, 'credentials_absent_from_git_and_operations': True}


@contextmanager
def repository_fixture(output, host):
    """Own real TLS smart-Git, a controlled Forgejo REST contract and fixed test fault controls through final shutdown."""
    from backend.tests.runtime.test_owned_remote_transport import tls_remote
    from backend.tests.runtime.test_remote_source import remote_source

    lifecycle = tls_remote.__wrapped__(output, None)
    remote = next(lifecycle)
    remote_source.__wrapped__(remote)
    sources = host / 'sources'
    alpha = seed(sources / 'original', 'Conserva el orden original al exportar.')
    beta = seed(sources / 'independiente', 'Material de otro proyecto; no debe mezclarse.')
    git(Path(alpha['path']), 'push', str(remote.repo), 'main')
    remote_head = git(remote.repo, 'rev-parse', 'main')
    raw = sources / 'sin-git'
    raw.mkdir()
    (raw / 'nota.txt').write_text('Carpeta registrada sin Git; no prueba una revisión.\n')
    config_path = host / 'runtime.json'
    config = json.loads(config_path.read_text())
    config['ca_bundle'] = str(remote.cert)
    config['remote_publication'] = {'api_base': remote.origin + '/api/v1', 'username': 'fixture-user',
                                  'token_file': str(remote.token_file), 'ca_bundle': str(remote.cert)}
    config_path.write_text(json.dumps(config, indent=2) + '\n')

    class Controls(BaseHTTPRequestHandler):
        """Expose only fixed fixture actions; never accept arbitrary paths, SQL or commands from the browser."""

        def log_message(self, *_arguments):
            """Suppress request logs; all credentials are synthetic but remain outside evidence."""

        def do_POST(self):
            """Apply one explicit test control and return bounded independent fixture observations."""
            action = self.path.removeprefix('/')
            if action == 'hold-clone':
                remote.entered.clear(); remote.finished.clear(); remote.release.clear(); remote.hold_clone = True
            elif action == 'release-clone':
                remote.hold_clone = False; remote.release.set()
            elif action == 'drop-remote-reply':
                remote.drop_create = True
            elif action == 'allow-remote-reply':
                remote.drop_create = False
            elif action in ('fail-registration', 'allow-registration'):
                with sqlite3.connect(host / 'source.db') as db:
                    db.execute('DROP TRIGGER IF EXISTS acceptance_source_registration')
                    if action == 'fail-registration':
                        db.execute("CREATE TRIGGER acceptance_source_registration BEFORE INSERT ON repositories WHEN NEW.name='recuperable' BEGIN SELECT RAISE(ABORT,'synthetic source registration failure'); END")
            elif action == 'note-partial':
                partial = sources / 'interrumpida'
                assert partial.is_dir() and not partial.is_symlink()
                (partial / 'nota-local.txt').write_text('Conservar esta nota durante la reparación.\n')
            elif action != 'state':
                self.send_error(404); return
            value = {'clone_entered': remote.entered.is_set(), 'git_writes': remote.git_writes,
                     'remote_head': git(remote.repo, 'rev-parse', 'main'),
                     'create_posts': [{'path': path, 'name': body['name'], 'private': body['private']} for path, body in remote.create_posts]}
            data = json.dumps(value).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Controls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    fixture = {'root': str(sources), 'alpha': alpha, 'beta': beta, 'raw': str(raw),
               'remote_origin': remote.origin, 'remote_head': remote_head,
               'control': 'http://127.0.0.1:' + str(server.server_port)}
    try:
        yield fixture
    finally:
        remote.release.set(); server.shutdown(); server.server_close(); thread.join(3)
        with sqlite3.connect(host / 'source.db') as db:
            db.execute('DROP TRIGGER IF EXISTS acceptance_source_registration')
        lifecycle.close()
        assert git(remote.repo, 'rev-parse', 'main') == remote_head and remote.git_writes == 0
        assert git(Path(alpha['path']), 'rev-parse', 'HEAD') == alpha['head']
        assert hashlib.sha256((Path(alpha['path']) / '.git/config').read_bytes()).hexdigest() == alpha['config_sha256']
        assert (Path(alpha['path']) / 'nota-local.txt').read_text() == alpha['note']
        if (output / 'browser/evidence.json').exists() and json.loads((output / 'browser/evidence.json').read_text()).get('status') == 'passed':
            verified = verify_repository_files(output, host, fixture)
            (output / 'file-verification.json').write_text(json.dumps(verified, indent=2) + '\n')
