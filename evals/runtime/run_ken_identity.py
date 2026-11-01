"""Native Ken search through the production CLI boundary; zero model turns.

Fresh synthetic code, pinned public local assets, owned peers and subscription
account metadata. No OpenAI generation, source edits or user data migration.
"""

import argparse
import asyncio
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


async def main(args):
    from backend.runtime.contracts import RunSpec
    from backend.runtime.native_inference import KEN_SERVER, CodexRuntime
    from backend.runtime.peer_registry import AttemptPeers
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.runtime.workspaces import WorkspaceRegistry
    from evals.runtime.run_research import backend, environment

    root = REPO / ".researcher/evaluations" / ("ken-identity-" + uuid4().hex[:8])
    workspace = root / "workspaces/workspace"
    workspace.mkdir(parents=True)
    settings = json.loads(args.config.read_text())
    evidence = {"status": "starting", "model_turns_submitted": 0, "image_calls": 0}
    print("Native Ken identity:", root, flush=True)
    for name in ("invoice.py", "test_invoice.py"):
        (workspace / name).write_bytes(
            (REPO / "evals/runtime/fixture" / name).read_bytes()
        )
    expected = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in workspace.glob("*.py")
    }
    git_env = {
        **environment(),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }
    for command in (
        ["git", "init", "-q"],
        ["git", "add", "invoice.py", "test_invoice.py"],
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@localhost",
            "commit",
            "-qm",
            "Synthetic Ken source",
        ],
    ):
        await asyncio.to_thread(
            subprocess.run,
            command,
            cwd=workspace,
            env=git_env,
            capture_output=True,
            timeout=10,
            check=True,
        )
    info = workspace.stat()
    try:
        # Exercise the exact CLI main used by app-server, including asset/cache
        # forwarding. Direct worker_process-only probes would miss this boundary.
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",
            "-m",
            "backend.runtime.ken_worker",
            "--ken-command",
            settings["ken_command"],
            "--workspace",
            str(workspace),
            "--model-cache",
            settings["model_cache"],
            "--expected-device",
            str(info.st_dev),
            "--expected-inode",
            str(info.st_ino),
            "--prepare",
            env=environment(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            async with asyncio.timeout(90):
                stdout, stderr = await process.communicate()
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
        (root / "prepare.stdout").write_bytes(stdout)
        (root / "prepare.stderr").write_bytes(stderr)
        assert process.returncode == 0, stderr[-2000:].decode(errors="replace")
        evidence["cli_prepare"] = "passed"
        async with backend(root, environment()) as (research, _owner, api, database):
            with sqlite3.connect(database) as conn:
                conn.execute(
                    "INSERT INTO repositories(id,project_id,name,local_path) VALUES(11,101,'fixture',?)",
                    (str(workspace),),
                )
            runs = SQLiteRunStore(database)
            binding = WorkspaceRegistry(database, root / "workspaces").bind(101, 11)
            run = runs.admit(
                RunSpec(
                    101,
                    1001,
                    "probe",
                    1,
                    "ken-identity",
                    "Verify source identity and search without inference",
                    "codex",
                ),
                binding=binding,
            )
            lease, peers = AttemptPeers.claim(
                runs, 101, run.run_id, "probe-owner", lease_seconds=120
            )
            token = research.issue_grant(
                project_id=101,
                task_id=1001,
                agent_id="probe",
                permissions={"sources.read"},
            )
            scope = research.authorize(token)
            runtime = CodexRuntime(
                codex_binary=Path(args.codex_binary),
                managed_home=Path(settings["managed_home"]),
                control_root=root / "controls",
                ken_command=Path(settings["ken_command"]),
                model_cache=Path(settings["model_cache"]),
                business_script=Path(settings["business_script"]),
                uv_binary=Path(settings["uv_binary"]),
                uv_cache=Path(settings["uv_cache"]),
                api_url=api,
                model=settings["model"],
            )
            try:
                async with runtime.open(
                    workspace=workspace, tool_token=token, peer_owner=peers
                ) as session:
                    config = (
                        await session.native.rpc.request(
                            "config/read",
                            {"cwd": str(workspace), "includeLayers": False},
                        )
                    )["config"]
                    worker_args = config["mcp_servers"][KEN_SERVER]["args"]
                    assert worker_args[
                        worker_args.index("--expected-device") + 1
                    ] == str(info.st_dev)
                    assert worker_args[
                        worker_args.index("--expected-inode") + 1
                    ] == str(info.st_ino)
                    for tool, arguments, markers in [
                        (
                            "ken_find",
                            {
                                "query": "Find the function that calculates an invoice total including tax",
                                "scope": "symbols",
                                "piece_kind": "symbol",
                                "purpose": "implementation",
                                "max_chars": 2000,
                            },
                            ["total_due", "invoice.py"],
                        ),
                        (
                            "ken_read",
                            {
                                "path": "invoice.py",
                                "include": ["source"],
                                "start_line": 1,
                                "end_line": 10,
                            },
                            ["return subtotal + tax_rate"],
                        ),
                    ]:
                        response = await session.native.rpc.request(
                            "mcpServer/tool/call",
                            {
                                "threadId": session.thread_id,
                                "server": KEN_SERVER,
                                "tool": tool,
                                "arguments": arguments,
                            },
                        )
                        text = json.dumps(response)
                        (root / (tool + ".json")).write_text(text)
                        assert response.get("isError") is False, response
                        assert all(marker in text for marker in markers), response
                        evidence[tool] = "passed"
                    assert session.native.turns_sent == 0
                    evidence.update(
                        {
                            "catalog_count": len(session.catalog),
                            "model": session.model,
                            "native_turns_sent": session.native.turns_sent,
                        }
                    )
            finally:
                research.revoke_grant(scope.grant_id)
                await peers.aclose()
                if peers.closed():
                    # This diagnostic never reserves inference. Retire even when
                    # preflight failed; do not leave a logically running fixture.
                    runs.retire_inference(lease, outcome="failed")
            assert peers.closed()
            evidence["all_registered_peers_closed"] = True
            with sqlite3.connect(database) as conn:
                assert (
                    conn.execute(
                        "SELECT COUNT(*) FROM runtime_inference_dispatches"
                    ).fetchone()[0]
                    == 0
                )
                assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in workspace.glob("*.py")
        } == expected
        evidence.update(
            {
                "status": "passed",
                "source_files_unchanged": True,
                "source_sha256": expected,
            }
        )
    except BaseException as exc:
        evidence["status"], evidence["error_kind"] = "failed", type(exc).__name__
        raise
    finally:
        (root / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
        print("Evidence:", root / "evidence.json", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--codex-binary", required=True)
    asyncio.run(main(parser.parse_args()))
