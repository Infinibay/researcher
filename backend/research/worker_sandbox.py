"""Irreversible filesystem and syscall restrictions for fixed single-process workers.

Only selected public interpreter/package files can be read. Filesystem writes,
networking, new processes/threads, execution and cross-process controls are denied.
This is not a namespace: Landlock does not conceal all filesystem metadata.
"""

import ctypes
import errno
import os
from pathlib import Path
import struct
import sys
import platform


class _Ruleset(ctypes.Structure):
    """ABI-stable Landlock filesystem mask; require truncate protection from ABI3."""

    _fields_ = [('handled_access_fs', ctypes.c_uint64)]


class _PathRule(ctypes.Structure):
    """Packed Linux landlock_path_beneath_attr, retaining its kernel field layout."""

    _pack_ = 1
    _fields_ = [('allowed_access', ctypes.c_uint64), ('parent_fd', ctypes.c_int32)]


class _Filter(ctypes.Structure):
    """Native sock_fprog pointing to owned classic-BPF instructions during prctl."""

    _fields_ = [('length', ctypes.c_ushort), ('instructions', ctypes.c_void_p)]


def _checked(result, operation):
    """Reject any unsupported or denied sandbox operation without an unrestricted fallback."""
    if result < 0:
        number = ctypes.get_errno()
        raise OSError(number, operation)
    return result


def requirements():
    """Inspect mandatory worker capabilities without restricting or modifying the host process."""
    if sys.platform != 'linux' or platform.machine() != 'x86_64':
        raise RuntimeError('Document workers require the verified Linux x86_64 policy')
    if os.getuid() == 0 or os.geteuid() == 0:
        raise RuntimeError('Document workers require an unprivileged serving user')
    libc = ctypes.CDLL(None, use_errno=True)
    abi = _checked(libc.syscall(444, 0, 0, 1), 'Landlock ABI query failed')
    if abi < 3:
        raise RuntimeError('Document workers require Landlock ABI3 or newer')
    return abi


def install(options):
    """Restrict a fresh unprivileged worker before importing third-party document/model code."""
    from backend.runtime.broker_profile import _syscall_filter

    abi = requirements()
    libc = ctypes.CDLL(None, use_errno=True)
    _checked(libc.prctl(38, 1, 0, 0, 0), 'Worker no-new-privileges failed')
    # Handle every filesystem right through truncate; no mutation is granted.
    attributes = _Ruleset((1 << 15) - 1)
    ruleset = _checked(libc.syscall(444, ctypes.byref(attributes), ctypes.sizeof(attributes), 0),
                       'Worker filesystem ruleset failed')
    roots = [Path('/usr'), Path('/lib'), Path('/lib64'), Path(sys.base_prefix),
             Path(options['dependencies']), Path(options['package_root'])/'backend']
    files = [Path('/etc/ld.so.cache'), Path('/dev/null'), Path('/dev/urandom'),
             Path('/proc/cpuinfo')]
    try:
        seen = set()
        for candidate in [*roots, *files]:
            if not candidate.exists():
                continue
            path = candidate.resolve(strict=True)
            if path == Path('/'):
                raise ValueError('Worker cannot expose the host filesystem root')
            if path in seen:
                continue
            seen.add(path)
            fd = os.open(path, os.O_PATH | os.O_CLOEXEC | os.O_NOFOLLOW)
            try:
                access = (1 << 2) | ((1 << 3) if path.is_dir() else 0)
                rule = _PathRule(access, fd)
                _checked(libc.syscall(445, ruleset, 1, ctypes.byref(rule), 0), 'Worker filesystem rule failed')
            finally:
                os.close(fd)
        _checked(libc.syscall(446, ruleset, 0), 'Worker filesystem restriction failed')
    finally:
        os.close(ruleset)
    policy = _syscall_filter(network=False, protected_peers=True)
    # The shared broker prefix first validates the architecture and syscall ABI.
    extra = []
    # Landlock does not mediate chmod/chown/xattr/timestamps. Deny those syscall
    # families separately, plus shared host IPC, signals and descriptor controls.
    for number in (16, 29, 30, 31, 56, 57, 58, 59, 62, 64, 65, 66, 67, 68, 69,
                   70, 71, 72, 73, 90, 91, 92, 93, 94, 129, 132, 169, 175, 176,
                   188, 189, 190, 197, 198, 199, 200, 220, 234, 235, 240, 241,
                   242, 243, 244, 245, 246, 248, 249, 250, 260, 261, 268, 280,
                   297, 313, 320, 322, 424, 425, 426, 427, 434, 435, 452, 463, 466):
        extra += [(0x15, 0, 1, number), (0x06, 0, 0, 0x00050000 | errno.EPERM)]
    encoded = policy[:48] + b''.join(struct.pack('=HBBI', *row) for row in extra) + policy[48:]
    instructions = ctypes.create_string_buffer(encoded)
    program = _Filter(len(encoded)//8, ctypes.addressof(instructions))
    _checked(libc.prctl(22, 2, ctypes.byref(program), 0, 0), 'Worker syscall restriction failed')
    return {'landlock_abi': abi, 'filesystem': 'selected_public_reads_no_writes',
            'network': 'denied', 'new_processes_and_threads': 'denied'}
