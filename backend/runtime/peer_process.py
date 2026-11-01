"""Linux namespace-init identity and terminal proof; never signal a numeric PID.

This owns process lifetime, not filesystem/network policy or remote billing.
Only identities captured before releasing a trusted payload gate are recoverable.
"""

import ctypes
import errno
import os
import select
import signal
from dataclasses import dataclass
from pathlib import Path


class PeerUncertain(RuntimeError):
    """The kernel observation cannot prove the registered namespace closed."""


def boot_id():
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()


def observer_namespace():
    return os.stat("/proc/self/ns/pid").st_ino


def start_ticks(pid):
    # comm may contain spaces or ')' characters; fields after its last ') '
    # begin at state (field 3), so starttime (field 22) is index 19.
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()
    return int(fields[19])


def _libc():
    libc = ctypes.CDLL(None, use_errno=True)
    libc.pidfd_open.argtypes = [ctypes.c_int, ctypes.c_uint]
    libc.pidfd_send_signal.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint,
    ]
    return libc


def _pidfd(pid):
    fd = _libc().pidfd_open(pid, 0)
    if fd < 0:
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number))
    return fd


def _signal(fd):
    if _libc().pidfd_send_signal(fd, signal.SIGKILL, None, 0) < 0:
        number = ctypes.get_errno()
        if number != errno.ESRCH:
            raise OSError(number, os.strerror(number))


def _init_fields(pid):
    ticks = start_ticks(pid)
    namespace = os.stat(f"/proc/{pid}/ns/pid").st_ino
    lines = Path(f"/proc/{pid}/status").read_text().splitlines()
    ids = next(line.split()[1:] for line in lines if line.startswith("NSpid:"))
    return ticks, namespace, ids[-1] == "1"


@dataclass(frozen=True)
class NamespaceIdentity:
    init_pid: int
    start_ticks: int
    boot_id: str
    init_namespace: int
    observer_namespace: int

    @classmethod
    def capture(cls, pid, *, expected_parent=None):
        fd = _pidfd(pid)
        try:
            ticks, namespace, is_init = _init_fields(pid)
            observer = observer_namespace()
            if not is_init or namespace == observer:
                raise PeerUncertain("Reported process is not a private namespace init")
            if expected_parent is not None:
                parent = int(
                    Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()[1]
                )
                if parent != expected_parent:
                    raise PeerUncertain("Namespace init belongs to another launcher")
            poller = select.poll()
            poller.register(fd, select.POLLIN | select.POLLHUP)
            if poller.poll(0):
                raise PeerUncertain("Namespace init exited during registration")
            return cls(pid, ticks, boot_id(), namespace, observer)
        finally:
            os.close(fd)

    @classmethod
    def from_record(cls, record):
        return cls(**{key: record[key] for key in cls.__dataclass_fields__})


def close_namespace(identity, *, timeout=5):
    """Pin, revalidate, kill init, and wait for the kernel namespace barrier.

    Missing/replaced init is proof only because binding validated that it was
    PID 1 of a fresh private namespace. Permission/visibility failures are unknown.
    """
    try:
        if boot_id() != identity.boot_id:
            raise PeerUncertain(
                "Registered kernel differs; original host closure is not proven"
            )
        if observer_namespace() != identity.observer_namespace:
            raise PeerUncertain("Observer PID namespace changed")
        try:
            fd = _pidfd(identity.init_pid)
        except ProcessLookupError:
            return "init_absent"
        try:
            try:
                ticks, namespace, is_init = _init_fields(identity.init_pid)
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                # Exit can remove stat/ns metadata before all procfs reads
                # finish. Keep the pinned pidfd and wait for its kernel barrier;
                # Exit was also observed returning EACCES for ns/pid. Denial
                # alone never authorizes signaling or closure: a live pidfd
                # remains unknown when this bounded terminal wait expires.
                poller = select.poll()
                poller.register(fd, select.POLLIN | select.POLLHUP)
                if poller.poll(int(timeout * 1000)):
                    return "init_exited"
                raise PeerUncertain(
                    "Process namespace temporarily unreadable"
                ) from None
            if (ticks, namespace, is_init) != (
                identity.start_ticks,
                identity.init_namespace,
                True,
            ):
                return "identity_replaced"
            _signal(fd)
            poller = select.poll()
            poller.register(fd, select.POLLIN | select.POLLHUP)
            if not poller.poll(int(timeout * 1000)):
                raise PeerUncertain("Namespace init did not reach terminal state")
            return "init_exited"
        finally:
            os.close(fd)
    except (OSError, ValueError, IndexError, StopIteration, AttributeError) as exc:
        raise PeerUncertain(
            "Unable to verify the registered process namespace"
        ) from exc
