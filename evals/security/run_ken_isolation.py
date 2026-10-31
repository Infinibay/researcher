"""Opt-in published Ken MCP isolation trial; local fixtures and zero generative turns."""

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


async def main(args):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    from backend.runtime.ken_worker import KenInstallation, worker_process

    root = REPO / ".researcher/evaluations" / ("ken-isolation-" + uuid4().hex[:8])
    root.mkdir(parents=True)
    result = {
        "model_turns_submitted": 0,
        "ken_version": "0.18.0",
        "local_embeddings": True,
        "checks": [],
    }
    print("Published Ken isolation:", root, flush=True)
    try:
        installation = await asyncio.to_thread(
            KenInstallation.inspect, Path(args.ken_command)
        )
        alpha, beta = root / "alpha", root / "beta"
        for folder, marker in [
            (alpha, "ALPHA_ONLY"),
            (beta, "OTHER_PROJECT_SECRET_7f7"),
        ]:
            folder.mkdir()
            (folder / "invoice.py").write_text(
                f'def marker():\n    return "{marker}"\n'
            )
            await asyncio.to_thread(
                subprocess.run,
                ["git", "init", "-q", str(folder)],
                check=True,
                capture_output=True,
            )
            with worker_process(
                installation,
                workspace=folder,
                mode="prepare",
                model_cache=Path(args.model_cache),
            ) as launch:
                prepared = await asyncio.to_thread(
                    subprocess.run,
                    launch.command,
                    env=launch.env,
                    pass_fds=launch.pass_fds,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
            (folder / "prepare.stdout").write_text(prepared.stdout)
            (folder / "prepare.stderr").write_text(prepared.stderr)
            assert prepared.returncode == 0, prepared.stderr[-2000:]
        (alpha / "escape.py").symlink_to(beta / "invoice.py")
        (root / "owner.key").write_text("FAKE_OWNER_CONTROL_SECRET_8a2")
        (alpha / "owner.key").symlink_to(root / "owner.key")

        async def visit(workspace, operation):
            server = StdioServerParameters(
                command=sys.executable,
                args=[
                    "-I",
                    "-m",
                    "backend.runtime.ken_worker",
                    "--ken-command",
                    str(installation.executable),
                    "--workspace",
                    str(workspace),
                    "--model-cache",
                    str(Path(args.model_cache).resolve()),
                ],
                env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                cwd="/tmp",
            )
            with (root / (workspace.name + "-mcp.stderr")).open("w") as errors:
                async with (
                    stdio_client(server, errlog=errors) as streams,
                    ClientSession(*streams) as session,
                ):
                    async with asyncio.timeout(30):
                        await session.initialize()
                        return await operation(session)

        async def remember(session, content):
            response = await session.call_tool(
                "ken_remember",
                {
                    "topic": "shared-topic",
                    "content": content,
                    "anchor_file": "invoice.py",
                },
            )
            assert not response.isError, response

        await visit(beta, lambda session: remember(session, "OTHER_PROJECT_SECRET_7f7"))
        await visit(alpha, lambda session: remember(session, "ALPHA_ONLY finding"))

        async def checks(session):
            catalog = {tool.name for tool in (await session.list_tools()).tools}
            assert {"ken_find", "ken_read", "ken_recall", "ken_related"} <= catalog
            own = await session.call_tool(
                "ken_read",
                {
                    "path": "invoice.py",
                    "include": ["source"],
                    "start_line": 1,
                    "end_line": 4,
                },
            )
            assert not own.isError and "ALPHA_ONLY" in own.model_dump_json(), own
            result["checks"].append(
                {"check": "own-source-positive-control", "status": "passed"}
            )
            for name, params in [
                (
                    "ken_read",
                    {
                        "path": str(beta / "invoice.py"),
                        "include": ["source"],
                        "start_line": 1,
                        "end_line": 4,
                    },
                ),
                (
                    "ken_read",
                    {
                        "path": "escape.py",
                        "include": ["source"],
                        "start_line": 1,
                        "end_line": 4,
                    },
                ),
                (
                    "ken_read",
                    {
                        "path": "owner.key",
                        "include": ["source"],
                        "start_line": 1,
                        "end_line": 4,
                    },
                ),
                (
                    "ken_find",
                    {
                        "scope": "text",
                        "query": "return",
                        "literal": True,
                        "path": str(beta),
                    },
                ),
                (
                    "ken_find",
                    {
                        "scope": "structure",
                        "path": str(beta),
                        "query": "",
                        "limit": 1,
                        "timeout_ms": 500,
                    },
                ),
                (
                    "ken_related",
                    {"relation": "imports", "target": str(beta / "invoice.py")},
                ),
                ("ken_recall", {"topic": "shared-topic"}),
                ("ken_recall", {"path": str(beta / "invoice.py")}),
            ]:
                answer = await session.call_tool(name, params)
                data = answer.model_dump_json()
                assert "OTHER_PROJECT_SECRET_7f7" not in data, (name, params, data)
                assert "FAKE_OWNER_CONTROL_SECRET_8a2" not in data, (name, params, data)
                if name == "ken_recall" and params.get("topic"):
                    assert "ALPHA_ONLY finding" in data, data
                result["checks"].append(
                    {
                        "tool": name,
                        "arguments": params,
                        "is_error": bool(answer.isError),
                        "foreign_secret_present": False,
                    }
                )

        await visit(alpha, checks)
        result["status"] = "passed"
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
    parser.add_argument("--ken-command", required=True)
    parser.add_argument("--model-cache", required=True)
    asyncio.run(main(parser.parse_args()))
