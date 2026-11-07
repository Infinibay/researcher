"""Capture preauthenticated synthetic owner pages; no model or user database.

This first pass deliberately performs no product mutations. Pairing occurs over
real HTTP in the owned-server helper; browser login UX is outside this capture.
"""

import argparse
import asyncio
import hashlib
import json
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


async def main(args):
    """Capture current owner pages over actual HTTP using a new closed native-command fixture."""
    from evals.runtime.owner_trial import fingerprint, prepare
    from evals.runtime.run_research import backend, environment

    trials = REPO / '.researcher/evaluations'
    root = trials / ('owner-ui-' + uuid4().hex[:8])
    trial = await prepare(root, args.codex_binary, args.cgroup_parent)
    before_source = fingerprint(trial.source_database)
    auth = root / "browser-auth.json"
    build_index = REPO / "frontend/dist/index.html"
    build_hash = hashlib.sha256(build_index.read_bytes()).hexdigest()
    evidence = {
        "status": "starting",
        "fixture": "fresh native command, closed before capture",
        "model_turns_submitted": 0,
        "image_generation_calls": 0,
        "login_flow": "preauthenticated via real owner HTTP; login UI not tested",
    }
    print("Owner browser capture:", root, flush=True)
    try:
        async with backend(root, environment(), seed_data=False, evidence=evidence) as (
            _store,
            owner,
            api,
            _database,
        ):
            payload = {
                "base_url": api,
                "output": str(root),
                "flow": args.flow,
                "stdout_bytes": len(trial.expected_stdout),
                "expected_stdout": trial.expected_stdout.decode(),
                "check": args.check,
                "viewport": args.viewport,
                "keyboard": args.keyboard,
                "cookies": [
                    {
                        "name": cookie.name,
                        "value": cookie.value,
                        "url": api,
                        "httpOnly": True,
                        "sameSite": "Lax",
                    }
                    for cookie in owner.cookies.jar
                ],
            }
            descriptor = os.open(auth, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as stream:
                json.dump(payload, stream)
            process = await asyncio.create_subprocess_exec(
                str(args.node),
                str(REPO / "evals/ui/capture_owner.mjs"),
                str(auth),
                cwd=REPO,
                env={**environment(), "PLAYWRIGHT_BROWSERS_PATH": str(args.browsers)},
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
            (root / "browser.stdout").write_bytes(stdout)
            (root / "browser.stderr").write_bytes(stderr)
            assert process.returncode == 0, stderr[-2000:].decode(errors="replace")
        assert fingerprint(root / "research.db") == before_source
        assert fingerprint(trial.source_database) == before_source
        assert hashlib.sha256(build_index.read_bytes()).hexdigest() == build_hash, (
            "Build changed during capture; screenshots rejected"
        )
        evidence.update(
            {
                "status": "captured_unreviewed",
                "source_runtime_tables_unchanged": True,
                "copy_runtime_tables_unchanged": True,
                "visual_acceptance": False,
                "build_index_sha256": build_hash,
            }
        )
    except BaseException as exc:
        evidence["status"], evidence["error_kind"] = "failed", type(exc).__name__
        raise
    finally:
        auth.unlink(missing_ok=True)
        (root / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
        print("Evidence:", root / "evidence.json", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--browsers", type=Path, required=True)
    parser.add_argument(
        "--flow",
        choices=["initial", "menu", "selected", "inspector", "commands"],
        default="initial",
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--viewport", choices=["desktop", "mobile"], default="desktop")
    parser.add_argument("--keyboard", action="store_true")
    from evals.runtime.kernel_trial import arguments

    asyncio.run(main(arguments(parser)))
