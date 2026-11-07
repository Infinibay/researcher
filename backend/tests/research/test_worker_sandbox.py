"""Exercise real kernel denials and shared document/semantic worker admission."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from backend.research.parser_process import PDFParser
from backend.research.models import ResearchForbidden, SourceUnavailable
from backend.tests.research.pdf_fixtures import pdf_bytes
from backend.tests.research.test_parser_process import worker_fault


def test_parser_dependency_cannot_read_host_secret_write_or_open_network(monkeypatch, tmp_path):
    """A compromised parser runs after mandatory Landlock/seccomp, even though its host UID can read the secret."""
    secret = tmp_path/'private-token'
    secret.write_text('synthetic-secret')
    result = tmp_path/'unexpected-directory'
    body = '''
            import socket
            outcomes = {}
            for key, action in {
                'read_private': lambda: open(SECRET).read(),
                'create_directory': lambda: os.mkdir(DESTINATION),
                'chmod_private': lambda: os.chmod(SECRET, 0o777),
                'socket': lambda: socket.socket(),
                'fork': lambda: os.fork(),
                'exec': lambda: os.execv('/bin/true', ['/bin/true']),
            }.items():
                try:
                    action()
                except OSError as error:
                    outcomes[key] = error.errno
                else:
                    outcomes[key] = 'unexpectedly_allowed'
            return (json.dumps(outcomes), {})'''
    worker_fault(monkeypatch, tmp_path, body.replace('SECRET',repr(str(secret))).replace('DESTINATION',repr(str(result))))
    text, provenance = PDFParser().read(pdf_bytes('probe'))
    outcomes = json.loads(text)
    assert outcomes == {'read_private': 13, 'create_directory': 13, 'chmod_private': 1,
                        'socket': 1, 'fork': 1, 'exec': 1}
    assert secret.read_text() == 'synthetic-secret'
    assert not result.exists()
    assert provenance['execution']['sandbox']['filesystem'] == 'selected_public_reads_no_writes'


def test_unavailable_sandbox_never_falls_back_to_parser_execution(monkeypatch, tmp_path):
    """An unsupported mandatory restriction terminates bootstrap instead of parsing without it."""
    import backend.research.parser_process as module

    worker = tmp_path/'unavailable.py'
    worker.write_text('''import json, sys
options=json.loads(sys.argv[1]);sys.path.insert(0,options['package_root'])
import backend.research.worker_sandbox as sandbox
def unavailable():
    raise RuntimeError('unsupported fixture kernel')
sandbox.requirements = unavailable
from backend.research.worker_limits import apply_limits
apply_limits(options)
print(json.dumps({'ok':True,'content':'unrestricted fallback','provenance':{}}))
''')
    monkeypatch.setattr(module, 'WORKER', worker)
    with pytest.raises(SourceUnavailable, match='terminated'):
        PDFParser().read(pdf_bytes('must not parse'))


def test_all_worker_kinds_share_capacity_until_original_child_closes(monkeypatch, tmp_path):
    """A busy document worker blocks even another transport label; cancellation releases the same slot."""
    from backend.research.parser_process import ParserLimits
    from backend.research.worker_transport import exchange
    from backend.runtime.live_grants import LiveGrants

    marker = worker_fault(monkeypatch, tmp_path, 'import time; time.sleep(30)')
    gate = LiveGrants(); gate.activate('worker')
    parser = PDFParser(owner=gate, grant_id='worker', limits=ParserLimits(wall_seconds=5))
    with ThreadPoolExecutor(1) as pool:
        pending = pool.submit(parser.read, pdf_bytes('input'))
        deadline = time.monotonic()+3
        while not marker.exists() and time.monotonic()<deadline:
            time.sleep(.01)
        assert marker.exists()
        with pytest.raises(SourceUnavailable, match='ocupado'):
            exchange(b'', worker=tmp_path/'must-not-start.py', options={'wall_seconds':1},
                     limits=ParserLimits(), cancelled=Event(), label='Semantic')
        gate.withdraw('worker')
        with pytest.raises(ResearchForbidden):
            pending.result(timeout=3)
        gate.wait_closed('worker', timeout=1)
    # A launch failure after physical closure proves the slot is available again.
    with pytest.raises(SourceUnavailable, match='terminated'):
        exchange(b'', worker=tmp_path/'absent.py', options={'wall_seconds':1},
                 limits=ParserLimits(), cancelled=Event(), label='Semantic')


def test_busy_processing_is_not_an_invalid_document_http_error():
    """Expose saturation as429 with its useful explanation, preserving document validity as unknown."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.routes.research import install_research_errors
    from backend.research.models import WorkerBusy

    app = FastAPI()
    install_research_errors(app)

    @app.get('/busy')
    def busy():
        """Represent the shared worker admission result without starting any parser."""
        raise WorkerBusy('El procesamiento está ocupado; no se inició otro proceso.')

    response = TestClient(app).get('/busy')
    assert response.status_code == 429
    assert response.json()['code'] == 'processing_busy'
    assert 'ocupado' in response.json()['detail']
