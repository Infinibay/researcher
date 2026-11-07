"""Explicit one-turn subscription test of the actual human conversation API.

Fresh data and owned server. Checks durable chat, owner evidence, correction,
and old-context receipt recovery. No browser/rendered-UI acceptance is implied.
"""

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

    root = REPO / ".researcher/evaluations" / ("conversation-" + uuid4().hex[:8])
    trial = prepare(root, args.assets, live=args.live, turns=1)
    workspace = trial.workspace
    evidence = {"status": "starting", "instruction_posts": 0}
    print("Conversation trial:", root, flush=True)
    try:
        async with backend(trial, evidence) as (
            _store,
            owner,
            _api,
            database,
        ):
            body = {
                "operation_key": "conversation-instruction",
                "thread_id": "human-conversation",
                "task_id": 1001,
                "context_version": 1,
                "message": "En español: usa Ken MCP para leer invoice.py; usa herramientas researcher para capturar policy.md, registrar una observación provisional con cita literal y guardar un informe borrador. Explica con un ejemplo simple qué significa tasa 0.21 para base 100, distinguiendo impuesto y total. Aclara qué demuestra la fuente y qué demuestra el código. No ejecutes tests, publiques ni aceptes la tarea. Conserva claves de operación para reintentos y termina con el ID del informe.",
            }
            first = await owner.post("/api/chat/101/instructions", json=body)
            first.raise_for_status()
            evidence["instruction_posts"] += 1
            admitted = first.json()
            duplicate = await owner.post("/api/chat/101/instructions", json=body)
            duplicate.raise_for_status()
            evidence["instruction_posts"] += 1
            assert duplicate.json()["message"]["id"] == admitted["message"]["id"]
            run_id = admitted["run"]["run_id"]
            async with asyncio.timeout(320):
                while True:
                    observed = await owner.get("/api/projects/101/tasks/1001/workspace")
                    observed.raise_for_status()
                    data = observed.json()
                    run = next(run for run in data["runs"] if run["run_id"] == run_id)
                    if run["status"] not in ("queued", "running", "cancelling"):
                        break
                    await asyncio.sleep(0.5)
            evidence["run"] = run
            assert run["status"] == "needs_review", run
            messages = (
                await owner.get("/api/chat/101/threads/human-conversation")
            ).json()
            assert len(messages) == 2
            assert messages[1]["message"] == run["result"]["summary"]
            assert messages[1]["runtime_status"] == "needs_review"
            assert messages[1]["context_version"] == 1
            evidence["messages_before_correction"] = messages
            assert data["sources"] and len(data["reports"]) == 1, data
            source = (
                await owner.get(
                    f"/api/projects/101/research-sources/{data['sources'][0]['id']}"
                )
            ).json()
            assert "0.21 means 21 percent" in source["content"]
            evidence["owner_source"] = source
            report = await owner.get(
                f"/api/artifacts/{data['reports'][0]['id']}?project_id=101"
            )
            report.raise_for_status()
            evidence["owner_report"] = report.json()
            assert "121" in report.json()["content"]
            corrected = await owner.post(
                "/api/projects/101/tasks/1001/context-corrections",
                json={
                    "operation_key": "conversation-example",
                    "expected_version": 1,
                    "statement": "El próximo ejemplo debe usar base 200. La tasa no cambia.",
                    "source_kind": "user_example",
                },
            )
            corrected.raise_for_status()
            assert corrected.json()["context_version"] == 2
            assert corrected.json()["inference_started"] is False
            old_receipt = await owner.post("/api/chat/101/instructions", json=body)
            old_receipt.raise_for_status()
            evidence["instruction_posts"] += 1
            assert old_receipt.json()["run"]["run_id"] == run_id
            assert old_receipt.json()["run"]["status"] == "superseded"
            after = (await owner.get("/api/chat/101/threads/human-conversation")).json()
            assert len(after) == 2 and after[1]["runtime_status"] == "superseded"
            assert after[1]["message"] == messages[1]["message"]
            with closing(connect(str(database))) as conn:
                evidence["native_dispatches"] = conn.execute(
                    "SELECT COUNT(*) FROM runtime_inference_dispatches"
                ).fetchone()[0]
                assert evidence["native_dispatches"] == 1
                assert (
                    conn.execute("SELECT COUNT(*) FROM agent_events").fetchone()[0] == 0
                )
                assert (
                    conn.execute(
                        "SELECT COUNT(*) FROM tool_grants WHERE revoked_at IS NULL"
                    ).fetchone()[0]
                    == 0
                )
                assert (
                    conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
                    == "in_progress"
                )
                assert (
                    conn.execute(
                        "SELECT COUNT(*) FROM finding_sources f JOIN research_sources s ON f.source_id=s.id WHERE instr(s.content,f.quote)>0"
                    ).fetchone()[0]
                    > 0
                )
            evidence.update(
                correction=corrected.json(),
                messages_after_correction=after,
                legacy_events_created=0,
                grants_revoked=True,
                task_not_done=True,
                status="passed",
            )
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
