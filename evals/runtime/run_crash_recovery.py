"""Kill an owned native holder, reopen the same DB and recover via owner HTTP.

No turn/start, no generation, no metered fallback. Actual managed Codex, business
MCP and mandatory published Ken run in their recorded gated namespaces.
"""

import argparse
import asyncio
import json
import os
import sys
from contextlib import closing
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


async def holder(root):
    from backend.api.runtime_dependencies import configured_runtime
    from backend.runtime.contracts import RunSpec
    from backend.runtime.live_grants import LiveGrants
    from backend.runtime.peer_registry import AttemptPeers

    os.environ["INFINIBAY_DB"] = str(root / "research.db")
    os.environ["INFINIBAY_RUNTIME_CONFIG"] = str(root / "holder-settings.json")
    service = configured_runtime(LiveGrants())
    async with service:
        run = service.store.admit(
            RunSpec(
                101,
                1001,
                "researcher",
                1,
                "before-crash",
                "Read native metadata without starting a turn",
                "codex",
            )
        )
        lease, peers = AttemptPeers.claim(
            service.store, 101, run.run_id, service.owner_id, lease_seconds=120
        )
        token = service.research.issue_grant(
            project_id=101,
            task_id=1001,
            agent_id="researcher",
            permissions={"sources.read"},
        )
        scope = service.research.authorize(token)
        service.store.bind_grant(lease, scope.grant_id)
        # No tool call is made against the deliberately inactive API. The real
        # MCP initializes/catalogs; the grant remains bound and is revoked at recovery.
        async with service.runtime.open(
            workspace=service.workspaces.select(101), tool_token=token, peer_owner=peers
        ) as session:
            service.store.bind_thread(lease, thread_id=session.thread_id)
            assert session.native.turns_sent == 0
            ready = {
                "run_id": run.run_id,
                "attempt_id": lease.attempt_id,
                "model": session.model,
                "native_turns_sent": session.native.turns_sent,
            }
            temporary = root / "ready.tmp"
            temporary.write_text(json.dumps(ready))
            temporary.replace(root / "ready.json")
            await asyncio.Event().wait()


async def main(args):
    from backend.db.connection import connect
    from backend.tools.base.db import ensure_migrations
    from evals.runtime.run_research import backend, environment, terminate

    root = REPO / ".researcher/evaluations" / ("crash-recovery-" + uuid4().hex[:8])
    root.mkdir(parents=True)
    (root / "uploads").mkdir()
    database = root / "research.db"
    ensure_migrations(str(database))
    workspace = Path(args.workspace).resolve(strict=True)
    with closing(connect(str(database))) as conn, conn:
        conn.execute("INSERT INTO projects(id,name) VALUES(101,'Recovery fixture')")
        conn.execute(
            "INSERT INTO tasks(id,project_id,type,title,status) VALUES(1001,101,'research','Recovery','in_progress')"
        )
        conn.execute(
            "INSERT INTO repositories(project_id,name,local_path) VALUES(101,'alpha',?)",
            (str(workspace),),
        )
    settings = json.loads(Path(args.config).read_text())
    settings.update(
        control_root=str(root / "holder-control"), api_url="http://127.0.0.1:1"
    )
    (root / "holder-settings.json").write_text(json.dumps(settings))
    evidence = {"status": "starting", "model_turns_submitted": 0}
    print("Crash recovery:", root, flush=True)
    log = (root / "holder.log").open("w")
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(Path(__file__).resolve()),
        "--holder",
        str(root),
        cwd=REPO,
        env=environment(),
        stdout=log,
        stderr=log,
        start_new_session=True,
    )
    try:
        async with asyncio.timeout(100):
            while not (root / "ready.json").exists():
                if process.returncode is not None:
                    raise RuntimeError("Owned holder exited before native readiness")
                await asyncio.sleep(0.1)
        ready = json.loads((root / "ready.json").read_text())
        assert ready["native_turns_sent"] == 0
        evidence["before_crash"] = ready
        process.kill()  # Directly owned host process, never an inner native PID.
        await process.wait()
        evidence["holder_terminal"] = True
        print("Holder killed; reopening its database", flush=True)
        settings["control_root"] = str(root / "recovery-control")
        async with backend(
            root, environment(), runtime_settings=settings, seed_data=False
        ) as (_store, owner, _api, _database):
            path = f"/api/projects/101/runs/{ready['run_id']}/recovery"
            before = await owner.get(path)
            before.raise_for_status()
            evidence["inspection"] = before.json()
            assert (
                before.json()["status"] == "reconciling"
                and before.json()["can_reconcile"]
            )
            body = {
                "operation_key": "recover-after-crash",
                "attempt_id": ready["attempt_id"],
                "expected_fence": before.json()["fence"],
            }
            result = await owner.post(path, json=body)
            result.raise_for_status()
            assert (
                result.json()["status"] == "failed"
                and result.json()["local_execution_closed"]
            )
            assert (
                not result.json()["inference_started"]
                and not result.json()["task_accepted"]
            )
            assert (await owner.post(path, json=body)).json() == result.json()
            evidence["recovered"] = result.json()
            with closing(connect(str(database))) as conn:
                evidence["namespace_peers"] = [
                    dict(row)
                    for row in conn.execute(
                        "SELECT kind,state,reason FROM runtime_peers ORDER BY kind"
                    )
                ]
                assert len(evidence["namespace_peers"]) == 2 and all(
                    p["state"] == "closed" for p in evidence["namespace_peers"]
                )
                assert (
                    conn.execute(
                        "SELECT COUNT(*) FROM runtime_inference_dispatches"
                    ).fetchone()[0]
                    == 0
                )
                assert (
                    conn.execute(
                        "SELECT COUNT(*) FROM tool_grants WHERE revoked_at IS NULL"
                    ).fetchone()[0]
                    == 0
                )
                assert (
                    conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
                    == "in_progress"
                )
                assert (
                    conn.execute("SELECT COUNT(*) FROM agent_events").fetchone()[0] == 0
                )
                assert conn.execute("PRAGMA foreign_key_check").fetchone() is None
            evidence.update(
                status="passed",
                no_dispatch_replayed=True,
                grants_revoked=True,
                task_not_accepted=True,
            )
        evidence["owned_backend_terminal"] = True
    except BaseException as exc:
        evidence.update(status="failed", error_type=type(exc).__name__)
        raise
    finally:
        await terminate(process)
        log.close()
        (root / "result.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
        )
        print("Trial", evidence["status"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--holder")
    parser.add_argument("--config")
    parser.add_argument("--workspace")
    arguments = parser.parse_args()
    if arguments.holder:
        asyncio.run(holder(Path(arguments.holder)))
    elif arguments.live and arguments.config and arguments.workspace:
        asyncio.run(main(arguments))
    else:
        parser.error(
            "Use --live --config ... --workspace ... for the owned zero-turn trial"
        )
