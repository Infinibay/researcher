"""Linux contained birth/retirement, not a sandbox or enrollment of all actors.

Only a trusted broker may call this primitive. It must persist the domain intent
before spawning and deny payload migration (cgroupfs, D-Bus and other control
channels). No production grant or peer gate is authorized by this module.
"""

import math
import os
import select
import stat
import threading
import time
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path

from backend.runtime import _domain_spawn
from backend.runtime.peer_process import boot_id, observer_namespace


def _deadline(timeout):
    """Validate a finite positive timeout of at most 60seconds and return its absolute monotonic
    deadline.
    """
    if (
        type(timeout) not in (int, float)
        or not math.isfinite(timeout)
        or not 0 < timeout <= 60
    ):
        raise ValueError("Expected a finite deadline between zero and 60 seconds")
    return time.monotonic() + timeout


class DomainUncertain(RuntimeError):
    """Domain identity or terminal closure cannot be established."""


@dataclass(frozen=True)
class DomainIdentity:
    """Pin an opened cgroup object together with boot, observer and cgroup-namespace identities; this
    value is not an execution grant.
    """
    device: int
    inode: int
    boot_id: str
    observer_namespace: int
    observer_cgroup_namespace: int


@dataclass(frozen=True)
class DomainClosure:
    """Exact subtree retirement plus optional kernel counters sampled before removing that identity."""

    identity: DomainIdentity
    removed: bool
    resources: dict | None = None


class ContainedChild:
    """A transport/reaping handle; its exit does not certify domain closure."""

    def __init__(self, pid, pidfd, stdin, stdout, stderr):
        """Own the child's pidfd and unbuffered transport pipes for later observation and reaping,
        without certifying subtree closure.
        """
        self.pid, self._pidfd = pid, pidfd
        self.stdin = os.fdopen(stdin, "wb", buffering=0)
        self.stdout = os.fdopen(stdout, "rb", buffering=0)
        self.stderr = os.fdopen(stderr, "rb", buffering=0)
        self._status = None
        self._wait_lock = threading.Lock()

    def wait(self, *, timeout=5):
        """Poll the owned pidfd and cache the reaped direct-child exit; timeout or external reaping
        does not become an invented terminal receipt.
        """
        with self._wait_lock:
            if self._status is None:
                poller = select.poll()
                poller.register(self._pidfd, select.POLLIN | select.POLLHUP)
                if not poller.poll(int(timeout * 1000)):
                    raise TimeoutError("Contained child is still running")
                try:
                    _, status = os.waitpid(self.pid, 0)
                except ChildProcessError as exc:
                    raise DomainUncertain(
                        "Child was reaped without its owned receipt"
                    ) from exc
                self._status = os.waitstatus_to_exitcode(status)
            return self._status

    def close_handles(self):
        """Release transport streams and the pidfd without terminating or certifying retirement of the
        execution domain.
        """
        for stream in (self.stdin, self.stdout, self.stderr):
            stream.close()
        if self._pidfd is not None:
            os.close(self._pidfd)
            self._pidfd = None


class ExecutionDomain:
    """Open-only kernel domain. Closing handles never claims actors are closed.

    A missing expected domain is uncertain, never an empty installation. Retire
    kills the exact opened subtree, waits for populated=0, then removes the leaf.
    A caller retaining an old cgroup FD cannot birth into that retired object.
    Identity must be persisted externally; opening a fresh test leaf proves no
    coverage of actors outside that leaf.
    """

    @classmethod
    def open(cls, path, *, expected=None):
        """Open an existing non-threaded cgroup domain, reject the controller's ancestry and optionally
        match an externally retained identity; never provision a new domain.
        """
        self = cls.__new__(cls)
        self.path = Path(path).absolute()
        self._fd = self._parent_fd = None
        self._pid = os.getpid()
        self._lock = threading.RLock()
        self._retired = False
        self._retiring = threading.Event()
        try:
            self._parent_fd = os.open(
                self.path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
            )
            self._fd = os.open(
                self.path.name,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=self._parent_fd,
            )
            _domain_spawn.validate(self._fd)
            info = os.fstat(self._fd)
            self.identity = DomainIdentity(
                info.st_dev,
                info.st_ino,
                boot_id(),
                observer_namespace(),
                os.stat("/proc/self/ns/cgroup").st_ino,
            )
            if expected is not None and self.identity != expected:
                raise DomainUncertain("Provisioned execution domain identity differs")
            self._check()
            self._reject_own_ancestors()
            if self._read("cgroup.type").strip() != "domain":
                raise DomainUncertain("Execution requires a non-threaded domain cgroup")
            return self
        except BaseException as exc:
            self.close()
            if isinstance(exc, OSError):
                raise DomainUncertain(
                    "Execution domain unavailable or not cgroup v2"
                ) from exc
            raise

    def __enter__(self):
        """Use the already opened domain without starting or releasing an actor."""
        return self

    def __exit__(self, *_):
        """Release domain handles on context exit; actor retirement remains a separate explicit
        operation.
        """
        self.close()

    def close(self):
        """Release local directory descriptors, including inherited handles after fork, without killing
        actors or claiming the domain is empty.
        """
        with self._lock if self._pid == os.getpid() else nullcontext():
            for name in ("_fd", "_parent_fd"):
                fd = getattr(self, name)
                if fd is not None:
                    os.close(fd)
                    setattr(self, name, None)

    def _reject_own_ancestors(self):
        # Never permit retirement of the broker/test runner or an ancestor.
        """Reject a domain containing the controller or one of its ancestors before the object can be
        used for subtree retirement.
        """
        mount = Path("/sys/fs/cgroup")
        entries = Path("/proc/self/cgroup").read_text().splitlines()
        unified = [line[3:] for line in entries if line.startswith("0::")]
        if len(unified) != 1:
            raise DomainUncertain("Cannot locate the controller observer cgroup")
        current = mount / unified[0].lstrip("/")
        for path in (current, *current.parents):
            info = path.stat()
            if (info.st_dev, info.st_ino) == (
                self.identity.device,
                self.identity.inode,
            ):
                raise DomainUncertain("Execution domain contains its own controller")
            if path == mount:
                return
        raise DomainUncertain("Cannot verify the controller cgroup ancestry")

    def _check(self):
        """Require the same live opened object, process, boot and observer namespaces; replaced or
        retired paths require explicit reconciliation.
        """
        if self._pid != os.getpid() or self._fd is None or self._retired:
            raise DomainUncertain("Reopen domain after fork, close or retirement")
        info = os.stat(self.path.name, dir_fd=self._parent_fd, follow_symlinks=False)
        opened = os.fstat(self._fd)
        if (
            not stat.S_ISDIR(info.st_mode)
            or (info.st_dev, info.st_ino) != (self.identity.device, self.identity.inode)
            or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)
        ):
            raise DomainUncertain("Execution domain path was replaced")
        if (
            boot_id() != self.identity.boot_id
            or observer_namespace() != self.identity.observer_namespace
            or os.stat("/proc/self/ns/cgroup").st_ino
            != self.identity.observer_cgroup_namespace
        ):
            raise DomainUncertain("Execution domain kernel/observer changed")

    def _read(self, name):
        """Read one bounded ASCII control-file window relative to the pinned domain descriptor without
        following a symlink leaf.
        """
        fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=self._fd)
        try:
            return os.read(fd, 4096).decode("ascii")
        finally:
            os.close(fd)

    def limit(self, *, pids, memory_bytes, cpu_millis=2000):
        """Bound all descendants together; CPU milliseconds per second are shared bandwidth, not a per-process allowance."""
        if (
            type(pids) is not int
            or not 1 <= pids <= 1024
            or type(memory_bytes) is not int
            or not 64 * 1024**2 <= memory_bytes <= 8 * 1024**3
            or type(cpu_millis) is not int
            or not 100 <= cpu_millis <= 8000
        ):
            raise ValueError("Invalid execution domain resource limits")
        if self._pid != os.getpid():
            raise DomainUncertain("Reopen execution domain after fork")
        with self._lock:
            self._check()
            if (
                self._retiring.is_set()
                or "populated 0" not in self._read("cgroup.events").splitlines()
            ):
                raise DomainUncertain(
                    "Only an empty admitted domain can configure limits"
                )
            for name, value in (
                ("pids.max", pids),
                ("memory.max", memory_bytes),
                ("memory.swap.max", 0),
                ("memory.oom.group", 1),
                ("cpu.max", f"{cpu_millis * 100} 100000"),
            ):
                fd = os.open(
                    name, os.O_WRONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=self._fd
                )
                try:
                    data = str(value).encode()
                    if os.write(fd, data) != len(data) or self._read(
                        name
                    ).strip() != str(value):
                        raise DomainUncertain(
                            "Required execution limit was not applied"
                        )
                finally:
                    os.close(fd)

    def _resource_observation(self):
        """Read aggregate kernel counters without allowing unavailable telemetry to prevent physical retirement."""
        try:
            cpu = dict(line.split() for line in self._read("cpu.stat").splitlines())
            memory = dict(line.split() for line in self._read("memory.events").splitlines())
            pids = dict(line.split() for line in self._read("pids.events").splitlines())
            counters = {
                "cpu_usage_usec": int(cpu["usage_usec"]),
                "cpu_throttled_periods": int(cpu["nr_throttled"]),
                "memory_oom_kills": int(memory["oom_kill"]),
                "memory_group_oom_kills": int(memory["oom_group_kill"]),
                "pids_denied": int(pids["max"]),
            }
            if any(value < 0 for value in counters.values()):
                raise ValueError("Invalid kernel counter")
            return {"observed": True, **counters, "limits": {
                "cpu_max": self._read("cpu.max").strip(),
                "memory_max": self._read("memory.max").strip(),
                "pids_max": self._read("pids.max").strip(),
            }}
        except (OSError, ValueError, KeyError):
            return {"observed": False}

    def spawn(self, argv, *, env=None, pass_fds=()):
        """Birth one child in the exact domain from a fair scheduler; admitted capsules deny subsequent scheduler changes."""
        if os.sched_getscheduler(0) not in (os.SCHED_OTHER, os.SCHED_BATCH, os.SCHED_IDLE):
            raise DomainUncertain("Execution requires a scheduler covered by CPU bandwidth control")
        if not isinstance(pass_fds, tuple) or any(
            type(fd) is not int or fd < 3 for fd in pass_fds
        ):
            raise ValueError(
                "Explicit inherited descriptors must be a tuple of nonstandard FDs"
            )
        if self._pid != os.getpid():
            raise DomainUncertain("Reopen execution domain after fork")
        with self._lock:
            self._check()
            if self._retiring.is_set():
                raise DomainUncertain("Execution domain admission withdrawn")
            # No parent environment, library injection or implicit credentials.
            environment = {} if env is None else dict(env)
            reads_writes = []
            try:
                for _ in range(3):
                    reads_writes.append(os.pipe2(os.O_CLOEXEC))
                (
                    (input_read, input_write),
                    (output_read, output_write),
                    (error_read, error_write),
                ) = reads_writes
                pid, pidfd = _domain_spawn.spawn(
                    self._fd,
                    argv,
                    environment,
                    {
                        0: input_read,
                        1: output_write,
                        2: error_write,
                        **{fd: fd for fd in pass_fds},
                    },
                )
                child = ContainedChild(pid, pidfd, input_write, output_read, error_read)
            except BaseException:
                for pair in reads_writes:
                    for fd in pair:
                        os.close(fd)
                raise
            for fd in (input_read, output_write, error_write):
                os.close(fd)
            if self._retiring.is_set():
                try:
                    self._kill()
                    child.wait(timeout=5)
                finally:
                    child.close_handles()
                raise DomainUncertain(
                    "Execution domain admission withdrawn during birth"
                )
            return child

    def _kill(self):
        # Pin/recheck before using a descriptor while another thread drains
        # startup. Never reopen a controller through an unverified numeric FD.
        """Signal cgroup.kill through a duplicated, identity-checked subtree handle; the caller must
        separately establish emptiness and removal.
        """
        pinned = os.dup(self._fd)
        try:
            info = os.fstat(pinned)
            if (info.st_dev, info.st_ino) != (
                self.identity.device,
                self.identity.inode,
            ):
                raise DomainUncertain("Execution domain handle changed")
            fd = os.open(
                "cgroup.kill", os.O_WRONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=pinned
            )
            try:
                if os.write(fd, b"1") != 1:
                    raise DomainUncertain("Domain retirement write was incomplete")
            finally:
                os.close(fd)
        finally:
            os.close(pinned)

    def retire(self, *, timeout=5):
        """Withdraw births, kill the exact subtree, retain available counters and remove only after confirmed emptiness."""
        deadline = _deadline(timeout)
        if self._pid != os.getpid():
            raise DomainUncertain("Reopen execution domain after fork")
        self._check()
        self._retiring.set()
        # Withdraw admission and stop existing actors before waiting for a
        # constructor's exec acknowledgment. Kill again if birth raced the
        # first empty observation; never block Stop behind the startup lock.
        while True:
            self._kill()
            if self._lock.acquire(timeout=0.01):
                break
            if time.monotonic() >= deadline:
                raise DomainUncertain("Execution constructors did not drain")
        try:
            self._check()
            self._kill()
            while True:
                values = dict(
                    line.split() for line in self._read("cgroup.events").splitlines()
                )
                if values.get("populated") == "0":
                    break
                if values.get("populated") != "1" or time.monotonic() >= deadline:
                    raise DomainUncertain("Domain terminal closure is unknown")
                time.sleep(0.01)
            self._check()
            # Rmdir refuses a concurrent new birth or descendant cgroup. A
            # removed cgroup FD cannot be reused by a delayed clone3 caller.
            resources = self._resource_observation()
            os.rmdir(self.path.name, dir_fd=self._parent_fd)
            self._retired = True
            return DomainClosure(self.identity, True, resources)
        finally:
            self._lock.release()
