"""Native production boundary metadata/tool probe; no generative turn is sent."""

import argparse
import asyncio
import json
import os
import shutil
import sys
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


async def main(args):
    from backend.runtime.native_inference import KEN_SERVER, CodexRuntime
    from evals.runtime.run_research import backend, environment

    root = REPO / ".researcher/evaluations" / ("native-boundary-" + uuid4().hex[:8])
    root.mkdir(parents=True)
    workspace = Path(args.workspace).resolve(strict=True)
    result = {"model_turns_submitted": 0, "status": "starting"}
    print("Native boundary:", root, flush=True)
    try:
        async with backend(root, environment()) as (store, _owner, api, _database):
            token = store.issue_grant(
                project_id=101,
                task_id=1001,
                agent_id="native-researcher",
                permissions={"sources.read"},
            )
            scope = store.authorize(token)
            try:
                runtime = CodexRuntime(
                    codex_binary=Path(args.codex_binary),
                    managed_home=Path(
                        os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
                    ),
                    control_root=root / "control",
                    ken_command=Path(args.ken_command),
                    model_cache=Path(args.model_cache),
                    business_script=REPO / "scripts/researcher_mcp_server.py",
                    uv_binary=Path(shutil.which("uv")),
                    uv_cache=Path(
                        os.environ.get("UV_CACHE_DIR", str(Path.home() / ".cache/uv"))
                    ),
                    api_url=api,
                    model="gpt-6.1-sol",
                )
                async with runtime.open(
                    workspace=workspace, tool_token=token
                ) as session:
                    result["thread_id"] = session.thread_id
                    result["catalog_hash"] = session.catalog_hash
                    result["native_thread_ephemeral"] = (
                        session.native.thread_configuration["thread"].get("ephemeral")
                    )
                    config = session.native.thread_configuration
                    result["profile"] = config.get("activePermissionProfile")
                    result["model"] = session.model
                    assert session.model == config.get("model")
                    result["native_turns_sent"] = session.native.turns_sent
                    observed = await session.native.rpc.request(
                        "mcpServer/tool/call",
                        {
                            "threadId": session.thread_id,
                            "server": KEN_SERVER,
                            "tool": "ken_read",
                            "arguments": {
                                "path": "invoice.py",
                                "include": ["source"],
                                "start_line": 1,
                                "end_line": 4,
                            },
                        },
                    )
                    assert "ALPHA_ONLY" in json.dumps(observed), observed
                    result["native_ken_read"] = "passed"
                    references = await session.business.call(
                        {"tool": "researcher_reference_list", "arguments": {}}
                    )
                    assert references["success"] and "policy.md" in json.dumps(
                        references
                    ), references
                    result["host_business_read"] = "passed"
                    sentinel = root / "private-control.key"
                    sentinel.write_text("SYNTHETIC_PRIVATE_CONTROL_8a2")
                    assert token not in json.dumps(session.native.rpc.env)
                    assert token not in json.dumps(session.native.rpc.command)
                    result["business_grant_absent_from_native_launch"] = True
                    reads = []
                    for label, command in [
                        ("inside", ["/bin/cat", str(workspace / "invoice.py")]),
                        ("outside", ["/bin/cat", str(sentinel)]),
                        (
                            "python-positive",
                            ["/usr/bin/python3", "-c", "print('RUNTIME_EXEC_READY')"],
                        ),
                        (
                            "read-only",
                            [
                                "/usr/bin/python3",
                                "-c",
                                "from pathlib import Path; import sys,json\ntry: Path('native-boundary-unexpected-write').write_text('unexpected')\nexcept OSError as e: print(json.dumps({'write_errno':e.errno}));sys.exit(23)",
                            ],
                        ),
                        (
                            "network",
                            [
                                "/usr/bin/python3",
                                "-c",
                                "import socket,sys,json\ntry: socket.socket()\nexcept OSError as e: print(json.dumps({'socket_errno':e.errno}));sys.exit(23)",
                            ],
                        ),
                    ]:
                        reply = await session.native.rpc.request(
                            "command/exec",
                            {
                                "command": command,
                                "cwd": str(workspace),
                                "permissionProfile": "researcher_inference",
                                "timeoutMs": 2000,
                                "outputBytesCap": 8192,
                            },
                        )
                        if label == "inside":
                            assert (
                                reply["exitCode"] == 0
                                and "ALPHA_ONLY" in reply["stdout"]
                            ), reply
                        elif label == "python-positive":
                            assert (
                                reply["exitCode"] == 0
                                and "RUNTIME_EXEC_READY" in reply["stdout"]
                            ), reply
                        else:
                            assert (
                                reply["exitCode"] != 0
                                and "SYNTHETIC_PRIVATE_CONTROL_8a2"
                                not in json.dumps(reply)
                            ), reply
                            if label == "network":
                                assert reply["exitCode"] == 23 and json.loads(
                                    reply["stdout"]
                                )["socket_errno"] in {1, 13}, reply
                            if label == "read-only":
                                assert reply["exitCode"] == 23 and json.loads(
                                    reply["stdout"]
                                )["write_errno"] in {13, 30}, reply
                        reads.append({"case": label, "exit_code": reply["exitCode"]})
                    assert not (workspace / "native-boundary-unexpected-write").exists()
                    result["inference_profile_effect_checks"] = reads
                    assert session.native.turns_sent == 0
                result["owned_peers_closed"] = session.peers_closed
                assert session.peers_closed
                if args.verify_resume:
                    async with runtime.open(
                        workspace=workspace,
                        tool_token=token,
                        resume_thread_id=result["thread_id"],
                        expected_catalog_hash=result["catalog_hash"],
                    ) as restored:
                        assert restored.thread_id == result["thread_id"]
                        assert restored.catalog_hash == result["catalog_hash"]
                        assert restored.native.turns_sent == 0
                        result["scoped_catalog_resume"] = "passed"
                        await restored.native.rpc.request(
                            "thread/archive", {"threadId": restored.thread_id}
                        )
                        result["owned_test_thread_archived"] = True
                else:
                    result["resume"] = (
                        "not_tested; zero-turn threads may have no persisted rollout"
                    )
                result["status"] = "passed"
            finally:
                store.revoke_grant(scope.grant_id)
        result["owned_backend_terminal"] = True
    except BaseException as exc:
        result["status"] = "failed"
        result["error_type"] = type(exc).__name__
        raise
    finally:
        (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(
            json.dumps({"status": result["status"], "model_turns_submitted": 0}),
            flush=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument(
        "--workspace", required=True, help="Previously prepared synthetic Alpha fixture"
    )
    parser.add_argument(
        "--verify-resume",
        action="store_true",
        help="Separate zero-turn persistence diagnostic; may fail as thread not loaded",
    )
    parser.add_argument("--ken-command", required=True)
    parser.add_argument("--model-cache", required=True)
    parser.add_argument("--codex-binary", default=shutil.which("codex"))
    asyncio.run(main(parser.parse_args()))
