"""One explicit subscription turn exercising Ken and the host analysis facade.

Fresh synthetic source/DB and owner HTTP. No edits, publication or replay.
This verifies tool integration, not statistical prompt quality or human comprehension.
"""

import argparse
import asyncio
import hashlib
import json
import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


async def main(args):
    """Run one bounded native scenario from fresh resources and preserve original evidence."""
    from backend.db.connection import connect
    from evals.runtime.native_trial import backend, prepare

    root = REPO / ".researcher/evaluations" / ("analysis-inference-" + uuid4().hex[:8])
    trial = prepare(root, args.assets, live=args.live, turns=1)
    workspace = trial.workspace
    print("Native scenario:", root, flush=True)
    original = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in workspace.glob("*.py")
    }
    evidence = {
        "status": "starting",
        "generation_limit": 1,
        "admitted_requests": 0,
        "image_calls": 0,
    }
    try:
        async with backend(trial, evidence) as (
            _store,
            owner,
            _api,
            database,
        ):
            body = {
                "operation_key": "analysis-integration",
                "thread_id": "analysis",
                "task_id": 1001,
                "context_version": 1,
                "message": (
                    "Este caso es ficticio. En español: usa Ken MCP para leer invoice.py y captura policy.md "
                    "con researcher. Para base 137, verifica el impuesto y total de la política mediante "
                    "researcher_python (biblioteca estándar, clave calculate-policy), leyendo el job con "
                    "researcher_command_read hasta obtener su recibo terminal. No uses sólo cálculo mental. "
                    "Explica la diferencia con el código, separando fuente, resultado ejecutado e interpretación. "
                    "Guarda un informe draft con cita de la fuente (clave analysis-report), e incluye su ID al final. "
                    "No edites archivos ni ejecutes tests, no publiques ni aceptes la tarea."
                ),
            }
            response = await owner.post("/api/chat/101/instructions", json=body)
            response.raise_for_status()
            evidence["admitted_requests"] = 1
            run_id = response.json()["run"]["run_id"]
            evidence["run_id"] = run_id
            print("Admitted", run_id, flush=True)
            async with asyncio.timeout(320):
                while True:
                    response = await owner.get(f"/api/projects/101/runs/{run_id}")
                    response.raise_for_status()
                    run = response.json()
                    if run["status"] not in ("queued", "running", "cancelling"):
                        break
                    await asyncio.sleep(0.5)
            evidence["run"] = run
            assert run["status"] == "needs_review", run
            record = await owner.get(f"/api/projects/101/runs/{run_id}/input")
            record.raise_for_status()
            record = record.json()
            names = [tool["name"] for tool in record["business_catalog"]]
            verify_native_catalog(names)
            evidence["catalog_names"] = names
            assert (
                hashlib.sha256(record["input_text"].encode()).hexdigest()
                == record["input_sha256"]
            )
            with closing(connect(str(database))) as conn:
                jobs = [
                    dict(row)
                    for row in conn.execute(
                        "SELECT operation_key,status,exit_code,stdout,stderr FROM runtime_jobs ORDER BY rowid"
                    )
                ]
                assert (
                    len(jobs) == 1 and jobs[0]["operation_key"] == "calculate-policy"
                ), jobs
                assert jobs[0]["status"] == "exited" and jobs[0]["exit_code"] == 0, jobs
                assert all(
                    value in jobs[0]["stdout"].decode() for value in ("28.77", "165.77")
                ), jobs
                evidence["jobs"] = [
                    {
                        **job,
                        "stdout": job["stdout"].decode(errors="replace"),
                        "stderr": job["stderr"].decode(errors="replace"),
                    }
                    for job in jobs
                ]
                evidence["peers"] = [
                    dict(row)
                    for row in conn.execute(
                        "SELECT kind,state FROM runtime_peers ORDER BY rowid"
                    )
                ]
                assert {"business", "native", "ken", "command"} <= {row["kind"] for row in evidence["peers"]} and all(
                    row["state"] == "closed" for row in evidence["peers"]
                )
                evidence["dispatches"] = [
                    dict(row)
                    for row in conn.execute(
                        "SELECT model,status,observed_tokens,native_status FROM runtime_inference_dispatches"
                    )
                ]
                assert len(evidence["dispatches"]) == 1
                evidence["reports"] = [
                    dict(row)
                    for row in conn.execute(
                        "SELECT artifact_id,status FROM research_reports"
                    )
                ]
                assert (
                    len(evidence["reports"]) == 1
                    and evidence["reports"][0]["status"] == "draft"
                )
                assert (
                    conn.execute(
                        "SELECT COUNT(*) FROM tool_grants WHERE revoked_at IS NULL"
                    ).fetchone()[0]
                    == 0
                )
                assert (
                    conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
                    != "done"
                )
                assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
            duplicate = await owner.post("/api/chat/101/instructions", json=body)
            duplicate.raise_for_status()
            assert duplicate.json()["run"]["run_id"] == run_id
            assert {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in workspace.glob("*.py")
            } == original
            evidence["source_files_unchanged"] = True
            evidence["status"] = "passed"
    except BaseException as exc:
        evidence["status"], evidence["error_kind"] = "failed", type(exc).__name__
        raise
    finally:
        (root / "evidence.json").write_text(
            json.dumps(evidence, indent=2, ensure_ascii=False) + "\n"
        )
        print("Evidence:", root / "evidence.json", flush=True)

    return root


def verify_native_catalog(names):
    """Check the synthetic research input's complete host composition, including Ken and analysis."""
    from backend.runtime.analysis_tools import _TOOLS
    from backend.runtime.business_mediation import RESEARCH_NAMES
    from backend.runtime.ken_mediation import KEN_NAMES

    expected = RESEARCH_NAMES | KEN_NAMES | set(_TOOLS)
    assert set(names) == expected and len(names) == len(expected), 'Incomplete or unexpected native research catalog'


def verify_ken_reads(rows):
    """Require a Ken source-read call and matching returned fixture code, not readiness or a model claim.

    This correlates the synthetic scenario's native trace. It is not a general
    verifier of arbitrary JavaScript or adversarial tool-result attribution.
    """
    calls = []
    for row in rows:
        if row.get("type") == "custom_tool_call" and row.get("name") == "exec":
            names = re.findall(r"tools\.((?:mcp__researcher_ken__)?ken_(?:read|recall))\s*\(", row.get("input", ""))
            output_type = "custom_tool_call_output"
        elif row.get("type") == "function_call":
            names = [row["name"]] if row.get("name") in {"ken_read", "ken_recall", "mcp__researcher_ken__ken_read", "mcp__researcher_ken__ken_recall"} else []
            output_type = "function_call_output"
        else:
            continue
        outputs = [x for x in rows if x.get("type") == output_type and x.get("call_id") == row.get("call_id")]
        if names and len(outputs) == 1 and "return subtotal + tax_rate" in str(outputs[0].get("output", "")):
            calls.extend(names)
    assert calls, "Ken read needs its own returned source; a call or readiness alone is insufficient"
    return calls


def verify_existing(root):
    """Read terminal evidence after a harness failure; never restart generation."""
    root = root.resolve(strict=True)
    original = root / "evidence.json"
    prior = json.loads(original.read_text())
    result = {
        "status": "checking",
        "generations_started_by_verification": 0,
        "original_evidence_sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
        "original_harness_status": prior["status"],
        "original_harness_error": prior.get("error_kind"),
        "repeated_http_receipt_check": (
            "executed"
            if prior["status"] == "passed"
            else "not_executed_in_original_harness"
        ),
    }
    native = (root / "installation/installation.json").is_file()
    database = root / ("installation/source.db" if native else "research.db")
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        run = conn.execute(
            "SELECT status FROM runtime_runs WHERE id=?", (prior["run_id"],)
        ).fetchone()
        assert run["status"] == "needs_review"
        dispatches = [
            dict(row)
            for row in conn.execute(
                "SELECT model,status,observed_tokens,native_status FROM runtime_inference_dispatches"
            )
        ]
        assert (
            len(dispatches) == 1
            and dispatches[0]["status"] == "settled"
            and dispatches[0]["native_status"] == "completed"
        )
        result["dispatches"] = dispatches
        peers = [
            dict(row)
            for row in conn.execute(
                "SELECT kind,state FROM runtime_peers ORDER BY rowid"
            )
        ]
        assert all(row["state"] == "closed" for row in peers)
        if native:
            assert {"business", "native", "ken", "command"} <= {row["kind"] for row in peers}
        else:
            assert len(peers) == 3
        result["peers"] = peers
        jobs = [
            dict(row)
            for row in conn.execute(
                "SELECT operation_key,status,exit_code,stdout,stderr FROM runtime_jobs"
            )
        ]
        assert len(jobs) == 1 and jobs[0]["operation_key"] == "calculate-policy"
        assert jobs[0]["status"] == "exited" and jobs[0]["exit_code"] == 0
        assert all(text in jobs[0]["stdout"].decode() for text in ("28.77", "165.77"))
        result["jobs"] = [
            {**row, "stdout": row["stdout"].decode(), "stderr": row["stderr"].decode()}
            for row in jobs
        ]
        reports = [
            dict(row)
            for row in conn.execute("SELECT artifact_id,status FROM research_reports")
        ]
        assert len(reports) == 1 and reports[0]["status"] == "draft"
        result["reports"] = reports
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM tool_grants WHERE revoked_at IS NULL"
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
            != "done"
        )
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        snapshot = conn.execute(
            "SELECT business_catalog_json FROM runtime_input_snapshots"
        ).fetchone()
        names = [tool["name"] for tool in json.loads(snapshot[0])]
        if native:
            verify_native_catalog(names)
        else:
            assert len(names) == 15 and "researcher_python" in names
        result["catalog_names"] = names
        thread_id = conn.execute("SELECT thread_id FROM runtime_attempts").fetchone()[0]
    workspace = root / ("installation/sources/invoice" if native else "workspaces/workspace")
    result["source_sha256"] = {}
    for name in ("invoice.py", "test_invoice.py"):
        data = (workspace / name).read_bytes()
        assert data == (REPO / "evals/runtime/fixture" / name).read_bytes()
        result["source_sha256"][name] = hashlib.sha256(data).hexdigest()
    if native:
        matches = list((root / "installation/control/native-state").rglob("*" + thread_id + "*.jsonl"))
    else:
        settings = json.loads((root / "runtime-settings.json").read_text())
        matches = list((Path(settings["managed_home"]) / "sessions").rglob("*" + thread_id + "*.jsonl"))
    assert len(matches) == 1, (
        "Need the exact native thread trace, not another conversation"
    )
    rows = [
        json.loads(line).get("payload", {})
        for line in matches[0].read_text().splitlines()
    ]
    result["ken_call_names"] = verify_ken_reads(rows)
    result["native_thread_trace_sha256"] = hashlib.sha256(
        matches[0].read_bytes()
    ).hexdigest()
    result["status"] = "passed"
    (root / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        "PASS: existing terminal artifacts verified; zero new generation. Evidence:",
        root / "verification.json",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--assets", type=Path)
    parser.add_argument("--verify-root", type=Path)
    args = parser.parse_args()
    if args.verify_root and not args.live:
        verify_existing(args.verify_root)
    elif args.live and args.assets and not args.verify_root:
        verify_existing(asyncio.run(main(args)))
    else:
        parser.error("Use --live --assets for a fresh scenario, or --verify-root for read-only inspection")
