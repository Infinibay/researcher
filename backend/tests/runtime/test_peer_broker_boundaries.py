"""Real contention and descendant pressure over the analysis broker profile."""

import json
import logging
import select
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest


def test_startup_log_preserves_private_failure_origin_after_physical_close_and_withdrawal(broker_setup, monkeypatch, caplog):
    """A withdrawn real pre-gate namespace retains safe original diagnostics before its public conflict suppresses that cause."""
    from backend.runtime.authority_journal import AuthorityConflict

    _source, registry, peer, broker, storage, path = broker_setup
    private = '/private/synthetic-account.json synthetic-secret-do-not-log'
    observed = []
    logger = logging.getLogger('backend.runtime.peer_broker')
    warning = logger.warning

    def record_warning(*args, **kwargs):
        """Require physical retirement before operator logging can perform any I/O."""
        observed.append({'domain_present': path.exists(), 'args': args})
        return warning(*args, **kwargs)

    def interrupted_namespace(_descriptor):
        """Inject an original namespace observation failure alongside a real owner withdrawal, before any gate is sent."""
        broker.withdraw()
        raise OSError(private)

    monkeypatch.setattr(logger, 'warning', record_warning)
    monkeypatch.setattr(broker, '_info', interrupted_namespace)
    with caplog.at_level(logging.WARNING, logger='backend.runtime.peer_broker'):
        with pytest.raises(AuthorityConflict) as caught:
            broker.run_peer(registry, peer, operation_key='withdrawn-startup-failure', code="print('MUST NOT RUN')")
    assert caught.value.__suppress_context__ is True
    assert len(observed) == 1 and observed[0]['domain_present'] is False
    record, = [record for record in caplog.records if record.name == 'backend.runtime.peer_broker']
    assert record.args[0:2] == ('command', 'namespace_observation')
    assert record.args[2][0]['type'] == 'OSError'
    assert record.args[2][0]['sites'] and len(record.args[2][0]['sites']) <= 4
    assert record.exc_info is None and private not in caplog.text
    assert broker.revoke()['state'] == 'retired'
    snapshot = storage.load()
    operations = [value for key, value in snapshot.records.items() if key.startswith('broker:op:')]
    assert len(operations) == 1 and operations[0]['gate_sent'] is False


def test_operator_log_failure_cannot_replace_startup_error_or_delay_physical_close(broker_setup, monkeypatch):
    """An unavailable log sink preserves the original startup exception and observes a closed real pre-gate domain."""
    from backend.runtime.peer_broker import logger

    _source, registry, peer, broker, _storage, path = broker_setup
    observed = []

    def failed_namespace(_descriptor):
        """Fail before native code can receive a gate; the error message is synthetic and private."""
        raise OSError('private synthetic namespace observation')

    def failed_log(*_arguments, **_keywords):
        """Simulate a broken operator sink after physical retirement instead of granting logging authority over Stop."""
        observed.append(path.exists())
        raise RuntimeError('operator sink unavailable')

    monkeypatch.setattr(broker, '_info', failed_namespace)
    monkeypatch.setattr(logger, 'warning', failed_log)
    with pytest.raises(OSError, match='private synthetic namespace observation'):
        broker.run_peer(registry, peer, operation_key='unavailable-startup-log', code="print('MUST NOT RUN')")
    assert observed == [False]
    assert broker.revoke()['state'] == 'retired'


def test_two_databases_on_same_source_cannot_hold_global_concession(
    broker_setup, tmp_path
):
    from backend.runtime.authority_journal import AuthorityConflict
    from backend.runtime.contracts import RunSpec
    from backend.runtime.execution_domain import ExecutionDomain
    from backend.runtime.peer_broker import PeerBroker
    from backend.runtime.peer_registry import AttemptPeers
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.runtime.workspaces import WorkspaceRegistry
    from backend.tools.base.db import ensure_migrations

    s, registry, peer, broker, storage, path = broker_setup
    other = tmp_path / "second-project.db"
    with sqlite3.connect(other) as conn:
        conn.executescript((Path(__file__).parents[2] / "db/schema.sql").read_text())
    ensure_migrations(str(other))
    with sqlite3.connect(other) as conn:
        conn.execute("INSERT INTO projects(id,name) VALUES(101,'Other authority DB')")
        conn.execute(
            "INSERT INTO tasks(id,project_id,type,title,status) VALUES(1001,101,'research','Other','in_progress')"
        )
        conn.execute(
            "INSERT INTO repositories(id,project_id,name,local_path) VALUES(11,101,'same-physical-source',?)",
            (str(s.workspace),),
        )
    store = SQLiteRunStore(other)
    binding = WorkspaceRegistry(other, s.root).bind(101, 11)
    spec = RunSpec(
        101, 1001, "other-agent", 1, "other-request", "Other source request", "codex"
    )
    run = store.admit(spec, binding=binding)
    lease, peers = AttemptPeers.claim(
        store, 101, run.run_id, "other-owner", lease_seconds=120
    )
    other_peer = peers.registry.prepare(lease, "command")
    other_path = path.parent / ("researcher-broker-test-" + uuid4().hex)
    other_path.mkdir(mode=0o700)
    with ExecutionDomain.open(other_path) as other_domain:
        second = PeerBroker(storage, other_domain)
        started = broker.run_peer(
            registry,
            peer,
            operation_key="first-db",
            code="print('READY',flush=True);input();print('UNAFFECTED',flush=True)",
        )
        try:
            assert started.child.stdout.readline() == b"READY\n"
            assert (
                peers.registry.inspect(other_peer)["database_identity"]
                != registry.inspect(peer)["database_identity"]
            )
            with pytest.raises(AuthorityConflict):
                second.run_peer(
                    peers.registry,
                    other_peer,
                    operation_key="other-db",
                    code="print('MUST NOT START')",
                )
            assert "populated 0" in (other_path / "cgroup.events").read_text()
            assert storage.load().records["broker:active"] == broker.grant_id
            started.child.stdin.write(b"continue\n")
            assert started.child.stdout.readline() == b"UNAFFECTED\n"
            assert started.child.wait(timeout=3) == 0
        finally:
            second.revoke()
            started.child.close_handles()


def test_analysis_forks_hit_private_pid_limit_and_all_descendants_close(broker_setup):
    _s, registry, peer, broker, _storage, path = broker_setup
    code = """import json,os,time
made=0
while made<256:
 try:pid=os.fork()
 except OSError:
  print(json.dumps({'fork_denied':True,'children':made}),flush=True)
  break
 if pid==0:
  time.sleep(30)
  os._exit(0)
 made+=1
time.sleep(30)
"""
    started = broker.run_peer(registry, peer, operation_key="fork-pressure", code=code)
    assert select.select([started.child.stdout], [], [], 5)[0]
    result = json.loads(started.child.stdout.readline())
    assert result["fork_denied"] and 0 < result["children"] < 128
    assert int((path / "pids.current").read_text()) <= 128
    assert (path / "memory.max").read_text().strip() == "536870912"
    assert broker.revoke()["state"] == "retired"
    assert not path.exists()


def test_retired_attempt_cannot_reactivate_in_fresh_domain_with_old_local_lease(
    broker_setup,
):
    from backend.runtime.authority_journal import AuthorityConflict
    from backend.runtime.execution_domain import ExecutionDomain
    from backend.runtime.peer_broker import PeerBroker

    _s, registry, peer, broker, storage, path = broker_setup
    started = broker.run_peer(
        registry, peer, operation_key="original", code="print('original')"
    )
    assert started.child.wait(timeout=3) == 0
    started.child.close_handles()
    broker.revoke()
    # The local DB still admits that original fence. A global retirement must
    # block resurrection even before its local Stop projection is persisted.
    with registry.runs._transaction() as conn:
        _, lease = registry._lease(conn, registry.inspect(peer))
    another = registry.prepare(lease, "command")
    fresh_path = path.parent / ("researcher-broker-test-" + uuid4().hex)
    fresh_path.mkdir(mode=0o700)
    with ExecutionDomain.open(fresh_path) as domain:
        stale = PeerBroker(storage, domain)
        try:
            with pytest.raises(AuthorityConflict):
                stale.run_peer(
                    registry,
                    another,
                    operation_key="old-fence",
                    code="print('MUST NOT REACTIVATE')",
                )
            assert "populated 0" in (fresh_path / "cgroup.events").read_text()
        finally:
            stale.revoke()
