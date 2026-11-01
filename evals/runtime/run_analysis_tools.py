"""Real CLI analysis-tool probes. No model turns, accounts or API credentials."""

import argparse
import asyncio
import json
import os
import sqlite3
import sys
from functools import partial
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


async def main(args):
    from backend.runtime.analysis_tools import AnalysisTools
    from backend.runtime.contracts import RunSpec
    from backend.runtime.native_commands import command_executor
    from backend.runtime.peer_registry import AttemptPeers
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.tools.base.db import ensure_migrations

    root = REPO / ".researcher/evaluations" / ("analysis-tools-" + uuid4().hex[:8])
    root.mkdir(parents=True)
    workspace, outside = root / "workspace", root / "outside"
    workspace.mkdir()
    outside.mkdir()
    (workspace / "source.txt").write_text("SOURCE_UNCHANGED")
    (outside / "secret.txt").write_text("OTHER_PROJECT_PRIVATE")
    (workspace / "escape").symlink_to(outside, target_is_directory=True)
    (workspace / ".codex").mkdir()
    (workspace / ".codex/config.toml").write_text(
        '[permissions.researcher_jobs.filesystem]\n":workspace_roots"="write"\n'
        + json.dumps(str(outside))
        + '="read"\n'
        "[permissions.researcher_jobs.network]\nenabled=true\n"
    )
    database = root / "research.db"
    ensure_migrations(database)
    with sqlite3.connect(database) as conn:
        conn.execute("INSERT INTO projects(id,name) VALUES(101,'Analysis')")
        conn.execute(
            "INSERT INTO tasks(id,project_id,type,title,status) VALUES(1001,101,'research','Calculate','in_progress')"
        )
    journal = SQLiteRunStore(database)
    run = journal.admit(
        RunSpec(101, 1001, "worker", 1, "analysis-probe", "Probe", "codex")
    )
    lease, peers = AttemptPeers.claim(
        journal, 101, run.run_id, "owner", lease_seconds=120
    )
    results = {"root": str(root), "model_turns": 0, "commands": []}
    print("Analysis integration:", root, flush=True)
    os.environ["RESEARCHER_TOOL_TOKEN"] = "SYNTHETIC_MUST_NOT_BE_INHERITED"
    python = Path(sys.executable).resolve()
    try:
        async with AnalysisTools(
            journal=journal,
            lease=lease,
            workspace=workspace,
            python_executable=python,
            executor_factory=partial(
                command_executor,
                journal=journal,
                lease=lease,
                workspace=workspace,
                control_root=root / "controls",
                codex_binary=Path(args.codex_binary),
                readable_toolchains=(Path(sys.base_prefix).resolve(),),
                workspace_access="read",
            ),
        ) as tools:
            cases = [
                ("calculate", "print(137 * .21)", 0, "28.77\n"),
                (
                    "read",
                    "from pathlib import Path; print(Path('source.txt').read_text())",
                    0,
                    "SOURCE_UNCHANGED\n",
                ),
                (
                    "write",
                    "from pathlib import Path; Path('source.txt').write_text('BAD')",
                    None,
                    None,
                ),
                (
                    "outside",
                    "from pathlib import Path; print(Path("
                    + repr(str(outside / "secret.txt"))
                    + ").read_text())",
                    None,
                    None,
                ),
                (
                    "symlink",
                    "from pathlib import Path; print(Path('escape/secret.txt').read_text())",
                    None,
                    None,
                ),
                ("network", "import socket; socket.socket()", None, None),
                (
                    "environment",
                    "import os; print(os.getenv('RESEARCHER_TOOL_TOKEN', 'ABSENT')); print(os.getenv('OPENAI_API_KEY', 'ABSENT')); print(os.getenv('CODEX_HOME', 'ABSENT'))",
                    0,
                    "ABSENT\nABSENT\nABSENT\n",
                ),
            ]
            for key, code, expected_exit, expected_out in cases:
                response = await tools.call(
                    {
                        "tool": "researcher_python",
                        "arguments": {"operation_key": key, "code": code},
                    }
                )
                assert response["success"], response
                job_id = json.loads(response["contentItems"][0]["text"])["job_id"]
                async with asyncio.timeout(15):
                    while True:
                        response = await tools.call(
                            {
                                "tool": "researcher_command_read",
                                "arguments": {"job_id": job_id, "wait_ms": 1000},
                            }
                        )
                        assert response["success"], response
                        record = json.loads(response["contentItems"][0]["text"])
                        if record["status"] in ("exited", "unknown"):
                            break
                results["commands"].append({"key": key, **record})
                assert (
                    record["status"] == "exited" and record["local_execution_closed"]
                ), record
                if expected_exit is None:
                    assert (
                        record["exit_code"] != 0
                        and "OTHER_PROJECT_PRIVATE" not in record["stdout"]["text"]
                    ), record
                else:
                    assert (
                        record["exit_code"] == expected_exit
                        and record["stdout"]["text"] == expected_out
                    ), record
            assert (workspace / "source.txt").read_text() == "SOURCE_UNCHANGED"
            results["source_unchanged"] = True
    finally:
        await peers.aclose()
        results["all_peers_closed"] = peers.closed()
        (root / "evidence.json").write_text(json.dumps(results, indent=2))
    assert results["all_peers_closed"]
    print(
        "PASS: real CLI computation, read-only source, scope/symlink/network/env denial; zero model turns",
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-binary", required=True)
    asyncio.run(main(parser.parse_args()))
