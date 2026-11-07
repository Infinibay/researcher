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
def code_host_asset():
    from pathlib import Path

    from backend.runtime.broker_profile import CodexAsset

    binary = Path(
        "/home/andres/.codex/packages/standalone/releases/0.166.0-x86_64-unknown-linux-musl/bin/codex-code-mode-host"
    )
    if not binary.is_file():
        pytest.skip("Requires the pinned0.166.0 code-mode host; no model call")
    return CodexAsset.inspect(binary)


@pytest.fixture
def schema_target():
    """Default fixtures to current schema; historical tests explicitly select a forward prefix."""
    return None


@pytest.fixture
def coordination(_isolated_db, db_conn, schema_target):
    """Seed real scoped coordination storage at the explicitly selected supported schema version."""
    from backend.research.sqlite_store import SQLiteResearchStore
    from backend.runtime import contracts
    from backend.runtime.sqlite_runs import SQLiteRunStore

    ensure_migrations(_isolated_db, target_version=schema_target)
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


@pytest.fixture
def ken_installation(tmp_path):
    import sys
    import venv

    tool = tmp_path / "tool"
    venv.EnvBuilder(with_pip=False, symlinks=True).create(tool)
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    packages = tool / "lib" / version / "site-packages"
    metadata = packages / "ken_rank-0.18.0.dist-info"
    metadata.mkdir(parents=True)
    (metadata / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: ken-rank\nVersion: 0.18.0\n"
    )
    package = packages / "ken"
    package.mkdir()
    (package / "__init__.py").write_text("")
    executable = tool / "bin/ken"
    executable.write_text(
        "#!"
        + str(tool / "bin/python")
        + "\n"
        + """
import json, os, socket, sys
from pathlib import Path
root=Path(sys.argv[2])
result={"inside":(root/"source.py").read_text(),"credentials_present":[key for key in os.environ if key in {"OPENAI_API_KEY","RESEARCHER_TOOL_TOKEN","HF_TOKEN","CODEX_HOME"}]}
try: result["outside"]=(root/"escape.py").read_text()
except OSError: result["outside"]="denied"
try: (root/"source.py").write_text("unwanted")
except OSError: result["source_write"]="denied"
(root/".ken/worker-note").write_text("retained")
try: socket.create_connection(("127.0.0.1",int((root/".ken/fixture-port").read_text())),timeout=.1); result["network"]="available"
except OSError: result["network"]="unavailable"
result["leaked_handle_reads"]=[]
for fd in range(3,128):
    try: result["leaked_handle_reads"].append(Path(f"/proc/self/fd/{fd}/../owner.key").read_text())
    except OSError: pass
result["home"]=os.environ["HOME"]
print(json.dumps(result))
"""
    )
    executable.chmod(0o755)
    return executable
