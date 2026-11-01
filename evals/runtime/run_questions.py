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
    from backend.db.connection import connect
    from evals.runtime.run_research import backend, environment

    root = REPO / ".researcher/evaluations" / ("questions-" + uuid4().hex[:8])
    root.mkdir(parents=True)
    settings = json.loads(Path(args.config).read_text())
    settings.update(
        control_root=str(root / "native-control"),
        project_turn_limit=2,
        project_token_limit=700000,
    )
    settings["limits"].update(
        max_turns=1, max_observed_tokens=350000, max_tool_calls=20
    )
    workspace = Path(args.workspace).resolve(strict=True)
    evidence = {"status": "starting", "admitted_requests": 0, "runs": []}
    print("Question trial:", root, flush=True)
    try:
        async with backend(root, environment(), runtime_settings=settings) as (
            _store,
            owner,
            _api,
            database,
        ):
            with closing(connect(str(database))) as conn, conn:
                conn.execute(
                    "INSERT INTO repositories(project_id,name,local_path) VALUES(101,'alpha',?)",
                    (str(workspace),),
                )

            async def run(key, version, message, expected):
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--workspace", required=True)
    asyncio.run(main(parser.parse_args()))
