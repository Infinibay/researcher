"""Read real native receipts over owned local HTTP; never start inference.

Uses a copy of an earlier synthetic trial. No original/user database is migrated,
and read-only source fingerprints detect unintended changes.
"""

import argparse
import asyncio
import base64
import hashlib
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from uuid import uuid4

import httpx

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

TABLES = (
    "runtime_runs",
    "runtime_attempts",
    "runtime_jobs",
    "runtime_peers",
    "runtime_inference_dispatches",
    "runtime_input_snapshots",
    "tool_grants",
    "research_reports",
    "tasks",
)


def fingerprint(database):
    result = {}
    with closing(
        sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    ) as conn:
        for table in TABLES:
            rows = conn.execute("SELECT * FROM " + table + " ORDER BY 1,2").fetchall()
            result[table] = {
                "rows": len(rows),
                "sha256": hashlib.sha256(repr(rows).encode()).hexdigest(),
            }
    return result


async def main(args):
    from evals.runtime.run_research import backend, environment

    trials = (REPO / ".researcher/evaluations").resolve()
    source = args.source_root.resolve(strict=True)
    if not source.is_relative_to(trials):
        raise ValueError(
            "Only an explicit synthetic trial below .researcher/evaluations is supported"
        )
    source_database = source / "research.db"
    before_source = fingerprint(source_database)
    root = trials / ("owner-command-inspection-" + uuid4().hex[:8])
    root.mkdir()
    database = root / "research.db"
    with (
        closing(
            sqlite3.connect(source_database.as_uri() + "?mode=ro", uri=True)
        ) as origin,
        closing(sqlite3.connect(database)) as target,
    ):
        origin.backup(target)
    before_copy = fingerprint(database)
    assert before_copy == before_source
    evidence = {
        "status": "starting",
        "root": str(root),
        "source_trial": source.name,
        "new_inference_turns": 0,
        "image_calls": 0,
    }
    print("Owner command inspection:", root, flush=True)
    try:
        with closing(sqlite3.connect(database)) as conn:
            rows = conn.execute(
                "SELECT r.id,r.project_id,r.task_id,j.id,j.stdout,j.stderr FROM runtime_runs r JOIN runtime_jobs j ON j.run_id=r.id ORDER BY j.rowid"
            ).fetchall()
            assert len(rows) == 1, (
                "This bounded probe expects the one-job analysis fixture"
            )
            run_id, project, task, job_id, expected_stdout, expected_stderr = rows[0]
        async with backend(root, environment(), seed_data=False) as (
            _store,
            owner,
            api,
            _database,
        ):
            path = f"/api/projects/{project}/runs/{run_id}/jobs"
            async with httpx.AsyncClient(base_url=api, trust_env=False) as anonymous:
                assert (await anonymous.get(path)).status_code == 401
                assert (
                    await anonymous.get(
                        path, headers={"Authorization": "Bearer synthetic-agent-token"}
                    )
                ).status_code == 401
            listed = await owner.get(path)
            listed.raise_for_status()
            assert listed.headers["cache-control"] == "no-store"
            page = listed.json()
            assert page["total"] == 1 and page["items"][0]["job_id"] == job_id
            assert isinstance(page["items"][0]["seq"], str)
            assert page["items"][0]["local_execution_closed"]
            collected = bytearray()
            offset = 0
            reads = 0
            async with asyncio.timeout(15):
                while True:
                    response = await owner.get(
                        path + "/" + job_id,
                        params={"stdout_offset": offset, "max_bytes": 7},
                    )
                    response.raise_for_status()
                    assert response.headers["cache-control"] == "no-store"
                    body = response.json()
                    assert body["exit_code"] == 0 and body["local_execution_closed"]
                    collected.extend(
                        base64.b64decode(body["stdout"]["base64"], validate=True)
                    )
                    reads += 1
                    if not body["stdout"]["has_more"]:
                        break
                    assert body["stdout"]["next_offset"] > offset
                    offset = body["stdout"]["next_offset"]
            assert bytes(collected) == expected_stdout
            assert base64.b64decode(body["stderr"]["base64"]) == expected_stderr == b""
            assert (
                await owner.get(path.replace(f"projects/{project}", "projects/202"))
            ).status_code == 404
            workspace = await owner.get(
                f"/api/projects/{project}/tasks/{task}/workspace"
            )
            workspace.raise_for_status()
            assert workspace.json()["runtime"]["configured"] is False
            assert (await owner.get("/")).status_code == 200
            evidence.update(
                {
                    "window_reads": reads,
                    "stdout_bytes": len(collected),
                    "stdout_sha256": hashlib.sha256(collected).hexdigest(),
                    "anonymous_and_bearer_status": 401,
                    "foreign_project_status": 404,
                    "runtime_configured": False,
                }
            )
        assert fingerprint(database) == before_copy
        assert fingerprint(source_database) == before_source
        evidence.update(
            {
                "status": "passed",
                "original_unchanged": True,
                "copy_runtime_tables_unchanged": True,
                "table_fingerprints": before_copy,
                "browser_acceptance": "not_tested",
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
    parser.add_argument("--source-root", type=Path, required=True)
    asyncio.run(main(parser.parse_args()))
