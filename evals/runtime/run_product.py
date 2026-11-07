"""Explicit live product research → explanation → correction → revised draft.

Only --live sends native subscription turns. Fresh DB/uploads; owned server;
actual authenticated HTTP, coordinator, business MCP and isolated published Ken.
"""

import argparse
import asyncio
import hashlib
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

    root = REPO / ".researcher/evaluations" / ("product-runtime-" + uuid4().hex[:8])
    trial = prepare(root, args.assets, live=args.live, turns=2)
    workspace = trial.workspace
    evidence = {
        "status": "starting",
        "admission_requests": 0,
        "runs": [],
        "runtime": "Codex subscription",
    }
    print("Product trial:", root, flush=True)
    before = hashlib.sha256((workspace / "invoice.py").read_bytes()).hexdigest()
    try:
        async with backend(trial, evidence) as (
            _store,
            owner,
            _api,
            database,
        ):

            async def execute(key, version, prompt):
                """Admit one identified research turn and observe its original result without replay."""
                response = await owner.post(
                    "/api/projects/101/tasks/1001/runs",
                    json={
                        "operation_key": key,
                        "context_version": version,
                        "request": prompt,
                    },
                )
                response.raise_for_status()
                evidence["admission_requests"] += 1
                run_id = response.json()["run_id"]
                print("Admitted", key, run_id, flush=True)
                async with asyncio.timeout(320):
                    while True:
                        observed = await owner.get("/api/projects/101/runs/" + run_id)
                        observed.raise_for_status()
                        run = observed.json()
                        if run["status"] not in ("queued", "running", "cancelling"):
                            evidence["runs"].append(run)
                            print("Terminal", key, run["status"], flush=True)
                            assert run["status"] == "needs_review", run
                            return run
                        await asyncio.sleep(0.5)

            first = await execute(
                "initial",
                1,
                "En español: usa Ken MCP para leer invoice.py y explica exactamente qué demuestra ese archivo. "
                "Con researcher_reference_list y las herramientas researcher, captura policy.md, registra un hallazgo provisional "
                "respaldado por una cita literal de esa fuente y guarda un informe draft con ese hallazgo y un ejemplo sencillo "
                "de impuesto para una base de 100 y tasa 0.21. Explica impuesto y total por separado. "
                "Distingue la evidencia de la fuente y del código; no supongas que el código implementa esa política. "
                "Usa claves de operación initial-source, initial-finding e initial-report. No ejecutes tests ni publiques. "
                "Termina con una explicación breve, el ID del informe y sus límites; el turno no acepta la tarea.",
            )
            with closing(connect(str(database))) as conn:
                assert (
                    conn.execute("SELECT COUNT(*) FROM research_reports").fetchone()[0]
                    == 1
                ), (
                    "Initial native completion did not create the required draft; do not spend a second turn"
                )
            correction = await owner.post(
                "/api/projects/101/tasks/1001/context-corrections",
                json={
                    "operation_key": "example-correction",
                    "expected_version": 1,
                    "source_kind": "user_example",
                    "statement": "El ejemplo que necesito usa una base de 200, no de 100. No cambia la tasa 0.21 ni la política de redondeo.",
                },
            )
            correction.raise_for_status()
            assert correction.json()["inference_started"] is False
            assert (
                await owner.get("/api/projects/101/runs/" + first["run_id"])
            ).json()["status"] == "superseded"
            await execute(
                "revised",
                2,
                "En español: aplica la corrección de ejemplo registrada en el contexto. Usa Ken para comprobar invoice.py; "
                "recupera policy.md mediante las herramientas researcher, guarda un nuevo hallazgo provisional con cita literal "
                "y un nuevo informe draft sobre el ejemplo corregido. Distingue impuesto y total, evidencia y suposiciones. "
                "Usa claves revised-source, revised-finding y revised-report. Explica con claridad qué cambió y qué fue comprobado. "
                "No ejecutes tests, publiques ni aceptes la tarea. Termina con el ID del nuevo informe.",
            )
            with closing(connect(str(database))) as conn:
                reports = [
                    dict(row)
                    for row in conn.execute(
                        "SELECT a.id,a.content,r.status FROM artifacts a JOIN research_reports r ON r.artifact_id=a.id WHERE a.project_id=101 ORDER BY a.id"
                    )
                ]
                assert len(reports) == 2, reports
                assert all(row["status"] == "draft" for row in reports)
                assert (
                    "42" in reports[-1]["content"] and "242" in reports[-1]["content"]
                ), reports[-1]
                links = conn.execute(
                    "SELECT fs.quote,s.content FROM finding_sources fs JOIN research_sources s ON s.id=fs.source_id WHERE fs.project_id=101"
                ).fetchall()
                assert len(links) >= 2 and all(row[0] in row[1] for row in links)
                assert (
                    conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
                    == "in_progress"
                )
                assert (
                    conn.execute(
                        "SELECT COUNT(*) FROM tool_grants WHERE revoked_at IS NULL"
                    ).fetchone()[0]
                    == 0
                )
                dispatches = [
                    dict(row)
                    for row in conn.execute(
                        "SELECT status,observed_tokens,native_status,catalog_hash FROM runtime_inference_dispatches"
                    )
                ]
                assert len(dispatches) == 2 and all(
                    row["status"] == "settled" for row in dispatches
                )
                evidence.update(
                    reports=reports,
                    dispatches=dispatches,
                    exact_quotes_verified=len(links),
                    task_not_done=True,
                    grants_revoked=True,
                )
            evidence["history"] = (
                await owner.get("/api/projects/101/runtime-events?limit=200")
            ).json()
            evidence["source_unchanged"] = (
                before
                == hashlib.sha256((workspace / "invoice.py").read_bytes()).hexdigest()
            )
            assert evidence["source_unchanged"]
            evidence["status"] = "passed"
        evidence["owned_backend_terminal"] = True
    except BaseException as exc:
        evidence["status"] = "failed"
        evidence["error_type"] = type(exc).__name__
        raise
    finally:
        (root / "result.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
        )
        print("Trial", evidence["status"], flush=True)


if __name__ == "__main__":
    from evals.runtime.native_trial import arguments

    asyncio.run(main(arguments(argparse.ArgumentParser(description=__doc__))))
