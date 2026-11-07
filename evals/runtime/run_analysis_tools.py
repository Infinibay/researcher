"""Real CLI analysis-tool probes. No model turns, accounts or API credentials."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


async def main(args):
    """Probe the real account-free broker analysis facade and retain bounded denial/closure receipts."""
    from backend.runtime.analysis_tools import AnalysisTools
    from evals.runtime.kernel_trial import prepare

    root = REPO / ".researcher/evaluations" / ("analysis-tools-" + uuid4().hex[:8])
    trial = prepare(root, args.codex_binary, args.cgroup_parent)
    workspace, outside = trial.workspace, root / "outside"
    outside.mkdir()
    (workspace / "source.txt").write_text("SOURCE_UNCHANGED")
    (outside / "secret.txt").write_text("OTHER_PROJECT_PRIVATE")
    (workspace / "escape").symlink_to(outside, target_is_directory=True)
    (workspace / ".codex").mkdir()
    (workspace / ".codex/config.toml").write_text(
        '[permissions.researcher_jobs.filesystem]\n":workspace_roots"="write"\n'
        + json.dumps(str(outside)) + '="read"\n'
        '[permissions.researcher_jobs.network]\nenabled=true\n'
    )
    results = {"status": "starting", "model_turns": 0, "commands": [], "composition": "broker_command_executor"}
    print("Analysis integration:", root, flush=True)
    previous = os.environ.get("RESEARCHER_TOOL_TOKEN")
    os.environ["RESEARCHER_TOOL_TOKEN"] = "SYNTHETIC_MUST_NOT_BE_INHERITED"
    try:
        async with trial.open(), AnalysisTools(
            journal=trial.store, lease=trial.lease, workspace=workspace,
            python_executable=Path(sys.executable).resolve(), executor_factory=trial.commands,
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
                    "import os; from pathlib import Path; print(os.getenv('RESEARCHER_TOOL_TOKEN', 'ABSENT')); print(os.getenv('OPENAI_API_KEY', 'ABSENT')); print(os.getenv('CODEX_HOME', 'ABSENT')); print(Path('/home/actor/.codex/auth.json').exists())",
                    0,
                    "ABSENT\nABSENT\n/home/actor/.codex\nFalse\n",
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
        results["status"] = "passed"
    except BaseException as error:
        results.update(status="failed", error_type=type(error).__name__)
        raise
    finally:
        if previous is None:
            os.environ.pop("RESEARCHER_TOOL_TOKEN", None)
        else:
            os.environ["RESEARCHER_TOOL_TOKEN"] = previous
        lifecycle = root / "lifecycle.json"
        if lifecycle.exists():
            results["lifecycle"] = json.loads(lifecycle.read_text())
        (root / "evidence.json").write_text(json.dumps(results, indent=2) + "\n")
    assert results["lifecycle"]["domain_removed"] and results["lifecycle"]["all_peers_closed"]
    print("PASS: broker calculation, source/scope/symlink/network/environment isolation; zero models", flush=True)


if __name__ == "__main__":
    from evals.runtime.kernel_trial import arguments

    asyncio.run(main(arguments(argparse.ArgumentParser(description=__doc__))))
