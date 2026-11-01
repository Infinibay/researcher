"""Real delegated cgroups, not enrollment of a complete production actor domain."""

import fcntl
import json
import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest


@pytest.fixture
def private_cgroup():
    relative = Path("/proc/self/cgroup").read_text().strip().split(":", 2)[2]
    parent = Path("/sys/fs/cgroup") / relative.lstrip("/")
    if not os.access(parent, os.W_OK):
        pytest.skip("Requires a writable delegated cgroup for real containment tests")
    path = parent / ("researcher-test-" + uuid4().hex)
    path.mkdir(mode=0o700)
    try:
        yield path
    finally:
        # Only this freshly created exact child, never the test runner's cgroup.
        if path.exists():
            (path / "cgroup.kill").write_text("1")
            deadline = time.monotonic() + 3
            while "populated 1" in (path / "cgroup.events").read_text():
                assert time.monotonic() < deadline
                time.sleep(0.01)
            path.rmdir()


def test_child_is_born_inside_domain_and_unlisted_descendant_is_retired(
    private_cgroup, tmp_path
):
    from backend.runtime.execution_domain import ExecutionDomain

    marker, permit, late = (tmp_path / n for n in ("heartbeat", "permit", "late"))
    code = """import os,sys,time
from pathlib import Path
print(Path('/proc/self/cgroup').read_text().strip(),flush=True)
if os.fork()==0:
 os.setsid()
 while not Path(sys.argv[2]).exists():
  Path(sys.argv[1]).write_text(str(time.monotonic_ns()))
  time.sleep(.01)
 Path(sys.argv[3]).write_text('escaped')
 os._exit(0)
time.sleep(30)
"""
    with ExecutionDomain.open(private_cgroup) as domain:
        identity = domain.identity
        child = domain.spawn(
            [
                sys.executable,
                "-I",
                "-S",
                "-c",
                code,
                str(marker),
                str(permit),
                str(late),
            ]
        )
        try:
            assert select.select([child.stdout], [], [], 3)[0]
            assert (
                child.stdout.readline()
                .decode()
                .strip()
                .endswith("/" + private_cgroup.name)
            )
            deadline = time.monotonic() + 3
            while not marker.exists():
                assert time.monotonic() < deadline
                time.sleep(0.01)
            # A new observer only knows the domain; no namespace/child PID or project DB.
            with ExecutionDomain.open(private_cgroup, expected=identity) as recovery:
                proof = recovery.retire(timeout=3)
            assert proof.removed and proof.identity == identity
            permit.touch()
            time.sleep(0.1)
            assert not late.exists()
            assert child.wait(timeout=3) == -9
        finally:
            child.close_handles()


def test_removed_domain_fd_cannot_create_a_late_actor(private_cgroup, tmp_path):
    from backend.runtime import _domain_spawn
    from backend.runtime.execution_domain import ExecutionDomain

    descriptor = os.open(private_cgroup, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        with ExecutionDomain.open(private_cgroup) as domain:
            domain.retire()
        marker = tmp_path / "late"
        with pytest.raises(OSError):
            _domain_spawn.spawn(
                descriptor,
                [
                    sys.executable,
                    "-I",
                    "-S",
                    "-c",
                    f"from pathlib import Path;Path({str(marker)!r}).touch()",
                ],
                {},
                {0: 0, 1: 1, 2: 2},
            )
        assert not marker.exists()
    finally:
        os.close(descriptor)


def test_native_spawn_exec_failure_is_reaped_and_does_not_populate_domain(
    private_cgroup,
):
    from backend.runtime.execution_domain import ExecutionDomain

    with ExecutionDomain.open(private_cgroup) as domain:
        with pytest.raises(OSError):
            domain.spawn(["/definitely-not-a-trusted-executable"])
        assert "populated 0" in (private_cgroup / "cgroup.events").read_text()
        assert domain.retire().removed


def test_filesystem_directory_cannot_impersonate_a_cgroup(tmp_path):
    from backend.runtime.execution_domain import DomainUncertain, ExecutionDomain

    (tmp_path / "cgroup.type").write_text("domain\n")
    (tmp_path / "cgroup.events").write_text("populated 0\n")
    with pytest.raises(DomainUncertain):
        ExecutionDomain.open(tmp_path)


def test_child_drops_inherited_secret_fds_environment_and_normalizes_signals(
    private_cgroup, tmp_path
):
    from backend.runtime.execution_domain import ExecutionDomain

    secret = tmp_path / "secret"
    secret.write_text("not for the actor")
    with secret.open("rb") as handle, ExecutionDomain.open(private_cgroup) as domain:
        os.set_inheritable(handle.fileno(), True)
        code = """import json,os,signal
from pathlib import Path
fds={}
for p in Path('/proc/self/fd').iterdir():
 try:fds[p.name]=os.readlink(p)
 except FileNotFoundError:pass
print(json.dumps({'env':dict(os.environ),'fds':fds,'mask':list(signal.pthread_sigmask(signal.SIG_BLOCK,[])),'sigterm':signal.getsignal(signal.SIGTERM)}))
"""
        old_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1})
        old_term = signal.signal(signal.SIGTERM, signal.SIG_IGN)
        try:
            child = domain.spawn(
                [sys.executable, "-I", "-S", "-c", code],
                env={"LANG": "C.UTF-8", "DECLARED": "yes"},
            )
            assert signal.SIGUSR1 in signal.pthread_sigmask(signal.SIG_BLOCK, [])
            assert signal.getsignal(signal.SIGTERM) == signal.SIG_IGN
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
            signal.signal(signal.SIGTERM, old_term)
        try:
            assert child.wait(timeout=3) == 0
            data = json.loads(child.stdout.read())
            assert data["env"] == {"LANG": "C.UTF-8", "DECLARED": "yes"}
            assert str(secret) not in data["fds"].values()
            assert {"0", "1", "2"} <= set(data["fds"]), data
            assert data["mask"] == [] and data["sigterm"] == 0
        finally:
            child.close_handles()
        assert domain.retire().removed


@pytest.mark.parametrize("ancestor", [False, True])
def test_own_cgroup_and_ancestor_are_rejected_without_control_writes(ancestor):
    from backend.runtime.execution_domain import DomainUncertain, ExecutionDomain

    relative = Path("/proc/self/cgroup").read_text().strip().split(":", 2)[2]
    path = Path("/sys/fs/cgroup") / relative.lstrip("/")
    if ancestor:
        path = path.parent
    with pytest.raises(DomainUncertain), ExecutionDomain.open(path):
        pass


def test_other_process_recovers_spawn_before_peer_publication_without_project_database(
    coordination, private_cgroup, tmp_path
):
    from backend.tests.runtime.authority_fixture import journal, provisioned

    authority_root = tmp_path / "global"
    authority_root.mkdir(mode=0o700)
    c = provisioned(authority_root)
    command = [
        sys.executable,
        "-I",
        str(Path(__file__).with_name("fake_domain_broker.py")),
    ]
    for name in ("database", "witness", "mutex", "authority_id"):
        command.extend(["--" + name.replace("_", "-"), str(getattr(c, name))])
    heartbeat, permit, late = (tmp_path / n for n in ("heartbeat", "permit", "late"))
    broker = subprocess.Popen(
        [
            *command,
            "--domain",
            str(private_cgroup),
            "--heartbeat",
            str(heartbeat),
            "--permit",
            str(permit),
            "--late",
            str(late),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={"LANG": "C.UTF-8", "PATH": os.defpath},
    )
    try:
        assert select.select([broker.stdout], [], [], 5)[0]
        assert broker.stdout.readline() == b"BORN-BEFORE-PUBLICATION\n"
        with journal(c) as j:
            record = j.load().records["domain"]
            assert record["state"] == "starting" and record["published_peers"] == []
        coordination.conn.close()
        source = Path(coordination.database)
        source.unlink()
        broker.stdin.write(b"crash\n")
        broker.stdin.flush()
        broker.communicate(timeout=5)

        assert broker.returncode == -signal.SIGKILL
        deadline = time.monotonic() + 3
        while not heartbeat.exists():
            assert time.monotonic() < deadline
            time.sleep(0.01)
        before = heartbeat.stat().st_mtime_ns
        while heartbeat.stat().st_mtime_ns == before:
            assert time.monotonic() < deadline
            time.sleep(0.01)
        result = subprocess.run(
            [*command, "--recover"],
            capture_output=True,
            env={"LANG": "C.UTF-8", "PATH": os.defpath},
            timeout=8,
            check=False,
        )
        assert result.returncode == 0, result.stderr.decode()
        assert json.loads(result.stdout)["removed"]
        assert not private_cgroup.exists() and not source.exists()
        permit.touch()
        time.sleep(0.1)
        assert not late.exists()
        with journal(c) as j:
            assert j.load().records["domain"]["state"] == "retired"
    finally:
        if broker.poll() is None:
            broker.kill()
        broker.communicate(timeout=5)


def test_fd_remap_cycle_uses_original_sources_and_keeps_parent_fds(private_cgroup):
    from backend.runtime import _domain_spawn

    pairs = [os.pipe2(os.O_CLOEXEC) for _ in range(2)]
    (read_one, write_one), (read_two, write_two) = pairs
    group_fd = os.open(private_cgroup, os.O_RDONLY | os.O_DIRECTORY)
    pid = pidfd = None
    with open(os.devnull, "r+b", buffering=0) as null:
        try:
            code = (
                f"import os;os.write({write_one},b'TWO');os.write({write_two},b'ONE')"
            )
            pid, pidfd = _domain_spawn.spawn(
                group_fd,
                [sys.executable, "-I", "-S", "-c", code],
                {"LANG": "C.UTF-8"},
                {
                    0: null.fileno(),
                    1: null.fileno(),
                    2: null.fileno(),
                    write_one: write_two,
                    write_two: write_one,
                },
            )
            assert select.select([read_one], [], [], 3)[0]
            assert os.read(read_one, 3) == b"ONE"
            assert select.select([read_two], [], [], 3)[0]
            assert os.read(read_two, 3) == b"TWO"
            assert os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1]) == 0
            pid = None
            os.fstat(write_one)
            os.fstat(write_two)
        finally:
            if pid is not None:
                (private_cgroup / "cgroup.kill").write_text("1")
                os.waitpid(pid, 0)
            if pidfd is not None:
                os.close(pidfd)
            os.close(group_fd)
            for pair in pairs:
                for fd in pair:
                    os.close(fd)


def test_failed_fd_preparation_does_not_close_any_callers_descriptor(private_cgroup):
    from backend.runtime import _domain_spawn

    group_fd = os.open(private_cgroup, os.O_RDONLY | os.O_DIRECTORY)
    with open(os.devnull, "r+b", buffering=0) as handle:
        sentinel = fcntl.fcntl(handle.fileno(), fcntl.F_DUPFD_CLOEXEC, 200)
        try:
            with pytest.raises(OSError):
                _domain_spawn.spawn(
                    group_fd,
                    [sys.executable],
                    {},
                    {0: sentinel, 1: sentinel, 2: sentinel, 10: 2**30, 11: sentinel},
                )
            assert os.fstat(sentinel).st_rdev == os.fstat(handle.fileno()).st_rdev
            assert "populated 0" in (private_cgroup / "cgroup.events").read_text()
        finally:
            os.close(sentinel)
            os.close(group_fd)


def test_partial_pipe_allocation_failure_closes_owned_fds_without_spawning(
    private_cgroup, monkeypatch
):
    from backend.runtime import execution_domain

    real_pipe = os.pipe2
    allocated = []

    def exhausted(flags):
        if allocated:
            raise OSError(24, "synthetic descriptor capacity exhausted")
        pair = real_pipe(flags)
        allocated.append(pair)
        return pair

    with execution_domain.ExecutionDomain.open(private_cgroup) as domain:
        with monkeypatch.context() as patch:
            patch.setattr(execution_domain.os, "pipe2", exhausted)
            with pytest.raises(OSError):
                domain.spawn([sys.executable])
        for fd in allocated[0]:
            with pytest.raises(OSError):
                os.fstat(fd)
        assert "populated 0" in (private_cgroup / "cgroup.events").read_text()


def test_retirement_interrupts_birth_frozen_before_exec_without_waiting_on_spawn_lock(
    private_cgroup, tmp_path
):
    from concurrent.futures import ThreadPoolExecutor

    from backend.runtime.execution_domain import DomainUncertain, ExecutionDomain

    marker = tmp_path / "should-not-execute"
    freeze = private_cgroup / "cgroup.freeze"
    freeze.write_text("1")
    with ExecutionDomain.open(private_cgroup) as domain, ThreadPoolExecutor(2) as pool:
        startup = pool.submit(
            domain.spawn,
            [
                sys.executable,
                "-I",
                "-S",
                "-c",
                f"from pathlib import Path;Path({str(marker)!r}).touch()",
            ],
        )
        stopping = None
        try:
            deadline = time.monotonic() + 3
            while "populated 1" not in (private_cgroup / "cgroup.events").read_text():
                assert time.monotonic() < deadline
                time.sleep(0.01)
            stopping = pool.submit(domain.retire, timeout=2)
            assert stopping.result(timeout=1).removed
            with pytest.raises(DomainUncertain):
                startup.result(timeout=2)
            assert not marker.exists()
        finally:
            if freeze.exists():
                freeze.write_text("0")
            try:
                child = startup.result(timeout=3)
            except DomainUncertain:
                pass
            else:
                try:
                    child.wait(timeout=3)
                finally:
                    child.close_handles()
            if stopping is not None:
                stopping.result(timeout=3)


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), -1, True])
def test_invalid_retirement_deadline_rejected_before_kernel_writes(
    private_cgroup, timeout
):
    from backend.runtime.execution_domain import ExecutionDomain

    with ExecutionDomain.open(private_cgroup) as domain:
        with pytest.raises(ValueError):
            domain.retire(timeout=timeout)
        assert private_cgroup.exists()
