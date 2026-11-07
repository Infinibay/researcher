"""Real kernel check profiles keep source, protected metadata, credentials and outside networking unavailable."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.tests.runtime.test_check_state import prepared_copy


@pytest.fixture
def check_profile(broker_setup):
    """Use synthetic storage identities for profile-only tests; actual candidate Git has separate end-to-end coverage."""
    from backend.runtime.candidate_state import CodeCandidates
    from backend.runtime.check_registry import CandidateCheckRegistry
    from backend.runtime.check_state import CodeChecks
    from backend.runtime.development_state import DevelopmentWorkspaces
    from backend.runtime.development_workspace import PreparedDevelopmentWorkspace
    from backend.tests.runtime.test_code_candidate_state import (
        captured_result,
        closed_proof,
    )

    s, registry, peer, broker, storage, _domain = broker_setup
    with registry.runs._transaction() as conn:
        _row, lease = registry._lease(conn, registry._row(conn, peer))
    s.c.conn.execute(
        "UPDATE runtime_runs SET execution_kind='development' WHERE id=?",
        (lease.run_id,),
    )
    s.c.conn.commit()
    root = s.control / "development"
    root.mkdir(mode=0o700, parents=True)
    copies = DevelopmentWorkspaces(s.c.store, root)
    planned, _ = copies.plan(lease)
    author = Path(planned["allocation"]) / "repository"
    author.mkdir(mode=0o700, parents=True)
    info = author.stat()
    copies.complete(
        lease,
        PreparedDevelopmentWorkspace(
            11, str(author), info.st_dev, info.st_ino, "a" * 40, "b" * 40
        ),
    )
    candidates = CodeCandidates(s.c.store)
    reservation, _ = candidates.plan(lease)
    candidates.complete(lease, captured_result(reservation), closed_proof())

    def prepare(spec):
        """Reserve and bind a host recipe to its own physical copy and the original prepared command peer."""
        checks = CodeChecks(s.c.store)
        row, _ = checks.plan(lease, "profile-check", spec)
        prepared = prepared_copy(row)
        (Path(prepared.view.workspace) / ".git").mkdir(mode=0o700)
        checks.prepared(lease, row["id"], prepared)
        checks.bind_peer(lease, row["id"], peer)
        return SimpleNamespace(
            s=s,
            lease=lease,
            checks=checks,
            row=row,
            prepared=prepared,
            registry=CandidateCheckRegistry(s.c.store, lease, row["id"]),
            peer=peer,
            broker=broker,
            storage=storage,
            spec=spec,
        )

    return prepare


async def test_check_profile_writes_only_copy_and_keeps_metadata_and_network_protected(
    check_profile,
):
    """The actual child cannot write its validation Git mount or escape through inherited directory descriptors."""
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.check_capsule import CheckEnvironment, CheckLaunch
    from backend.runtime.check_contracts import CheckSpec
    from backend.runtime.check_execution import run_check_worker

    code = """import json,os,socket,stat
from pathlib import Path
Path('output.txt').write_text('private')
blocked=False
try:Path('.git/config').write_text('unsafe')
except OSError:blocked=True
leaks=[]
for item in os.listdir('/proc/self/fd'):
 try:
  fd=int(item)
  if stat.S_ISDIR(os.fstat(fd).st_mode):
   child=os.open('escaped-write',os.O_CREAT|os.O_WRONLY,0o600,dir_fd=fd);os.close(child);leaks.append(item)
 except OSError:pass
network=False
try:socket.socket(socket.AF_INET,socket.SOCK_STREAM)
except OSError:network=True
local=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);local.bind('/tmp/check.sock');local.close()
assert blocked and network and not leaks
assert not any('API_KEY' in key or key in ('CODEX_HOME','CODEX_AUTH_FILE') for key in os.environ)
print('isolated')
"""
    import sysconfig

    environment = CheckEnvironment.capture(
        "test-python", Path(sysconfig.get_paths()["purelib"])
    )
    spec = CheckSpec(
        (str(Path(sys.executable).resolve()), "-c", code),
        "command",
        environment_id="test-python",
    )
    c = check_profile(spec)
    launch = CheckLaunch(c.row["id"], spec, c.prepared.metadata, environment)
    async with AsyncPeerBroker(c.broker) as owner:
        result = await run_check_worker(owner, c.registry, c.peer, launch)
        assert result.payload["exit_code"] == 0 and result.execution_closed
        assert result.stdout == b"isolated\n"
        assert not (Path(c.prepared.metadata.path) / "config").exists()
        assert (Path(c.prepared.view.workspace) / "output.txt").read_text() == "private"
        assert not (c.s.workspace / "output.txt").exists()


@pytest.mark.parametrize(
    "test_source,status",
    [
        ("def test_ok():\n assert True\n", "passed"),
        ("def test_bad():\n assert False\n", "failed"),
        ('import pytest\ndef test_skip():\n pytest.skip("fixture")\n', "skipped"),
        ("VALUE = 137\n", "no_tests"),
    ],
)
async def test_real_pytest_report_is_collected_inside_owned_profile(
    check_profile, test_source, status
):
    """Actual pytest results come from bounded owned report bytes, not a host-followed workspace path."""
    import sysconfig

    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.check_capsule import CheckEnvironment, CheckLaunch
    from backend.runtime.check_contracts import (
        CandidateSubject,
        CheckObservation,
        CheckSpec,
    )
    from backend.runtime.check_execution import run_check_worker
    from backend.runtime.check_results import evaluate_check

    environment = CheckEnvironment.capture(
        "test-python", Path(sysconfig.get_paths()["purelib"])
    )
    spec = CheckSpec(
        (
            str(Path(sys.executable).resolve()),
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
        ),
        "pytest",
        environment_id="test-python",
    )
    c = check_profile(spec)
    (Path(c.prepared.view.workspace) / "test_fixture.py").write_text(test_source)
    async with AsyncPeerBroker(c.broker) as owner:
        result = await run_check_worker(
            owner,
            c.registry,
            c.peer,
            CheckLaunch(c.row["id"], spec, c.prepared.metadata, environment),
        )
        subject = CandidateSubject(**json.loads(c.row["subject_json"]))
        observed = CheckObservation(
            subject,
            spec.sha256,
            result.payload["exit_code"],
            result.execution_closed,
            result.payload["output_complete"],
            True,
            result.junit_xml,
        )
        assert evaluate_check(subject, spec, observed).status == status


def test_dependency_environment_cannot_silently_fall_back_to_system(tmp_path):
    """A named dependency environment requires a real bounded package root, even with direct typed construction."""
    from backend.runtime.check_capsule import CheckEnvironment

    with pytest.raises(ValueError):
        CheckEnvironment("runtime-python")
    info = tmp_path.stat()
    with pytest.raises(ValueError):
        CheckEnvironment("broad-root", str(tmp_path), info.st_dev, info.st_ino)


async def test_non_regular_report_is_rejected_without_blocking_collector(check_profile):
    """A malicious report FIFO cannot keep the collector blocked after its command already exited."""
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.check_capsule import CheckEnvironment, CheckLaunch
    from backend.runtime.check_contracts import CheckSpec
    from backend.runtime.check_execution import run_check_worker

    spec = CheckSpec(
        (
            str(Path(sys.executable).resolve()),
            "-c",
            "import os;os.mkfifo('/tmp/researcher-check.xml')",
        ),
        "pytest",
        timeout_seconds=1,
    )
    c = check_profile(spec)
    async with AsyncPeerBroker(c.broker) as owner:
        result = await run_check_worker(
            owner,
            c.registry,
            c.peer,
            CheckLaunch(
                c.row["id"], spec, c.prepared.metadata, CheckEnvironment.system()
            ),
        )
        assert (
            result.payload["exit_code"] == 0
            and result.junit_xml is None
            and result.execution_closed
        )


async def test_command_deadline_is_durable_infrastructure_error_with_closed_peer(
    check_profile,
):
    """An actual terminated child preserves its deadline cause and closure, without inventing a successful exit."""
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.check_capsule import CheckEnvironment, CheckLaunch
    from backend.runtime.check_contracts import (
        CandidateSubject,
        CheckObservation,
        CheckSpec,
    )
    from backend.runtime.check_execution import run_check_worker

    spec = CheckSpec(
        (str(Path(sys.executable).resolve()), "-c", "import time;time.sleep(10)"),
        "command",
        timeout_seconds=0.2,
    )
    c = check_profile(spec)
    async with AsyncPeerBroker(c.broker) as owner:
        result = await run_check_worker(
            owner,
            c.registry,
            c.peer,
            CheckLaunch(
                c.row["id"], spec, c.prepared.metadata, CheckEnvironment.system()
            ),
        )
        assert (
            result.payload["error"] == "deadline_exceeded" and result.execution_closed
        )
        subject = CandidateSubject(**json.loads(c.row["subject_json"]))
        observed = CheckObservation(
            subject,
            spec.sha256,
            result.payload["exit_code"],
            True,
            result.payload["output_complete"],
            False,
        )
        ready = c.checks.complete(
            c.lease,
            c.row["id"],
            observed,
            operation_id=result.operation_id,
            stdout=result.stdout,
            stderr=result.stderr,
            collector_issue=result.payload["error"],
        )
        assert ready["state"] == "finished" and ready["issue"] == "deadline_exceeded"
        assert json.loads(ready["result_json"])["status"] == "infrastructure_error"


async def test_broken_check_command_is_infrastructure_error_not_no_tests(check_profile):
    """Absent binaries fail before launch; a broken actual pytest command yields infrastructure error with no invented tests."""
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.check_capsule import CheckEnvironment, CheckLaunch
    from backend.runtime.check_contracts import CandidateSubject, CheckObservation, CheckSpec
    from backend.runtime.check_execution import run_check_worker

    spec = CheckSpec((str(Path(sys.executable).resolve()), '-m', 'researcher_fixture_missing_test_runner'), 'pytest')
    c = check_profile(spec)
    with pytest.raises(FileNotFoundError):
        CheckLaunch(c.row['id'], CheckSpec(('/usr/bin/researcher-fixture-missing-ci-tool',), 'command'), c.prepared.metadata, CheckEnvironment.system())
    async with AsyncPeerBroker(c.broker) as owner:
        result = await run_check_worker(owner, c.registry, c.peer, CheckLaunch(c.row['id'], spec, c.prepared.metadata, CheckEnvironment.system()))
        assert result.execution_closed and result.payload['exit_code'] == 1
        subject = CandidateSubject(**json.loads(c.row['subject_json']))
        observed = CheckObservation(subject, spec.sha256, result.payload['exit_code'], result.execution_closed, result.payload['output_complete'], True)
        ready = c.checks.complete(c.lease, c.row['id'], observed, operation_id=result.operation_id, stdout=result.stdout, stderr=result.stderr, collector_issue=result.payload['error'])
        verdict = json.loads(ready['result_json'])
        assert verdict['status'] == 'infrastructure_error' and verdict['tests'] is None
        assert verdict['reason'] == 'report_absent_or_oversized'
