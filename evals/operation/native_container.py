"""Exercise a fresh rootless native container with explicit assets and optional subscription.

The fixture owns one new cgroup subtree and synthetic installation. It retains
data on failure, sends at most one admission, and never adopts existing work.
"""

import argparse
import importlib.util
import json
import os
import socket
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx


def main():
    """Prepare, probe, admit once, restart and inspect one original container identity."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='localhost/researcher:native-host')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--host-assets', type=Path, required=True)
    parser.add_argument('--podman-command', type=Path)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    if os.getuid() != 1000:
        raise ValueError('This exercised image/user mapping requires host UID1000')
    prefix = json.loads(args.podman_command.read_text()) if args.podman_command else ['podman']
    supplied = json.loads(args.host_assets.read_text())
    parent = Path(supplied['cgroup_parent']).resolve(strict=True)
    if not parent.is_relative_to('/sys/fs/cgroup') or not {'memory', 'pids'} <= set((parent / 'cgroup.subtree_control').read_text().split()):
        raise ValueError('Select an already delegated cgroup parent with memory and pids')
    root = args.output.absolute()
    root.mkdir(mode=0o700)
    data, witness = root / 'data', root / 'witness'
    data.mkdir(mode=0o700)
    witness.mkdir(mode=0o700)
    group = parent / ('researcher-container-' + uuid4().hex)
    container = None
    receipt = {'status': 'running', 'image': args.image, 'admissions_sent': 0, 'service_exits': [], 'live_requested': args.live}
    spec = importlib.util.spec_from_file_location('host_smoke', Path(__file__).with_name('host_smoke.py'))
    host = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(host)

    def pod(*arguments, check=True):
        """Run a bounded command against the original container; never infer success from timeout."""
        result = subprocess.run(prefix + list(arguments), capture_output=True, text=True, timeout=120)
        if check and result.returncode:
            raise RuntimeError(f'Podman {arguments[0]} failed: {result.stderr}')
        return result

    def mount(source, destination, readonly=False):
        """Describe an explicit existing resource without mounting a broad host root or home."""
        return ['--mount', f'type=bind,source={Path(source).resolve(strict=True)},destination={destination}' + (',ro' if readonly else '')]

    def wait_ready(client):
        """Poll the same container and health endpoint, keeping an observation deadline bounded."""
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            state = json.loads(pod('inspect', container).stdout)[0]['State']
            if not state['Running']:
                raise RuntimeError(f'Original service exited before readiness: {state["ExitCode"]}')
            try:
                response = client.get('/api/health/ready', timeout=1)
                if response.status_code == 200 and response.json() == {'ready': True}:
                    return
            except httpx.TransportError:
                pass
            time.sleep(.1)
        raise TimeoutError('Original container did not become ready')

    def stop():
        """Observe original service shutdown without signalling unrelated container names."""
        pod('stop', '--time', '20', container)
        state = json.loads(pod('inspect', container).stdout)[0]['State']
        assert not state['Running'] and state['ExitCode'] == 143, state
        assert not list((data / 'installation/auth').iterdir())
        receipt['service_exits'].append(state['ExitCode'])

    try:
        group.mkdir(mode=0o700)
        (group / 'cgroup.subtree_control').write_text('+memory +pids')
        # Durable authority binds the observer PID namespace. A fresh private
        # controller namespace on restart must not be mistaken for that owner.
        common = ['--pull=never', '--userns=keep-id', '--cgroupns=host', '--pid=host',
                  '--security-opt', 'unmask=/proc/*',
                  '--cgroup-parent', '/' + str(group.relative_to('/sys/fs/cgroup')),
                  *mount(group, str(group)), *mount(data, '/data'), *mount(witness, '/witness'),
                  *mount(supplied['codex_binary'], '/opt/researcher-native/codex', True),
                  *mount(supplied['code_mode_host'], '/opt/researcher-native/codex-code-mode-host', True),
                  *mount(supplied['model_cache'], '/opt/researcher-models', True),
                  *mount(supplied['token_file'], '/run/researcher/subscription/auth.json', True)]
        policy = {k: supplied[k] for k in ('model', 'reasoning_effort', 'web_search', 'broker_limits', 'limits', 'project_turn_limit', 'project_token_limit') if k in supplied}
        policy.update(codex_binary='/opt/researcher-native/codex', code_mode_host='/opt/researcher-native/codex-code-mode-host',
                      ken_command='/opt/ken/bin/ken', model_cache='/opt/researcher-models',
                      token_file='/run/researcher/subscription/auth.json', cgroup_parent=str(group), static_dir='/app/frontend/dist')
        (data / 'assets.json').write_text(json.dumps(policy, indent=2) + '\n')
        (data / 'assets.json').chmod(0o600)
        initialized = pod('run', '--rm', '--network=none', *common, args.image,
                          'researcher-bootstrap', 'init-host', '--directory', '/data/installation',
                          '--witness-dir', '/witness/authority', '--assets', '/data/assets.json')
        receipt['initialization'] = json.loads(initialized.stdout)
        probe = pod('run', '--rm', '--network=none', *common, args.image,
                    'researcher-bootstrap', 'check-host', '--directory', '/data/installation', '--probe')
        receipt['kernel_probe'] = json.loads(probe.stdout)['kernel_probe']
        pod('run', '--rm', '--network=none', *common, args.image,
            'bwrap', '--unshare-all', '--cap-drop', 'ALL', '--ro-bind', '/usr', '/usr',
            '--symlink', 'usr/lib', '/lib', '--symlink', 'usr/lib64', '/lib64',
            '--proc', '/proc', '--dev', '/dev', '--', '/usr/bin/true')
        receipt['nested_namespace_probe'] = True
        installation = data / 'installation'
        host.seed(installation, stored_root=Path('/data/installation'))
        with socket.socket() as binding:
            binding.bind(('127.0.0.1', 0))
            port = binding.getsockname()[1]
        started = pod('run', '-d', '--network=host', *common, args.image,
                      'researcher-start', '--installation', '/data/installation', '--port', str(port))
        container = started.stdout.strip()
        receipt['container_id'] = container
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=15) as client:
            wait_ready(client)
            assert client.get('/').status_code == 200
            assert client.get('/api/projects').status_code == 401
            host.pair(client, installation)
            if args.live:
                host.admit_live(client, installation, receipt)
            else:
                receipt['before_restart'] = host.snapshot(installation / 'source.db')
            stop()
            pod('start', container)
            wait_ready(client)
            assert client.get('/api/projects').status_code == 401
            host.pair(client, installation)
            receipt['after_restart'] = host.snapshot(installation / 'source.db')
            assert receipt['after_restart'] == receipt['before_restart']
            stop()
        receipt['status'] = 'passed'
    except BaseException as error:
        receipt.update(status='failed', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        if container is not None:
            pod('stop', '--time', '20', container, check=False)
            logs = pod('logs', container, check=False)
            (root / 'service.log').write_text(logs.stdout + logs.stderr)
            pod('rm', container, check=False)
        if group.exists():
            try:
                group.rmdir()
                receipt['owned_cgroup_removed'] = True
            except OSError:
                receipt['owned_cgroup_removed'] = False
        (root / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'status': receipt['status'], 'admissions_sent': receipt['admissions_sent'], 'receipt': str(root / 'result.json')}))


if __name__ == '__main__':
    main()
