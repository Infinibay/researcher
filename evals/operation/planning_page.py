"""Review Planning against a new installed host with explicitly synthetic domain history.

No model is launched. Plan proposals are validated and accepted through domain
APIs with never-launched, closed logical peers; their completion is a fixture,
not evidence of native generation or physical process retirement.
"""

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys

from host_smoke import start, stop

ROOT = Path(__file__).resolve().parents[2]


def seed(host):
    """Build manual and protected planning cases before any service can dispatch work."""
    from backend.db.connection import connect
    from backend.planning.owner_records import OwnerPlanningRecords
    from backend.planning.store import ProjectPlans
    from backend.runtime.contracts import RunSpec
    from backend.runtime.peer_registry import AttemptPeers
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.runtime.workspaces import WorkspaceRegistry

    database = host / "source.db"
    source = host / "sources" / "planning-fixture"
    source.mkdir()
    (source / "observations.py").write_text('"""Synthetic observations; this review never executes this source."""\n')
    with closing(connect(database)) as db, db:
        db.execute("INSERT INTO projects(id,name,description) VALUES(101,'Atlas de observaciones','Ensayo sintético: comprobar el formato de los datos antes de exportarlos.'),(202,'Proyecto separado','Sin grupos ni propuestas de Atlas.')")
        db.execute("INSERT INTO repositories(id,project_id,name,local_path) VALUES(11,101,'planning-fixture',?)", (str(source),))
    runs = SQLiteRunStore(database)
    records = OwnerPlanningRecords(runs)
    manual = records.create_group(project_id=101, title="Organizar observaciones manuales", operation_key="fixture-manual")
    milestone = records.create_milestone(project_id=101, epic_id=manual["id"], title="Muestra documentada", operation_key="fixture-milestone")
    native = records.create_group(project_id=101, title="Conservar historia del planificador", operation_key="fixture-native")
    with closing(connect(database)) as db, db:
        for task_id, title in ((1001, "Leer una observación de ejemplo"), (1002, "Exportar columnas comprobadas")):
            db.execute("INSERT INTO tasks(id,project_id,epic_id,milestone_id,type,title,status) VALUES(?,101,?,?,'research',?,'pending')", (task_id, manual["id"], milestone["id"], title))
        db.execute("INSERT INTO task_dependencies(task_id,depends_on_task_id,dependency_type) VALUES(1002,1001,'blocks')")
        for task_id, title, epic in ((1101, "Plan sintético pendiente de revisión", native["id"]), (1102, "Plan sintético aceptado", None)):
            db.execute("INSERT INTO tasks(id,project_id,epic_id,type,title,description,status) VALUES(?,101,?,'plan',?,?,'in_progress')", (task_id, epic, title, "Comprobar el formato de las observaciones y exportar id y value."))
    plans = ProjectPlans(runs)
    identities = {"alpha": 101, "beta": 202, "manual": manual["id"], "milestone": milestone["id"], "native": native["id"], "manualTasks": [1001, 1002]}
    for task_id, accepted in ((1101, False), (1102, True)):
        spec = RunSpec(101, task_id, "synthetic-planner", runs.context_snapshot(101, task_id)["context_version"], f"fixture-plan-{task_id}", "Comprobar el formato de las observaciones y exportar id y value.", "codex")
        run = runs.admit(spec, binding=WorkspaceRegistry(database, host / "sources").bind(101))
        lease, peers = AttemptPeers.claim(runs, 101, run.run_id, "synthetic-never-launched-owner")
        packet = {
            "title": "Exportar observaciones con formato comprobado",
            "rationale": "Entrada ilustrativa: una lista de observaciones. Salida deseada: un CSV con columnas id y value. Primero leer una observación real para comprobar qué claves contiene; después exportar conservando el orden.",
            "assumptions": ["No está demostrado que cada observación contenga las claves id y value. El primer paso lo comprobará con un ejemplo real."],
            "basis": [{"source": "owner_request", "quote": "exportar id y value"}],
            "epics": [{"key": "export", "title": "Exportación aceptada" if accepted else "Exportación propuesta", "description": "Separar la comprobación del formato y la escritura del CSV."}],
            "tasks": [
                {"key": "inspect", "epic_key": "export", "type": "research", "title": "Comprobar una entrada real", "description": "Leer una observación y documentar sus claves y tipos. El ejemplo ilustrativo {id: 7, value: 12} no prueba el formato real.", "acceptance_criteria": "Un ejemplo real citado y su estructura descrita.", "priority": 2, "depends_on": []},
                {"key": "export", "epic_key": "export", "type": "code", "title": "Escribir el CSV", "description": "Usar las claves comprobadas y mantener el orden de entrada.", "acceptance_criteria": "La salida tiene cabecera id,value y una fila por observación válida; se explica el tratamiento de datos incompletos.", "priority": 2, "depends_on": ["inspect"]},
            ],
        }
        proposal = plans.propose(lease, f"fixture-proposal-{task_id}", packet)
        for peer in peers.ids.values():
            peers.registry.close(peer)
        runs.finish(lease, native_status="completed", summary="Synthetic domain fixture; no model or process was launched.")
        entry = {"task": task_id, "run": run.run_id, "sha256": proposal["proposal_sha256"]}
        if accepted:
            entry["acceptance"] = plans.accept(101, run.run_id, operation_key="fixture-owner-acceptance", proposal_sha256=proposal["proposal_sha256"], context_version=lease.context_version)
        identities["accepted" if accepted else "proposal"] = entry
    for index in range(16):
        records.create_group(project_id=101, title=f"Archivo de observaciones {index + 1:02d}: criterios, fuentes y comprobaciones de un objetivo extenso", description="Descripción sintética extensa para revisar lectura y distribución. " * 12, operation_key=f"fixture-scale-{index}")
    return identities


def observe(host):
    """Read independently retained identities, associations and absence of inference."""
    with closing(sqlite3.connect(host / "source.db")) as db:
        db.row_factory = sqlite3.Row
        return {
            "groups": [dict(row) for row in db.execute("SELECT id,project_id,title FROM epics ORDER BY id")],
            "milestones": [dict(row) for row in db.execute("SELECT id,epic_id FROM milestones")],
            "tasks": [dict(row) for row in db.execute("SELECT id,epic_id,milestone_id,status FROM tasks ORDER BY id")],
            "dependencies": [dict(row) for row in db.execute("SELECT task_id,depends_on_task_id FROM task_dependencies ORDER BY task_id")],
            "runs": [dict(row) for row in db.execute("SELECT id,status FROM runtime_runs ORDER BY id")],
            "peers": [dict(row) for row in db.execute("SELECT kind,state FROM runtime_peers")],
            "dispatches": db.execute("SELECT count(*) FROM runtime_inference_dispatches").fetchone()[0],
            "native_starts": db.execute("SELECT count(*) FROM runtime_attempts WHERE turn_id IS NOT NULL").fetchone()[0],
            "integrity": db.execute("PRAGMA integrity_check").fetchone()[0],
            "foreign_keys": db.execute("PRAGMA foreign_key_check").fetchall(),
        }


def main():
    """Own a fresh synthetic installation, service and browser through closure, retaining failures."""
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
        json.dump({"auth_mode": "chatgpt", "tokens": {"access_token": "synthetic.header.signature", "account_id": "synthetic-planning-review"}}, stream)
    assets.update(token_file=str(token), static_dir=str(ROOT / "frontend/dist"))
    assets.pop("storage", None)
    host = output / "host"
    initialize_host(host, witness_dir=output / "witness", assets=assets)
    identities = seed(host)
    fixture = output / "fixture.json"
    fixture.write_text(json.dumps(identities, indent=2) + "\n")
    result = {"status": "running", "synthetic_domain_history": True, "model_turns": 0, "backend": str(Path(backend.__file__).resolve()), "web_index_sha256": hashlib.sha256((ROOT / "frontend/dist/index.html").read_bytes()).hexdigest(), "before": observe(host)}
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
            browser = subprocess.run([str(args.node.resolve(strict=True)), "tests/planning.e2e.mjs"], cwd=ROOT / "frontend", env=env, stdout=browser_log, stderr=subprocess.STDOUT, check=False)
        result["browser_exit"] = browser.returncode
        assert browser.returncode == 0, "Inspect the original browser log"
        after = observe(host)
        assert after["dispatches"] == after["native_starts"] == 0
        assert after["integrity"] == "ok" and not after["foreign_keys"]
        assert all(row["state"] == "closed" for row in after["peers"])
        assert after["runs"] == result["before"]["runs"]
        assert after["dependencies"] == result["before"]["dependencies"]
        assert {row["id"] for row in after["groups"]} == {row["id"] for row in result["before"]["groups"]} - {identities["manual"]}
        assert all(row["epic_id"] is None and row["milestone_id"] is None for row in after["tasks"] if row["id"] in identities["manualTasks"])
        assert len(after["tasks"]) == len(result["before"]["tasks"])
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
