"""Explicit bounded subscription trial: question, closed peers, answer, next draft.

Only --live sends generation, at most two admitted turns in fresh data. The
second instruction never supplies the base; it must use the recorded answer.
No rendered UI or comprehension claim follows from these machine checks.
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

    root = REPO / ".researcher/evaluations" / ("questions-" + uuid4().hex[:8])
    trial = prepare(root, args.assets, live=args.live, turns=2)
    workspace = trial.workspace
    evidence = {"status": "starting", "admitted_requests": 0, "runs": []}
    print("Question trial:", root, flush=True)
    try:
        async with backend(trial, evidence) as (
            _store,
            owner,
            _api,
            database,
        ):

            async def run(key, version, message, expected):
                """Admit one chat instruction and observe its question or draft before continuing."""
                response = await owner.post(
                    "/api/chat/101/instructions",
                    json={
                        "operation_key": key,
                        "context_version": version,
                        "task_id": 1001,
                        "thread_id": "human-questions",
                        "message": message,
                    },
                )
                response.raise_for_status()
                evidence["admitted_requests"] += 1
                run_id = response.json()["run"]["run_id"]
                print("Admitted", key, run_id, flush=True)
                async with asyncio.timeout(320):
                    while True:
                        state = await owner.get(
                            "/api/projects/101/tasks/1001/workspace"
                        )
                        state.raise_for_status()
                        data = state.json()
                        current = next(r for r in data["runs"] if r["run_id"] == run_id)
                        if current["status"] not in ("queued", "running", "cancelling"):
                            evidence["runs"].append(current)
                            assert current["status"] == expected, current
                            print("Observed", key, expected, flush=True)
                            return current, data
                        await asyncio.sleep(0.5)

            _first, data = await run(
                "ask-base",
                1,
                "En español: revisa invoice.py con Ken MCP. Quiero un informe de impuesto y total según policy.md, "
                "pero todavía no elegí la base del ejemplo. Antes de calcular, usa researcher_ask_user con operation_key ask-base: "
                "una pregunta con id base, explicación de por qué importa y opciones 100 o 200, permitiendo texto libre. "
                "No supongas la base, no redactes el informe todavía y no publiques ni aceptes la tarea. El host cerrará el turno al preguntar.",
                "waiting_input",
            )
            question = data["questions"][0]
            assert len(data["questions"]) == 1 and question["ready_for_answer"]
            assert question["questions"][0]["id"] == "base"
            assert question["questions"][0]["why_needed"].strip()
            evidence["question"] = question
            qid = question["request_id"]
            body = {
                "operation_key": "answer-base",
                "expected_version": 1,
                "answers": {"base": "200"},
            }
            path = f"/api/projects/101/tasks/1001/questions/{qid}/answers"
            answer = await owner.post(path, json=body)
            answer.raise_for_status()
            assert answer.json() == {
                "context_version": 2,
                "application": "recorded_for_next_run",
                "inference_started": False,
            }
            assert (await owner.post(path, json=body)).json() == answer.json()
            with closing(connect(str(database))) as conn:
                assert (
                    conn.execute(
                        "SELECT COUNT(*) FROM runtime_inference_dispatches"
                    ).fetchone()[0]
                    == 1
                )
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
            evidence["answer"] = answer.json()
            _second, data = await run(
                "use-recorded-answer",
                2,
                "Continúa en español usando la respuesta del usuario guardada en el contexto. "
                "Comprueba invoice.py con Ken; captura policy.md mediante researcher, registra una observación provisional con cita literal "
                "y guarda un informe borrador con el ejemplo elegido. Distingue impuesto y total, evidencia de la fuente y del código. "
                "Explica qué cambió tras la respuesta y los límites. No vuelvas a preguntar lo ya contestado, no ejecutes tests, publiques ni aceptes la tarea. "
                "Usa claves source-after-answer, finding-after-answer y report-after-answer; termina con el ID del informe.",
                "needs_review",
            )
            assert (
                len(data["questions"]) == 1
                and data["questions"][0]["status"] == "responded"
            )
            assert len(data["reports"]) == 1
            report = await owner.get(
                f"/api/artifacts/{data['reports'][0]['id']}?project_id=101"
            )
            report.raise_for_status()
            text = report.json()["content"].replace(",", ".")
            assert all(value in text for value in ("200", "42", "242")), text
            evidence["report"] = report.json()
            evidence["messages"] = (
                await owner.get("/api/chat/101/threads/human-questions")
            ).json()
            assert [m["delivery"] for m in evidence["messages"]] == [
                "instruction_admitted",
                "question",
                "answer",
                "instruction_admitted",
                "proposal",
            ]
            with closing(connect(str(database))) as conn:
                evidence["dispatches"] = [
                    dict(r)
                    for r in conn.execute(
                        "SELECT model,status,native_status,observed_tokens FROM runtime_inference_dispatches ORDER BY rowid"
                    )
                ]
                assert len(evidence["dispatches"]) == 2
                assert (
                    conn.execute(
                        "SELECT COUNT(*) FROM tool_grants WHERE revoked_at IS NULL"
                    ).fetchone()[0]
                    == 0
                )
                assert (
                    conn.execute("SELECT COUNT(*) FROM agent_events").fetchone()[0] == 0
                )
                assert (
                    conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
                    == "in_progress"
                )
                assert conn.execute("PRAGMA foreign_key_check").fetchone() is None
            evidence.update(
                status="passed",
                grants_revoked=True,
                legacy_events_created=0,
                task_not_done=True,
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
