"""Audit real reader announcements on a retained synthetic installed workspace, never operator data."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import uuid

from host_smoke import start, stop
from web_workspace import observe

ROOT = Path(__file__).resolve().parents[2]


def main():
    """Verify fixture provenance, own the supervisor/container and compare durable business/inference records after closure."""
    import backend
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, required=True, help='Retained successful no-model web_workspace evaluation directory')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--chromium', type=Path, required=True, help='Full Chromium executable directory, mounted read-only')
    parser.add_argument('--container-spec', type=Path, help='Trusted JSON with argv and selected tool-local env; otherwise uses podman')
    parser.add_argument('--image', default='localhost/researcher:reader-evaluation')
    args = parser.parse_args()
    if not Path(backend.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError('Run with the noneditable installed product Python')
    fixture = args.fixture.absolute()
    previous = json.loads((fixture / 'result.json').read_text())
    assert previous['status'] == 'passed' and previous['journey'] in ('workspace', 'navigation', 'native_zoom') and previous['model_turns'] == 0
    account = json.loads((fixture / 'synthetic-account.json').read_text())
    assert account['tokens']['account_id'] == 'synthetic-web-evaluation'
    host = fixture / 'host'
    before = observe(host / 'source.db')
    assert before['runs'] == before['dispatches'] == before['native_starts'] == 0 and before['integrity'] == 'ok'
    assert {p['name'] for p in before['projects']} == {'Atlas comprobable', 'Contexto separado'}
    correction, = before['corrections']
    output = args.output.absolute()
    output.mkdir(mode=0o700)
    browser_output = output / 'browser'
    browser_output.mkdir(mode=0o700)
    spec = json.loads(args.container_spec.read_text()) if args.container_spec else {'argv': ['podman'], 'env': {}}
    assert isinstance(spec['argv'], list) and spec['argv'] and all(isinstance(part, str) for part in spec['argv'])
    assert set(spec.get('env', {})) <= {'PATH', 'LD_LIBRARY_PATH', 'CONTAINERS_CONF', 'XDG_CONFIG_HOME'}
    environment = {**os.environ, **spec.get('env', {})}
    name = 'researcher-reader-' + uuid.uuid4().hex
    with socket.socket() as binding:
        binding.bind(('127.0.0.1', 0))
        port = binding.getsockname()[1]
    result = {'status': 'running', 'scope': 'Installed synthetic owner workspace, real reader; no physical listening or human acceptance', 'storage_before': before, 'model_turns': 0}
    process = log = None
    container = None
    try:
        process, log = start(host, output, port, 1)
        owner, = (host / 'auth').glob('owner-*.key')
        (browser_output / 'inputs.json').write_text(json.dumps({'origin': f'http://127.0.0.1:{port}', 'projectId': correction['project_id'], 'taskId': correction['task_id'], 'correction': correction['statement']}) + '\n')
        mounts = [(ROOT / 'frontend/node_modules', '/opt/frontend/node_modules', True),
                  (ROOT / 'frontend/tests', '/opt/frontend/tests', True),
                  (ROOT / 'evals/operation/screen_reader_container.py', '/opt/audit/container.py', True),
                  (args.chromium.absolute(), '/opt/chromium', True),
                  (owner, '/run/reader/owner.key', True), (browser_output, '/out', False)]
        command = spec['argv'] + ['run', '--rm', '--name', name, '--network=host', '--shm-size=512m']
        for source, destination, readonly in mounts:
            command += ['--mount', f'type=bind,source={source},destination={destination}' + (',ro' if readonly else '')]
        command += [args.image, 'dbus-run-session', '--', 'python3', '/opt/audit/container.py']
        with (output / 'container.log').open('x') as stream:
            container = subprocess.Popen(command, env=environment, stdout=stream, stderr=subprocess.STDOUT)
            result['container_exit'] = container.wait(timeout=300)
        result['reader'] = json.loads((browser_output / 'reader-result.json').read_text())
        result['browser'] = json.loads((browser_output / 'browser-result.json').read_text())
        assert result['container_exit'] == 0 and result['reader']['status'] == result['browser']['status'] == 'passed'
        assert len(result['browser']['routes']) == 12 and result['browser']['content']
        result['status'] = 'passed'
    except BaseException as error:
        result.update(status='failed', error=str(error))
        raise
    finally:
        # Cleanup may fail independently; that must not prevent closing the original installed supervisor.
        try:
            cleanup = subprocess.run(spec['argv'] + ['rm', '--force', '--ignore', name], env=environment, capture_output=True, text=True, timeout=30)
            result['container_cleanup_exit'] = cleanup.returncode
            if container is not None and container.poll() is None:
                result['container_exit_after_cleanup'] = container.wait(timeout=15)
        except BaseException as error:
            result.update(status='failed', cleanup_error=str(error))
        finally:
            if process is not None:
                result['service_exit'] = stop(process, log)
            after = observe(host / 'source.db')
            result['storage_after_close'] = after
            result['business_and_inference_unchanged'] = before == after
            invariant = result.get('container_cleanup_exit') == 0 and before == after and after['runs'] == after['dispatches'] == after['native_starts'] == 0 and after['integrity'] == 'ok'
            if not invariant:
                result.update(status='failed', invariant_error='Container closure or durable storage observation failed')
            (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps({'status': result['status'], 'receipt': str(output / 'result.json')}), flush=True)
            assert invariant



if __name__ == '__main__':
    main()
