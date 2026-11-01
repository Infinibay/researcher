"""Explicit real native command integration; zero model turns or provider keys."""

import argparse
import asyncio
import json
import shutil
import sqlite3
import sys
import time
from contextlib import AsyncExitStack
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


async def main(args):
    from backend.runtime.contracts import CommandSpec, RunSpec
    from backend.runtime.native_commands import command_executor
    from backend.runtime.peer_registry import AttemptPeers
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.tools.base.db import ensure_migrations

    root = (
        REPO / ".researcher/evaluations" / ("command-integration-" + uuid4().hex[:8])
    ).resolve()
    root.mkdir(parents=True)
    database = root / "research.db"
    ensure_migrations(str(database))
    alpha, beta = root / "alpha", root / "beta"
    for directory, value in [(alpha, "ALPHA_ONLY"), (beta, "BETA_ONLY")]:
        directory.mkdir()
        (directory / "private.txt").write_text(value)
    # Workspace-local configuration must not broaden the command peer's scope.
    (alpha / ".codex").mkdir()
    (alpha / ".codex/config.toml").write_text(
        "[permissions.researcher_jobs.filesystem]\n"
        + json.dumps(str(beta))
        + ' = "read"\n[permissions.researcher_jobs.network]\nenabled = true\n'
    )
    with sqlite3.connect(database) as conn:
        conn.execute("INSERT INTO projects(id,name) VALUES(101,'Alpha'),(202,'Beta')")
        conn.execute(
            "INSERT INTO tasks(id,project_id,type,title,status) VALUES(1001,101,'research','Commands','in_progress'),(2002,202,'research','Commands','in_progress')"
        )
    store = SQLiteRunStore(database)
    run_a = store.admit(
        RunSpec(101, 1001, "worker-a", 1, "request-a", "Command integration", "codex")
    )
    run_b = store.admit(
        RunSpec(202, 2002, "worker-b", 1, "request-b", "Command integration", "codex")
    )
    lease_a, peers_a = AttemptPeers.claim(
        store, 101, run_a.run_id, "owner-a", lease_seconds=120
    )
    lease_b, peers_b = AttemptPeers.claim(
        store, 202, run_b.run_id, "owner-b", lease_seconds=120
    )
    results = {"model_turns_submitted": 0, "root": str(root), "commands": []}
    print("Command integration:", root, flush=True)
    try:
        async with (
            AsyncExitStack() as replacements,
            command_executor(
                journal=store,
                lease=lease_a,
                workspace=alpha,
                control_root=root / "controls",
                codex_binary=Path(args.codex_binary),
            ) as worker_a,
            command_executor(
                journal=store,
                lease=lease_b,
                workspace=beta,
                control_root=root / "controls",
                codex_binary=Path(args.codex_binary),
            ) as worker_b,
        ):
            for worker, lease, key, argv in [
                (worker_a, lease_a, "inside", ("/bin/cat", str(alpha / "private.txt"))),
                (worker_b, lease_b, "inside", ("/bin/cat", str(beta / "private.txt"))),
                (worker_a, lease_a, "outside", ("/bin/cat", str(beta / "private.txt"))),
                (
                    worker_a,
                    lease_a,
                    "network",
                    ("/usr/bin/python3", "-c", "import socket; socket.socket()"),
                ),
            ]:
                handle = await worker.start(lease, key, CommandSpec(argv))
                result = await handle.wait()
                results["commands"].append(
                    {
                        "key": key,
                        "project_id": lease.project_id,
                        "job_id": handle.job_id,
                        "status": result.status,
                        "exit_code": result.exit_code,
                        "stdout": result.stdout.decode(errors="replace"),
                        "stderr": result.stderr.decode(errors="replace"),
                    }
                )
            assert results["commands"][0]["stdout"] == "ALPHA_ONLY"
            assert results["commands"][1]["stdout"] == "BETA_ONLY"
            assert (
                results["commands"][2]["exit_code"] != 0
                and "BETA_ONLY" not in results["commands"][2]["stdout"]
            )
            assert "PermissionError" in results["commands"][3]["stderr"]
            if args.db_contention:
                blocked = await worker_a.start(
                    lease_a,
                    "busy-database",
                    CommandSpec(
                        (
                            "/usr/bin/python3",
                            "-c",
                            "from pathlib import Path; import time; Path('busy-started').write_text('yes'); time.sleep(0.6); Path('busy-delayed').write_text('must not happen')",
                        )
                    ),
                )
                async with asyncio.timeout(3):
                    while not (alpha / "busy-started").exists():
                        await asyncio.sleep(0.02)
                lock = sqlite3.connect(database)
                lock.execute("BEGIN IMMEDIATE")
                cancellation = asyncio.create_task(blocked.cancel())
                try:
                    await asyncio.sleep(0.8)
                    assert not (alpha / "busy-delayed").exists()
                finally:
                    lock.rollback()
                    lock.close()
                persisted = await asyncio.wait_for(cancellation, 3)
                assert (
                    persisted.status == "exited"
                    and persisted.exit_code != 0
                    and persisted.cancel_requested
                )
                results["database_contention"] = {
                    "physical_stop_preceded_database_unlock": True,
                    "exit_code": persisted.exit_code,
                    "cancellation_intent_persisted": True,
                }
                worker_a = await replacements.enter_async_context(
                    command_executor(
                        journal=store,
                        lease=lease_a,
                        workspace=alpha,
                        control_root=root / "controls",
                        codex_binary=Path(args.codex_binary),
                    )
                )
            child = "from pathlib import Path; import time; Path('child-started').write_text('yes'); time.sleep(2); Path('delayed').write_text('must not happen')"
            parent = (
                "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',"
                + repr(child)
                + "],start_new_session=True); time.sleep(10)"
            )
            a = await worker_a.start(
                lease_a,
                "cancel-detached",
                CommandSpec(("/usr/bin/python3", "-c", parent)),
            )
            b = await worker_b.start(
                lease_b,
                "other-owner",
                CommandSpec(
                    (
                        "/usr/bin/python3",
                        "-c",
                        "from pathlib import Path; import time; Path('other-started').write_text('yes'); time.sleep(0.5); Path('other-complete').write_text('yes')",
                    )
                ),
            )
            async with asyncio.timeout(3):
                while (
                    not (alpha / "child-started").exists()
                    or not (beta / "other-started").exists()
                ):
                    await asyncio.sleep(0.02)
            started = time.monotonic()
            await asyncio.to_thread(store.cancel, 101, run_a.run_id)
            stopped = await asyncio.wait_for(a.wait(), 3)
            stop_seconds = time.monotonic() - started
            untouched = await b.wait()
            assert (
                stopped.status == "exited"
                and stopped.exit_code != 0
                and stopped.cancel_requested
            )
            assert untouched.exit_code == 0 and not untouched.cancel_requested
            results["stop"] = {
                "seconds": stop_seconds,
                "job_id": a.job_id,
                "exit_code": stopped.exit_code,
                "other_job_exit_code": untouched.exit_code,
            }
            if args.peer_loss:
                from backend.research.models import ResearchForbidden
                from backend.research.sqlite_store import SQLiteResearchStore

                research = SQLiteResearchStore(database)
                token = research.issue_grant(
                    project_id=202,
                    task_id=2002,
                    agent_id="worker-b",
                    permissions={"sources.read", "sources.capture"},
                )
                store.bind_grant(lease_b, research.authorize(token).grant_id)
                loss_child = "from pathlib import Path; import time; Path('loss-started').write_text('yes'); time.sleep(2); Path('loss-delayed').write_text('must not happen')"
                loss_parent = (
                    "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',"
                    + repr(loss_child)
                    + "],start_new_session=True); time.sleep(10)"
                )
                loss = await worker_b.start(
                    lease_b,
                    "connection-loss",
                    CommandSpec(("/usr/bin/python3", "-c", loss_parent)),
                )
                async with asyncio.timeout(3):
                    while not (beta / "loss-started").exists():
                        await asyncio.sleep(0.02)
                # This is the local child handle we created, never a PID reported
                # by a shell in another namespace.
                worker_b.rpc._process.kill()
                uncertain = await asyncio.wait_for(loss.wait(), 3)
                assert uncertain.status == "unknown" and uncertain.exit_code is None
                assert store.get(202, run_b.run_id).status == "reconciling"
                try:
                    research.authorize(token)
                except ResearchForbidden:
                    pass
                else:
                    raise AssertionError(
                        "Lost command connection retained its business grant"
                    )
                results["peer_loss"] = {
                    "job_id": loss.job_id,
                    "status": uncertain.status,
                    "run_status": "reconciling",
                    "business_grant_revoked": True,
                }
        await peers_a.aclose()
        await peers_b.aclose()
        results["all_registered_peers_closed"] = peers_a.closed() and peers_b.closed()
        assert results["all_registered_peers_closed"]
        await asyncio.sleep(2.1)
        assert not (alpha / "delayed").exists()
        assert (beta / "other-complete").read_text() == "yes"
        if args.peer_loss:
            assert not (beta / "loss-delayed").exists()
            results["peer_loss"]["detached_delayed_effect_present"] = False
        results["detached_child_confirmed_started"] = True
        results["delayed_effect_present"] = False
        results["other_owner_effect_preserved"] = True
        results["status"] = "passed"
    except BaseException as exc:
        results.update(status="failed", error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        (root / "result.json").write_text(json.dumps(results, indent=2))
    print(
        json.dumps({"status": results["status"], "model_turns_submitted": 0}),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--peer-loss", action="store_true")
    parser.add_argument("--db-contention", action="store_true")
    parser.add_argument(
        "--codex-binary",
        default=shutil.which("codex"),
        required=shutil.which("codex") is None,
    )
    asyncio.run(main(parser.parse_args()))
