"""Read the overview on installed HTTP with synthetic plan/question history and no model.

The question fixture binds a clearly synthetic turn identifier to exercise its
domain protocol. That stored identifier is not a real native process start.
"""

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

from host_smoke import start, stop
from planning_page import observe, seed as seed_planning

ROOT = Path(__file__).resolve().parents[2]


def seed(host):
    """Extend the existing domain fixture with a parked synthetic question and real pagination data."""
    from backend.db.connection import connect
    from backend.research.sqlite_store import SQLiteResearchStore
    from backend.runtime.contracts import RunSpec
    from backend.runtime.peer_registry import AttemptPeers
    from backend.runtime.questions import Question, QuestionSet
    from backend.runtime.sqlite_questions import SQLiteQuestionStore
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.runtime.workspaces import WorkspaceRegistry

    ids = seed_planning(host)
    database = host / "source.db"
    with closing(connect(database)) as db, db:
        db.execute("INSERT INTO projects(id,name,description,status) VALUES(303,'Etiquetas históricas','Las etiquetas done no prueban aceptación del proyecto.','completed')")
        db.execute("INSERT INTO tasks(id,project_id,type,title,status) VALUES(1200,101,'research','Aclarar el formato de entrada','in_progress'),(3001,303,'research','Primera tarea marcada hecha','done'),(3002,303,'research','Segunda tarea marcada hecha','done')")
    runs = SQLiteRunStore(database)
    research = SQLiteResearchStore(database)
    spec = RunSpec(101, 1200, "synthetic-question-author", runs.context_snapshot(101, 1200)["context_version"], "fixture-question-run", "Comprobar qué campos contienen las observaciones.", "codex")
    run = runs.admit(spec, binding=WorkspaceRegistry(database, host / "sources").bind(101), conversation_thread="synthetic-overview-thread")
    lease, peers = AttemptPeers.claim(runs, 101, run.run_id, "synthetic-never-launched-owner")
    runs.bind_thread(lease, thread_id="synthetic-never-launched-thread")
    runs.bind_native(lease, thread_id="synthetic-never-launched-thread", turn_id="synthetic-never-launched-turn")
    token = research.issue_grant(project_id=101, task_id=1200, agent_id=spec.actor_id, permissions={"questions.ask"})
    scope = research.authorize(token)
    runs.bind_grant(lease, scope.grant_id)
    questions = SQLiteQuestionStore(runs, research)
    receipt = questions.ask(scope, "fixture-owner-question", QuestionSet((Question("sample", "¿Puedes describir una observación real de entrada?", "Necesitamos comprobar las claves antes de escribir el CSV.", (), "Un ejemplo ilustrativo sería {id: 7, value: 12}; no demuestra cómo son tus datos."),)))
    for peer in peers.ids.values():
        peers.registry.close(peer)
    questions.park(lease)
    with closing(connect(database)) as db, db:
        for index in range(51):
            db.execute("INSERT INTO user_requests(project_id,agent_id,request_type,title,body) VALUES(101,'legacy-fixture','question',?,?)", (f"Solicitud histórica {index + 1:02d}", "Ejemplo sintético anterior sin identidad comprobada del nuevo motor."))
        count = db.execute("SELECT COUNT(*) FROM user_requests WHERE project_id=101 AND status='pending'").fetchone()[0]
    ids.update(question={"task": 1200, "run": run.run_id, "request": receipt["request_id"]}, questionCount=count, doneProject=303)
    return ids


def main():
    """Own a new installed host and read-only browser through closure without copying real credentials."""
    import backend
    from backend.runtime.host_installation import initialize_host

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    args = parser.parse_args()
    if not Path(backend.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError("Use the separately installed product Python")
    output = args.output.resolve()
    output.mkdir(mode=0o700)
    assets = json.loads(args.assets.read_text())
    token = output / "synthetic-account.json"
    with token.open("x") as stream:
        os.chmod(token, 0o600)
        json.dump({"auth_mode": "chatgpt", "tokens": {"access_token": "synthetic.header.signature", "account_id": "synthetic-overview-review"}}, stream)
    assets.update(token_file=str(token), static_dir=str(ROOT / "frontend/dist"))
    assets.pop("storage", None)
    host = output / "host"
    initialize_host(host, witness_dir=output / "witness", assets=assets)
    ids = seed(host)
    fixture = output / "fixture.json"
    fixture.write_text(json.dumps(ids, indent=2) + "\n")
    before = observe(host)
    assert before["dispatches"] == 0
    assert all(row["state"] == "closed" for row in before["peers"])
    assert all(row["status"] in ("needs_review", "accepted", "waiting_input") for row in before["runs"])
    result = {"status": "running", "synthetic_domain_history": True, "actual_model_turns": 0, "synthetic_bound_turn_ids": before["native_starts"], "backend": str(Path(backend.__file__).resolve()), "web_index_sha256": hashlib.sha256((ROOT / "frontend/dist/index.html").read_bytes()).hexdigest(), "before": before}
    with socket.socket() as binding:
        binding.bind(("127.0.0.1", 0))
        port = binding.getsockname()[1]
    process = log = None
    try:
        process, log = start(host, output, port, 1)
        keys = list((host / "auth").glob("owner-*.key"))
        if len(keys) != 1:
            raise RuntimeError("Expected one private owner file")
        env = {**os.environ, "RESEARCHER_E2E_ORIGIN": f"http://127.0.0.1:{port}", "RESEARCHER_E2E_OWNER_FILE": str(keys[0]), "RESEARCHER_E2E_OUTPUT": str(output / "browser"), "RESEARCHER_E2E_FIXTURE": str(fixture)}
        with (output / "browser.log").open("x") as browser_log:
            browser = subprocess.run([str(args.node.resolve(strict=True)), "tests/overview.e2e.mjs"], cwd=ROOT / "frontend", env=env, stdout=browser_log, stderr=subprocess.STDOUT, check=False)
        result["browser_exit"] = browser.returncode
        assert browser.returncode == 0, "Inspect the original browser log"
        assert observe(host) == before, "Overview must not mutate task/run/planning domain state"
        result["status"] = "passed"
    except BaseException as error:
        result.update(status="failed", error_type=type(error).__name__)
        raise
    finally:
        if process is not None:
            result["service_exit"] = stop(process, log)
        result["after"] = observe(host)
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"status": result["status"], "receipt": str(output / "result.json")}), flush=True)


if __name__ == "__main__":
    main()
