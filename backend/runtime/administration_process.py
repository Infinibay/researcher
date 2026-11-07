"""Own one inference-free administrative process and its resource lifetime.

The public CLI keeps a small parent outside the operation's address-space and
CPU ceilings. Data operations run in one trusted child; partial files are never
deleted or retried. These limits do not constitute a filesystem sandbox or a
host-wide disk/memory quota.
"""

import ctypes
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import sysconfig

WORKER = Path(__file__).resolve()
COMMANDS = frozenset({'backup-host', 'verify-backup', 'restore-host', 'stage-legacy-host'})
MEMORY_BYTES = 1024**3


def apply_limits(options):
    """Arm parent-death and irreversible per-process fuses before importing administrative dependencies."""
    if sys.platform != 'linux':
        raise RuntimeError('Bounded administration requires Linux; no unrestricted fallback')
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'Administrative parent-death guard failed')
    if os.getppid() != options['parent_pid']:
        raise RuntimeError('Administrative parent changed before admission')
    operation = options['operation']
    for name, limit in (
        (resource.RLIMIT_CORE, 0),
        (resource.RLIMIT_AS, MEMORY_BYTES),
        (resource.RLIMIT_CPU, operation['timeout']),
        (resource.RLIMIT_FSIZE, operation['max_bytes']),
        (resource.RLIMIT_NOFILE, 512),
        (resource.RLIMIT_NPROC, 0),
    ):
        current = resource.getrlimit(name)[1]
        value = limit if current == resource.RLIM_INFINITY else min(limit, current)
        resource.setrlimit(name, (value, value))
    # The parent owns the normal deadline. This remains a kernel fuse if it
    # stays alive but stops making progress; parent death is handled above.
    signal.alarm(operation['timeout'] + 1)


def observed_limits():
    """Report actual child ceilings without claiming aggregate limits for other processes or storage."""
    return {
        'address_space_bytes': resource.getrlimit(resource.RLIMIT_AS)[1],
        'cpu_seconds': resource.getrlimit(resource.RLIMIT_CPU)[1],
        'per_file_bytes': resource.getrlimit(resource.RLIMIT_FSIZE)[1],
        'open_files': resource.getrlimit(resource.RLIMIT_NOFILE)[1],
        'aggregate_disk_quota': False,
    }


def run_administration(operation):
    """Run an allowlisted data operation, forwarding output without accumulating it, then reap its original child."""
    if operation.get('command') not in COMMANDS:
        raise ValueError('Unknown bounded administration command')
    if any(type(operation.get(key)) is not int or operation[key] <= 0
           for key in ('max_bytes', 'max_files', 'timeout')):
        raise ValueError('Snapshot limits must be positive integers')
    operation = dict(operation)
    for key in ('directory', 'backup', 'destination', 'database', 'storage_manifest'):
        if key in operation:
            operation[key] = str(Path(operation[key]).absolute())
    options = {'operation': operation, 'parent_pid': os.getpid(),
               'package_root': str(Path(__file__).resolve().parents[2]),
               'dependencies': sysconfig.get_path('purelib')}
    child = subprocess.Popen(
        [sys.executable, '-I', '-S', str(WORKER), json.dumps(options)],
        stdin=subprocess.DEVNULL, close_fds=True, cwd='/',
        env={'PATH': os.defpath, 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1',
             'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'},
    )
    try:
        try:
            status = child.wait(timeout=operation['timeout'])
        except subprocess.TimeoutExpired:
            print('Operation exceeded its time budget. Partial paths remain for inspection; '
                  'no automatic retry or repair was attempted.', file=sys.stderr)
            return 124
        except KeyboardInterrupt:
            print('Operation interrupted. Keep partial paths for inspection.', file=sys.stderr)
            return 130
        if status < 0:
            print(f'Administrative child ended by signal {-status}. Inspect partial paths and '
                  'completion receipts before deciding whether to start a new operation.', file=sys.stderr)
            return 128 - status
        return status
    finally:
        if child.poll() is None:
            child.kill()
        # A timeout in observation is not proof of closure. Do not return or
        # offer another operation until the original owned child is reaped.
        child.wait()


def worker_main():
    """Bootstrap the fixed administrative CLI in its constrained interpreter; never accept arbitrary Python code."""
    options = json.loads(sys.argv[1])
    apply_limits(options)
    sys.path[:0] = [options['package_root'], options['dependencies']]
    from backend.cli.bootstrap import main

    operation = options['operation']
    arguments = [operation['command']]
    for key, value in operation.items():
        if key == 'command' or value is False:
            continue
        arguments.append('--' + key.replace('_', '-'))
        if value is not True:
            arguments.append(str(value))
    return main(arguments, _in_worker=True)


if __name__ == '__main__':
    raise SystemExit(worker_main())
