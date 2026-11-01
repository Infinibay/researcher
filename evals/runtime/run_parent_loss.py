"""Kill only an owned host holder, observe native peer/job retirement; zero models."""

import argparse
import asyncio
import ctypes
import json
import os
import signal
import sys
from contextlib import closing
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
LIBC = ctypes.CDLL(None, use_errno=True)
LIBC.pidfd_open.argtypes = [ctypes.c_int, ctypes.c_uint]
LIBC.pidfd_send_signal.argtypes = [
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.c_uint,
]


def pidfd_open(pid):
    fd = LIBC.pidfd_open(pid, 0)
    if fd < 0:
        raise OSError(ctypes.get_errno(), "Unable to pin owned native process")
    return fd


def pidfd_kill(fd):
    if LIBC.pidfd_send_signal(fd, signal.SIGKILL, None, 0) < 0:
        raise OSError(ctypes.get_errno(), "Owned native process is no longer available")


async def holder(root, codex_binary):
    from backend.runtime.contracts import CommandSpec, RunSpec
    from backend.runtime.native_commands import command_executor
    from backend.runtime.peer_registry import AttemptPeers
    from backend.runtime.sqlite_runs import SQLiteRunStore

    store = SQLiteRunStore(root / "data.db")
    run = store.admit(
        RunSpec(101, 1001, "worker", 1, "parent-loss", "Parent loss", "codex")
    )
    lease, _peers = AttemptPeers.claim(
        store, 101, run.run_id, "owned-holder", lease_seconds=120
    )
    async with command_executor(
        journal=store,
        lease=lease,
        workspace=root / "workspace",
        control_root=root / "control",
        codex_binary=Path(codex_binary),
    ) as worker:
        handle = await worker.start(
            lease,
            "delayed",
            CommandSpec(
                (
                    "/usr/bin/python3",
                    "-c",
                    "from pathlib import Path; import time; Path('started').write_text('yes'); time.sleep(3); Path('delayed').write_text('unexpected')",
                )
            ),
        )
        (root / "identity.json").write_text(
            json.dumps(
                {
                    "native_pid": worker.rpc._process.pid,
                    "job_id": handle.job_id,
                    "peer_id": worker.peer_id,
                    "run_id": run.run_id,
                }
            )
        )
        await handle.wait()


async def main(codex_binary):
    from backend.db.connection import connect
    from backend.tools.base.db import ensure_migrations

    root = REPO / ".researcher/evaluations" / ("parent-loss-" + uuid4().hex[:8])
    (root / "workspace").mkdir(parents=True)
    ensure_migrations(str(root / "data.db"))
    with closing(connect(str(root / "data.db"))) as conn, conn:
        conn.execute("INSERT INTO projects(id,name) VALUES(101,'Owned loss')")
        conn.execute(
            "INSERT INTO tasks(id,project_id,type,title) VALUES(1001,101,'research','Loss')"
        )
    result = {"model_turns_submitted": 0, "status": "starting"}
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(Path(__file__).resolve()),
        "--holder",
        str(root),
        "--codex-binary",
        codex_binary,
        start_new_session=True,
    )
    pidfd = None
    try:
        async with asyncio.timeout(15):
            while (
                not (root / "identity.json").exists()
                or not (root / "workspace/started").exists()
            ):
                if process.returncode is not None:
                    raise RuntimeError("Owned holder exited before command readiness")
                await asyncio.sleep(0.02)
        identity = json.loads((root / "identity.json").read_text())
        pidfd = pidfd_open(identity["native_pid"])
        process.kill()  # Directly owned host holder; never a namespace PID.
        await process.wait()
        await asyncio.sleep(4)
        state = Path(f"/proc/{identity['native_pid']}/stat")
        terminal = not state.exists() or state.read_text().split(") ", 1)[1][0] == "Z"
        delayed = (root / "workspace/delayed").exists()
        result.update(
            identity,
            holder_terminal=process.returncode is not None,
            native_terminal=terminal,
            delayed_effect_observed=delayed,
        )
        assert terminal and not delayed, result
        from backend.runtime.recovery import RunRecovery
        from backend.runtime.sqlite_runs import SQLiteRunStore

        store = SQLiteRunStore(root / "data.db")
        store.recover_owners("replacement-owner")
        run = store.get(101, identity["run_id"])
        recovered = RunRecovery(store).reconcile(
            project_id=101,
            run_id=run.run_id,
            attempt_id=run.attempt_id,
            expected_fence=run.fence,
            operation_key="recover-command-owner",
        )
        job = store.get_job(101, identity["job_id"])
        assert (
            job.local_execution_closed
            and job.exit_code is None
            and job.status == "unknown"
        )
        assert (
            recovered["status"] == "failed"
            and not recovered["task_accepted"]
            and not recovered["inference_started"]
        )
        result["recovery"] = recovered
        result["job"] = {
            "status": job.status,
            "exit_code": job.exit_code,
            "local_execution_closed": job.local_execution_closed,
        }
        result["status"] = "passed"
    except BaseException as exc:
        result.update(status="failed", error_type=type(exc).__name__)
        raise
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        if pidfd is not None:
            # Stable pidfd identity, even if the numeric PID was recycled.
            try:
                pidfd_kill(pidfd)
            except ProcessLookupError:
                pass
            os.close(pidfd)
        (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(root, json.dumps(result), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--holder")
    parser.add_argument("--codex-binary", required=True)
    args = parser.parse_args()
    if args.holder:
        asyncio.run(holder(Path(args.holder), args.codex_binary))
    elif args.live:
        asyncio.run(main(args.codex_binary))
    else:
        parser.error("Use --live for this owned process-loss trial")
