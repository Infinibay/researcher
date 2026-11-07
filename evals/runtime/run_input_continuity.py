"""Two explicit subscription turns: exact host input and versioned chat continuity.

Fresh synthetic source/DB, mandatory published Ken, actual owner HTTP. No tests,
publication, replay or API-key fallback. Numerical checks are not human UX proof.
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
    """Run one bounded native scenario from fresh resources and preserve original evidence."""
    from backend.db.connection import connect
    from evals.runtime.native_trial import backend, prepare

    root = REPO / ".researcher/evaluations" / ("input-continuity-" + uuid4().hex[:8])
    trial = prepare(root, args.assets, live=args.live, turns=2)
    workspace = trial.workspace
    print("Native scenario:", root, flush=True)
    original = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in workspace.glob("*.py")
    }
    evidence = {
        "status": "starting",
        "admitted_requests": 0,
        "generation_limit": 2,
        "image_calls": 0,
        "runs": [],
        "input_records": [],
        "numerical_checks": "literal outputs, not human comprehension",
    }
    try:
        async with backend(trial, evidence) as (
            _store,
            owner,
            _api,
            database,
        ):

            async def run(key, version, prompt):
                """Record one instruction and verify its immutable input before comparing continuity."""
                body = {
                    "operation_key": key,
                    "thread_id": "continuity",
                    "task_id": 1001,
                    "context_version": version,
                    "message": prompt,
                }
                response = await owner.post("/api/chat/101/instructions", json=body)
                response.raise_for_status()
                evidence["admitted_requests"] += 1
                run_id = response.json()["run"]["run_id"]
                print("Admitted", key, run_id, flush=True)
                async with asyncio.timeout(320):
                    while True:
                        observed = await owner.get(f"/api/projects/101/runs/{run_id}")
                        observed.raise_for_status()
                        current = observed.json()
                        if current["status"] not in ("queued", "running", "cancelling"):
                            break
                        await asyncio.sleep(0.5)
                evidence["runs"].append(current)
                assert current["status"] == "needs_review", current
                record = await owner.get(f"/api/projects/101/runs/{run_id}/input")
                record.raise_for_status()
                record = record.json()
                evidence["input_records"].append(record)
                assert record["available"] and record["native_start_observed"]
                assert (
                    hashlib.sha256(record["input_text"].encode()).hexdigest()
                    == record["input_sha256"]
                )
                # Response loss/repeated receipt lookup must not generate another turn.
                duplicate = await owner.post("/api/chat/101/instructions", json=body)
                duplicate.raise_for_status()
                assert duplicate.json()["run"]["run_id"] == run_id
                print("Observed", key, "needs_review", flush=True)
                return current, record

            first, first_input = await run(
                "initial",
                1,
                "En español: este caso de ejemplo es ficticio y usa base 137. Usa Ken MCP para leer invoice.py y herramientas researcher para capturar policy.md. Explica con claridad el impuesto y el total según esa fuente. Guarda un informe draft con cita de la política y distingue evidencia del código, fuente e interpretación. No ejecutes tests, no edites archivos, no publiques ni aceptes la tarea. Usa claves initial-source e initial-report y termina con el ID del informe.",
            )
            first_data = json.loads(first_input["input_text"])
            assert first_data["conversation"]["messages"] == []
            with closing(connect(str(database))) as conn:
                assert (
                    conn.execute("SELECT COUNT(*) FROM research_reports").fetchone()[0]
                    == 1
                )
            correction = await owner.post(
                "/api/projects/101/tasks/1001/context-corrections",
                json={
                    "operation_key": "new-example",
                    "expected_version": 1,
                    "source_kind": "user_example",
                    "statement": "El ejemplo ahora usa base 200. La tasa sigue siendo la que dice la fuente; mantén separados impuesto y total.",
                },
            )
            correction.raise_for_status()
            assert (
                correction.json()["context_version"] == 2
                and correction.json()["inference_started"] is False
            )
            second, second_input = await run(
                "compare",
                2,
                "Compara el ejemplo original de esta conversación con el ejemplo corregido del contexto actual. No supongas que las propuestas antiguas son hechos verificados. Usa Ken MCP para comprobar de nuevo el código y la fuente ya capturada mediante researcher. Guarda otro informe draft que explique qué cambió, ambos impuestos y ambos totales, con evidencia y límites. No ejecutes tests, no edites ni publiques. Usa la clave compare-report y termina con su ID.",
            )
            second_data = json.loads(second_input["input_text"])
            assert "137" not in second_data["request"]
            assert any(
                m["kind"] == "owner_instruction" and "137" in m["content"]
                for m in second_data["conversation"]["messages"]
            )
            assert any(
                m["kind"] == "agent_proposal"
                and m["source_context_version"] == 1
                and m["run_status_at_snapshot"] == "superseded"
                for m in second_data["conversation"]["messages"]
            )
            assert second_data["corrections"][0]["source_kind"] == "user_example"
            text = second["result"]["summary"].replace(",", ".")
            assert all(
                value in text
                for value in ("137", "200", "28.77", "165.77", "42", "242")
            ), text
            old = await owner.get(f"/api/projects/101/runs/{first['run_id']}/input")
            old.raise_for_status()
            assert old.json()["input_text"] == first_input["input_text"]
            with closing(connect(str(database))) as conn:
                evidence["dispatches"] = [
                    dict(r)
                    for r in conn.execute(
                        "SELECT model,status,observed_tokens,native_status FROM runtime_inference_dispatches ORDER BY rowid"
                    )
                ]
                evidence["peer_states"] = [
                    dict(r)
                    for r in conn.execute(
                        "SELECT kind,state FROM runtime_peers ORDER BY rowid"
                    )
                ]
                evidence["report_states"] = [
                    r[0] for r in conn.execute("SELECT status FROM research_reports")
                ]
                assert len(evidence["dispatches"]) == 2 and all(
                    p["state"] == "closed" for p in evidence["peer_states"]
                )
                assert evidence["report_states"] == ["draft", "draft"]
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
            assert {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in workspace.glob("*.py")
            } == original
            evidence["source_files_unchanged"] = True
            evidence["status"] = "passed"
    except BaseException as exc:
        evidence["status"] = "failed"
        evidence["error_kind"] = type(exc).__name__
        raise
    finally:
        (root / "evidence.json").write_text(
            json.dumps(evidence, indent=2, ensure_ascii=False) + "\n"
        )
        print("Evidence:", root / "evidence.json", flush=True)


if __name__ == "__main__":
    from evals.runtime.native_trial import arguments

    asyncio.run(main(arguments(argparse.ArgumentParser(description=__doc__))))
