"""Mount only disposable VM disks and check full-volume retention across a remount.

This program is a guarded PID1 fixture, never a host administration command.
"""

import ctypes
import fcntl
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import traceback


def require_guest():
    """Refuse privileged operations outside the explicitly marked disposable kernel."""
    if (os.getpid() != 1 or os.getuid() != 0
            or not Path('/RESEARCHER_DISPOSABLE_VM').is_file()
            or 'researcher_disposable_vm=1' not in Path('/proc/cmdline').read_text().split()):
        raise RuntimeError('Storage fixture requires PID1 in its disposable VM')


def mount(source, destination, kind):
    """Mount one fixed guest-only filesystem, preserving failures rather than repairing it."""
    require_guest()
    Path(destination).mkdir(parents=True, exist_ok=True)
    subprocess.run(['/usr/bin/mount', '-n', '-t', kind, source, destination], check=True, timeout=10)


def run_phase(phase, *, recovery=False):
    """Run the installed product as the unprivileged serving user with no real credentials."""
    subprocess.run(
        ['/state/env/bin/python', '-I', '/state/eval/'+('storage_recovery_guest.py' if recovery else 'storage_guest.py'), phase],
        cwd='/state', env={'PATH': '/usr/bin:/bin', 'HOME': '/home/fixture', 'LANG': 'C.UTF-8'},
        user=1000, group=1000, extra_groups=[], check=True, timeout=90,
    )


def boot():
    """Observe exhaustion, missing storage and retained data using two private virtio disks."""
    require_guest()
    mount('sysfs', '/sys', 'sysfs')
    mount('cgroup2', '/sys/fs/cgroup', 'cgroup2')
    mount('/dev/vda', '/state', 'ext4')
    mount('/dev/vdb', '/bounded', 'ext4')
    for path in ('/state', '/bounded', '/home/fixture'):
        Path(path).mkdir(parents=True, exist_ok=True)
        os.chown(path, 1000, 1000)
        Path(path).chmod(0o700)
    Path('/tmp').chmod(0o1777)
    group = Path('/sys/fs/cgroup')
    (group/'init').mkdir()
    (group/'init/cgroup.procs').write_text(str(os.getpid()))
    (group/'cgroup.subtree_control').write_text('+cpu +memory +pids')
    delegated = group/'researcher'
    delegated.mkdir()
    (delegated/'cgroup.subtree_control').write_text('+cpu +memory +pids')
    (delegated/'owner').mkdir()
    for root in (delegated, delegated/'owner'):
        for name in ('', 'cgroup.procs', 'cgroup.threads', 'cgroup.subtree_control'):
            os.chown(root/name, 1000, 1000)
    (delegated/'owner/cgroup.procs').write_text(str(os.getpid()))
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as control:
        fcntl.ioctl(control,0x8914,struct.pack('16sH14x',b'lo',0x49))
    if json.loads(Path('/state/eval-mode.json').read_text()).get('storage_recovery'):
        phase='after' if Path('/state/storage-result.json').exists() else 'before'
        run_phase(phase,recovery=True)
        if phase=='before':return True
        result=json.loads(Path('/state/storage-result.json').read_text())
        result.update(status='passed',model_turns=0,real_credentials=False,controlled_kernel_restart=True)
        print('RESEARCHER-REBOOT-RESULT:'+json.dumps(result),flush=True)
        return False
    run_phase('exercise')
    subprocess.run(['/usr/bin/umount', '/bounded'], check=True, timeout=10)
    run_phase('missing')
    mount('/dev/vdb', '/bounded', 'ext4')
    run_phase('retained')
    result = json.loads(Path('/state/storage-result.json').read_text())
    result.update(status='passed', model_turns=0, remounted=True, real_credentials=False)
    print('RESEARCHER-REBOOT-RESULT:' + json.dumps(result), flush=True)


def main():
    """Power off only this marked guest after preserving the original trial's result."""
    require_guest()
    restart=False
    try:
        restart=boot()
    except BaseException as error:
        traceback.print_exc()
        print('RESEARCHER-REBOOT-RESULT:' + json.dumps({'status': 'failed', 'error_type': type(error).__name__}), flush=True)
    require_guest()
    os.sync()
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.reboot(0x01234567 if restart else 0x4321FEDC):
        raise OSError(ctypes.get_errno(), 'Disposable guest poweroff failed')


if __name__ == '__main__':
    main()
