"""One explicit subscription turn, then owner Stop after durable turn binding."""

import argparse
import asyncio
import json
import sys
from contextlib import closing
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


async def main(args):
    """Run the bounded scenario against a fresh native installation and retain its evidence."""
    from backend.db.connection import connect
    from evals.runtime.native_trial import backend, prepare

    root = REPO / ".researcher/evaluations" / ("product-stop-" + uuid4().hex[:8])
    trial = prepare(root, args.assets, live=args.live, turns=1, wall_seconds=30, no_progress_seconds=15)
    workspace = trial.workspace
    evidence = {"status": "starting", "admission_requests": 0}
    print("Product Stop:", root, flush=True)
    try:
        async with backend(trial, evidence) as (
            _store,
            owner,
            _api,
            database,
        ):
            admitted = await owner.post(
                "/api/projects/101/tasks/1001/runs",
                json={
                    "operation_key": "generation-stop",
                    "context_version": 1,
                    "request": "Usa Ken para leer invoice.py y las herramientas researcher para estudiar policy.md. Prepara una explicación detallada con ejemplos; no guardes informes ni aceptes la tarea. El propietario puede interrumpir esta prueba.",
                },
            )
            admitted.raise_for_status()
            evidence["admission_requests"] = 1
            run_id = admitted.json()["run_id"]
            async with asyncio.timeout(90):
                while True:
                    current = (
                        await owner.get("/api/projects/101/runs/" + run_id)
                    ).json()
                    if current.get("turn_id"):
                        assert current["status"] == "running", current
                        break
                    await asyncio.sleep(0.02)
            stop = await owner.post("/api/projects/101/runs/" + run_id + "/stop")
            stop.raise_for_status()
            evidence["stop_receipt_status"] = stop.json()["status"]
            async with asyncio.timeout(20):
                while True:
                    current = (
                        await owner.get("/api/projects/101/runs/" + run_id)
                    ).json()
                    if current["status"] not in ("running", "cancelling"):
                        break
                    await asyncio.sleep(0.05)
            evidence["run"] = current
            assert current["status"] == "cancelled", current
            with closing(connect(str(database))) as conn:
                assert (
                    conn.execute(
                        "SELECT COUNT(*) FROM tool_grants WHERE revoked_at IS NULL"
                    ).fetchone()[0]
                    == 0
                )
                assert (
                    conn.execute("SELECT COUNT(*) FROM research_reports").fetchone()[0]
                    == 0
                )
                assert (
                    conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
                    == "in_progress"
                )
                evidence["dispatch"] = dict(
                    conn.execute(
                        "SELECT status,observed_tokens FROM runtime_inference_dispatches"
                    ).fetchone()
                )
                evidence["peer_receipts"] = [
                    json.loads(row[0])
                    for row in conn.execute(
                        "SELECT event_data_json FROM events_log WHERE event_type='run.peers_retired'"
                    )
                ]
                assert (
                    evidence["peer_receipts"]
                    and evidence["peer_receipts"][-1]["native_and_business_closed"]
                )
                evidence.update(
                    grants_revoked=True, reports_created=0, task_not_done=True
                )
            evidence["status"] = "passed"
        evidence["owned_backend_terminal"] = True
    except BaseException as exc:
        evidence.update(status="failed", error_type=type(exc).__name__)
        raise
    finally:
        (root / "result.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
        )
        print("Trial", evidence["status"], flush=True)


if __name__ == "__main__":
    from evals.runtime.native_trial import arguments

    asyncio.run(main(arguments(argparse.ArgumentParser(description=__doc__))))
