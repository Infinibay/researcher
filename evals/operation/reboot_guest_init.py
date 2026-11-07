#!/python/bin/python3.12 -S
"""Boot only the disposable QEMU fixture, restart its guest kernel once, then power it off.

This file belongs in the test initramfs. It must never be run as host administration.
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
import time


def observe_live_process(identity):
    """Revalidate the recorded PID start time and namespace without signaling any numeric PID."""
    path = Path('/proc')/str(identity['pid'])
    fields = (path/'stat').read_text().rsplit(') ',1)[1].split()
    if fields[0] in ('Z','X') or int(fields[19]) != identity['start_ticks']:
        raise RuntimeError('Original guest process exited or its identity changed')
    if (path/'ns/pid').stat().st_ino != identity['namespace']:
        raise RuntimeError('Original guest process namespace changed')


def await_active_before_reboot(process, root):
    """Observe the original holder, native init and executing command alive before allowing a guest-only reboot."""
    deadline = time.monotonic()+60
    while not (root/'active-ready.json').exists():
        if process.poll() is not None:
            raise RuntimeError('Original active fixture exited before readiness')
        if time.monotonic() >= deadline:
            raise TimeoutError('Original active fixture did not reach its readiness boundary')
        time.sleep(.025)
    previous = json.loads((root/'before.json').read_text())
    if previous['holder']['pid'] != process.pid or process.poll() is not None:
        raise RuntimeError('Active readiness does not belong to the original child handle')
    boot_id = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if previous['boot_id'] != boot_id:
        raise RuntimeError('Active readiness belongs to another boot')
    peer = previous['peer_identity']
    observe_live_process(previous['holder'])
    observe_live_process({'pid':peer['init_pid'],'start_ticks':peer['start_ticks'],'namespace':peer['init_namespace']})
    observe_live_process(previous['command_child'])
    if previous['command_child']['namespace'] != peer['init_namespace'] or peer['init_namespace'] == previous['holder']['namespace']:
        raise RuntimeError('The native command is not in its original private namespace')
    with (root/'init-active-observation.json').open('x') as stream:
        json.dump({'boot_id':boot_id,'holder_alive':True,'peer_alive':True,'command_alive':True,
                   'holder_pid':process.pid,'peer_id':previous['peer_id'],'job_id':previous['active_job_id']},stream)
        stream.flush();os.fsync(stream.fileno())


def mount(source, target, kind):
    """Mount one fixed guest filesystem and surface the kernel's original errno."""
    Path(target).mkdir(parents=True, exist_ok=True)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.mount(source.encode(), target.encode(), kind.encode(), ctypes.c_ulong(0), None):
        raise OSError(ctypes.get_errno(), f'Guest mount failed: {target}')


def boot():
    """Prepare guest-only devices/controllers and run the unprivileged installed-product fixture."""
    if os.getpid() != 1 or os.getuid() != 0 or not Path('/RESEARCHER_DISPOSABLE_VM').is_file():
        raise RuntimeError('This init is only for PID1 in the disposable test initramfs')
    if not Path('/proc/self').exists():
        mount('proc', '/proc', 'proc')
    if 'researcher_disposable_vm=1' not in Path('/proc/cmdline').read_text().split():
        raise RuntimeError('Missing disposable guest kernel marker')
    mount('sysfs', '/sys', 'sysfs')
    if not Path('/dev/urandom').exists():
        mount('devtmpfs', '/dev', 'devtmpfs')
    mount('cgroup2', '/sys/fs/cgroup', 'cgroup2')
    mount('/dev/vda', '/state', 'ext4')
    os.chown('/state', 1000, 1000)
    Path('/state').chmod(0o700)
    Path('/tmp').mkdir(exist_ok=True)
    Path('/tmp').chmod(0o1777)
    Path('/home/fixture').mkdir(parents=True, exist_ok=True)
    os.chown('/home/fixture', 1000, 1000)
    group = Path('/sys/fs/cgroup')
    (group/'init').mkdir()
    (group/'init/cgroup.procs').write_text(str(os.getpid()))
    (group/'cgroup.subtree_control').write_text('+memory +pids')
    delegated = group/'researcher'
    delegated.mkdir()
    (delegated/'cgroup.subtree_control').write_text('+memory +pids')
    for name in ('', 'cgroup.procs', 'cgroup.threads', 'cgroup.subtree_control'):
        os.chown(delegated/name, 1000, 1000)
    owner = delegated/'owner'
    owner.mkdir()
    for name in ('', 'cgroup.procs', 'cgroup.threads', 'cgroup.subtree_control'):
        os.chown(owner/name, 1000, 1000)
    # The unprivileged fixture must inherit a cgroup inside its delegated subtree,
    # so clone-into-cgroup never needs migration permission on the root hierarchy.
    (owner/'cgroup.procs').write_text(str(os.getpid()))
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as control:
        fcntl.ioctl(control, 0x8914, struct.pack('16sH14x', b'lo', 0x49))
    phase = 'after' if Path('/state/before.json').exists() else 'before'
    print('RESEARCHER-GUEST-PHASE:'+phase, flush=True)
    command = ['/state/env/bin/python', '-I', '/state/eval/reboot_guest.py', phase]
    active = json.loads(Path('/state/eval-mode.json').read_text()).get('active_command',False)
    kwargs = dict(
        cwd='/state', env={'PATH':'/usr/bin:/bin', 'HOME':'/home/fixture', 'LANG':'C.UTF-8'},
        user=1000, group=1000, extra_groups=[])
    if phase == 'before' and active:
        process = subprocess.Popen(command,**kwargs)
        try:
            await_active_before_reboot(process,Path('/state'))
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
            raise
        # Do not reap or close this active holder before restarting its kernel.
    else:
        result = subprocess.run(command,**kwargs,check=False)
        if result.returncode:
            raise RuntimeError(f'Guest phase {phase} exited {result.returncode}')
    os.sync()
    return phase == 'before'


def main():
    """Reboot only after a successful first phase; preserve and report any fixture failure."""
    restart = False
    try:
        restart = boot()
    except BaseException as error:
        traceback.print_exc()
        print('RESEARCHER-REBOOT-RESULT:'+json.dumps({'status':'failed', 'error_type':type(error).__name__}), flush=True)
    # The safety checks must also hold before either reboot syscall after an error.
    if os.getpid() != 1 or not Path('/RESEARCHER_DISPOSABLE_VM').is_file():
        raise RuntimeError('Refusing any reboot outside the owned guest')
    os.sync()
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.reboot(0x01234567 if restart else 0x4321FEDC):
        raise OSError(ctypes.get_errno(), 'Guest reboot/poweroff failed')


if __name__ == '__main__':
    main()
