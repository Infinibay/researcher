"""Shared real SQLite coordination fixture; no model or external service."""

from types import SimpleNamespace

import pytest

from backend.tools.base.db import ensure_migrations


@pytest.fixture
def native_asset():
    from pathlib import Path

    from backend.runtime.broker_profile import CodexAsset

    binary = Path(
        "/home/andres/.codex/packages/standalone/releases/0.166.0-x86_64-unknown-linux-musl/bin/codex"
    )
    if not binary.is_file():
        pytest.skip("Requires the pinned Codex0.166.0 binary; no model call")
    return CodexAsset.inspect(binary)


@pytest.fixture
def coordination(_isolated_db, db_conn):
    from backend.research.sqlite_store import SQLiteResearchStore
    from backend.runtime import contracts
    from backend.runtime.sqlite_runs import SQLiteRunStore

    ensure_migrations(_isolated_db)
    db_conn.execute("INSERT INTO projects(id,name) VALUES(101,'Alpha'),(202,'Beta')")
    db_conn.execute(
        "INSERT INTO tasks(id,project_id,type,title,status) VALUES(1001,101,'research','Policy','in_progress'),(1002,101,'research','Second','pending'),(2002,202,'research','Policy','in_progress')"
    )
    db_conn.commit()
    now = [1000.0]
    store = SQLiteRunStore(_isolated_db, clock=lambda: now[0])
    spec = contracts.RunSpec(
        project_id=101,
        task_id=1001,
        actor_id="researcher-a",
        context_version=1,
        operation_key="request-1",
        prompt="Contrast source and code",
        runtime="codex",
    )
    return SimpleNamespace(
        store=store,
        spec=spec,
        now=now,
        contracts=contracts,
        conn=db_conn,
        research=SQLiteResearchStore(_isolated_db, clock=lambda: now[0]),
        database=_isolated_db,
    )


@pytest.fixture
def service_setup(coordination, tmp_path):
    c = coordination
    root = tmp_path / "workspaces"
    workspace = root / "alpha"
    workspace.mkdir(parents=True)
    c.conn.execute(
        "INSERT INTO repositories(id,project_id,name,local_path) VALUES(11,101,'alpha',?)",
        (str(workspace),),
    )
    c.conn.commit()
    return SimpleNamespace(
        c=c, root=root, workspace=workspace, control=tmp_path / "host-control"
    )


@pytest.fixture
def broker_setup(service_setup, tmp_path):
    import os
    import time
    from pathlib import Path
    from uuid import uuid4

    from backend.runtime.execution_domain import ExecutionDomain
    from backend.runtime.peer_broker import PeerBroker
    from backend.tests.runtime.authority_fixture import journal, provisioned
    from backend.tests.runtime.test_peer_workspace_view import bound_peer

    relative = Path("/proc/self/cgroup").read_text().strip().split(":", 2)[2]
    parent = (Path("/sys/fs/cgroup") / relative.lstrip("/")).parent
    if (
        not os.access(parent, os.W_OK)
        or not (parent / "cgroup.subtree_control").exists()
        or not {"memory", "pids"}
        <= set((parent / "cgroup.subtree_control").read_text().split())
    ):
        pytest.skip("Requires delegated cgroup memory/pids controllers")
    domain_path = parent / ("researcher-broker-test-" + uuid4().hex)
    domain_path.mkdir(mode=0o700)
    root = tmp_path / "global-authority"
    root.mkdir(mode=0o700)
    c = provisioned(root)
    registry, peer = bound_peer(service_setup, "command")
    domain = storage = broker = None
    try:
        domain = ExecutionDomain.open(domain_path)
        storage = journal(c)
        broker = PeerBroker(storage, domain)
        yield service_setup, registry, peer, broker, storage, domain_path
    finally:
        try:
            if broker is not None:
                broker.revoke()
        finally:
            if domain is not None:
                domain.close()
            if storage is not None:
                storage.close()
            if domain_path.exists():
                (domain_path / "cgroup.kill").write_text("1")
                deadline = time.monotonic() + 3
                while "populated 1" in (domain_path / "cgroup.events").read_text():
                    assert time.monotonic() < deadline
                    time.sleep(0.01)
                domain_path.rmdir()
