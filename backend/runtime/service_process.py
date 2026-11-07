"""Own a bounded API/service process tree independently of native actor grants.

A small guardian outside the service cgroup owns its retirement. The launcher
holds original pidfds and an ownership lock; the guardian shares that lock until
physical group closure, including after launcher death. Neither this receipt nor
a service exit certifies closure or acceptance of native agent attempts.
"""

from contextlib import contextmanager
from dataclasses import asdict
import ctypes
import errno
import fcntl
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import sysconfig
from threading import Event, Thread
import time
from uuid import uuid4

PROGRAM = Path(__file__).resolve()
DEFAULT_SERVICE_LIMITS = {'memory_bytes':2*1024**3,'pids':128,'cpu_millis':2000}


def _ownership_lock(directory):
    """Hold one private lock shared by launches, their guardians and offline backups."""
    directory = Path(directory).absolute()
    info = directory.stat()
    if directory.resolve(strict=True) != directory or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Service state directory must be canonical, private and user-owned')
    fd = os.open(directory/'service-owner.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BaseException:
        os.close(fd)
        raise RuntimeError('Another launcher, backup or resource guardian still owns this installation')
    return fd


@contextmanager
def frozen_service_ownership(directory, *, reboot_evidence=None):
    """Exclude service startup during backup; pending prior-kernel receipts remain archival evidence only."""
    fd = _ownership_lock(directory)
    try:
        try:receipt = read_receipt(directory)
        except FileNotFoundError:receipt = None
        if receipt is not None and (receipt.get('status') != 'closed' or receipt.get('domain_removed') is not True):
            from backend.runtime.reboot_authority import validate_reboot_evidence
            from backend.runtime.peer_process import boot_id

            if reboot_evidence is None:
                raise ValueError('Service closure is unconfirmed; preserve its receipt and reconcile before backup')
            evidence = validate_reboot_evidence(reboot_evidence)
            identity = receipt.get('domain_identity') or {}
            if (evidence['observed_boot_id'] != boot_id() or
                    identity.get('boot_id') != evidence['source_boot_id'] or
                    identity.get('observer_namespace') != evidence['source_observer_namespace']):
                raise ValueError('Unconfirmed service closure does not match verified prior-kernel evidence')
        yield
    finally:
        os.close(fd)


def write_receipt(directory, value):
    """Atomically replace the private service resource receipt without publishing partially written JSON."""
    directory = Path(directory)
    temporary = directory / ('.service-resources-' + uuid4().hex)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(temporary, directory/'service-resources.json')
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


def read_receipt(directory):
    """Read only a bounded regular private receipt, never a symbolic redirect into other host state."""
    import stat

    fd = os.open(Path(directory)/'service-resources.json', os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'r') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 65536:
            raise ValueError('Invalid service resource receipt')
        return json.load(stream)


def _forward(stream, destination, failed):
    """Relay bounded chunks without accumulating a slow or verbose service's output in launcher memory."""
    try:
        while data := stream.read(8192):
            while data:
                count = os.write(destination, data)
                data = data[count:]
    except (OSError, ValueError):
        failed.set()


def _poll(child):
    """Observe only the original contained child; an observation timeout leaves it running."""
    try:return child.wait(timeout=0)
    except TimeoutError:return None


def _terminate(child):
    """Request graceful shutdown through the original pidfd using the project's supported libc binding."""
    from backend.runtime.peer_process import _libc

    if _libc().pidfd_send_signal(child._pidfd,signal.SIGTERM,None,0) < 0:
        number = ctypes.get_errno()
        if number != errno.ESRCH:
            raise OSError(number,os.strerror(number))


def run_bounded_services(services, *, cgroup_parent, limits, state_dir, grace=15):
    """Serve under one shared kernel budget, draining original children and the guardian before releasing ownership."""
    from backend.runtime.execution_domain import ExecutionDomain
    from backend.runtime.peer_broker import BrokerLimits

    limits = asdict(BrokerLimits(**limits))
    directory = Path(state_dir).absolute()
    lock = _ownership_lock(directory)
    domain = guardian = control = None
    children = [];forwarders = [];requested = 0
    failed_output = Event();armed = False
    old_handlers = {}
    receipt = None

    def request_stop(number, _frame):
        """Record shutdown intent without losing a child whose atomic constructor has not returned yet."""
        nonlocal requested
        requested = 128 + number

    try:
        try:previous = read_receipt(directory)
        except FileNotFoundError:previous = None
        if previous is not None and (previous.get('status') != 'closed' or previous.get('domain_removed') is not True):
            raise RuntimeError('Previous service resource closure is unconfirmed; inspect service-resources.json before starting another host')
        path = Path(cgroup_parent)/('researcher-service-' + uuid4().hex)
        path.mkdir(mode=0o700)
        try:domain = ExecutionDomain.open(path)
        except BaseException:
            path.rmdir()
            raise
        domain.limit(**limits)
        receipt = {'format':1,'status':'starting','domain_path':str(path),
                   'domain_identity':asdict(domain.identity),'limits':limits,
                   'domain_removed':False,'native_actor_closure_proven':False}
        write_receipt(directory, receipt)
        read_fd, control = os.pipe2(os.O_CLOEXEC)
        options = {'directory':str(directory),'domain_path':str(path),
                   'identity':asdict(domain.identity),'control':read_fd,
                   'package_root':str(PROGRAM.parents[2]),'dependencies':sysconfig.get_path('purelib')}
        try:
            guardian = subprocess.Popen([sys.executable,'-I','-S',str(PROGRAM),'guardian',json.dumps(options)],
                stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                pass_fds=(read_fd,lock),env={'PATH':os.defpath,'LANG':'C.UTF-8'},cwd='/')
        finally:os.close(read_fd)
        if not select.select([guardian.stdout],[],[],5)[0] or os.read(guardian.stdout.fileno(),1) != b'R':
            raise RuntimeError('Service resource guardian did not arm; no service was started')
        armed = True
        for number in (signal.SIGINT,signal.SIGTERM):
            old_handlers[number] = signal.signal(number,request_stop)
        for label, command, cwd in services:
            if requested:return requested
            payload = json.dumps({'argv':command,'cwd':str(cwd)})
            child = domain.spawn([sys.executable,'-I','-S',str(PROGRAM),'entry',payload],env=dict(os.environ))
            children.append(child)
            child.stdin.close()
            for stream, target in ((child.stdout,1),(child.stderr,2)):
                forwarding = Thread(target=_forward,args=(stream,target,failed_output),daemon=True)
                forwarding.start();forwarders.append(forwarding)
            print(f'Starting {label} in a bounded service group.',flush=True)
        while not requested:
            if guardian.poll() is not None:
                raise RuntimeError('Service resource guardian ended unexpectedly')
            if failed_output.is_set():
                raise RuntimeError('Service output transport failed; stopping the original group')
            for child in children:
                status = _poll(child)
                if status is not None:return status if status >= 0 else 128-status
            time.sleep(.05)
        return requested
    finally:
        try:
            for child in children:
                if _poll(child) is None:
                    try:_terminate(child)
                    except OSError:
                        print('El cierre ordenado falló; se retirará el grupo original de servicios.',file=sys.stderr,flush=True)
            deadline = time.monotonic()+grace
            while any(_poll(child) is None for child in children) and time.monotonic()<deadline:
                time.sleep(.01)
            if control is not None:
                try:os.write(control,b'S')
                except BrokenPipeError:pass
                os.close(control);control=None
            if guardian is not None:
                # Keep observing this handle; elapsed observation is not closure.
                while True:
                    try:guard_status=guardian.wait(timeout=5);break
                    except subprocess.TimeoutExpired:
                        print('El cierre del grupo de servicios sigue pendiente; no se iniciará otro.',file=sys.stderr,flush=True)
                guardian.stdout.close()
            else:guard_status=None
            if domain is not None and (not armed or guard_status != 0):
                closure = domain.retire(timeout=5)
                if receipt is not None:
                    write_receipt(directory,{**receipt,'status':'closed','reason':'guardian_unavailable',
                        'domain_removed':closure.removed,'resources':closure.resources})
            if domain is not None and receipt is not None:
                final = read_receipt(directory)
                if final.get('status') != 'closed' or final.get('domain_removed') is not True or final.get('domain_identity') != asdict(domain.identity):
                    raise RuntimeError('Original service group closure is not confirmed')
                resources = final.get('resources') or {}
                if resources.get('memory_oom_kills',0):
                    print('El servicio agotó su límite compartido de memoria. Se conserva el almacenamiento; '
                          'revisa la recuperación antes de reanudar tareas.',file=sys.stderr,flush=True)
                elif resources.get('pids_denied',0):
                    print('El servicio alcanzó su límite de procesos o hilos; se conserva el diagnóstico de recursos.',file=sys.stderr,flush=True)
            for child in children:child.wait(timeout=5)
        finally:
            if control is not None:os.close(control)
            for forwarder in forwarders:forwarder.join(timeout=1)
            for child in children:child.close_handles()
            if domain is not None:domain.close()
            for number,handler in old_handlers.items():signal.signal(number,handler)
            os.close(lock)


def guardian_main(options):
    """Retire the exact service group on a stop byte or launcher pipe loss, then persist physical closure."""
    sys.path[:0] = [options['package_root'],options['dependencies']]
    from backend.runtime.execution_domain import DomainIdentity, ExecutionDomain

    with ExecutionDomain.open(options['domain_path'],expected=DomainIdentity(**options['identity'])) as domain:
        receipt = read_receipt(options['directory'])
        os.write(1,b'R')
        message = os.read(options['control'],1)
        os.close(options['control'])
        closure = domain.retire(timeout=5)
        write_receipt(options['directory'],{**receipt,'status':'closed',
            'reason':'stop_requested' if message == b'S' else 'launcher_lost',
            'domain_removed':closure.removed,'resources':closure.resources})


def main():
    """Run only a trusted guardian or exec bootstrap; public service selection belongs to the installed launcher."""
    options = json.loads(sys.argv[2])
    if sys.argv[1] == 'guardian':
        guardian_main(options)
    elif sys.argv[1] == 'entry':
        os.chdir(options['cwd'])
        os.execvpe(options['argv'][0],options['argv'],os.environ)
    else:raise ValueError('Unknown service resource helper mode')


if __name__ == '__main__':
    main()
