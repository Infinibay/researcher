"""Inspect saved findings/reports on installed owner HTTP without generative models.

Domain history contains two explicit synthetic native turn IDs and never-launched,
closed logical peers. Documentary acceptance here is a fixture, not human approval.
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
from planning_page import observe as observe_planning

ROOT = Path(__file__).resolve().parents[2]


def seed(host):
    """Write actual scoped sources/findings/draft reports and one accepted documentary fixture."""
    from backend.db.connection import connect
    from backend.research.models import RESEARCH_PERMISSIONS, EvidenceReference, FindingDraft, ReportDraft, ResultDraft, SourceDraft
    from backend.research.sqlite_store import SQLiteResearchStore
    from backend.runtime.contracts import RunSpec
    from backend.runtime.peer_registry import AttemptPeers
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.runtime.workspaces import WorkspaceRegistry

    database = host / "source.db"
    folder = host / "sources" / "inventory"
    folder.mkdir()
    (folder / "inventory.txt").write_text("Synthetic documentary fixture; not an independently measured inventory.\n")
    with closing(connect(database)) as db, db:
        db.execute("INSERT INTO projects(id,name,description) VALUES(101,'Inventario documentado','Comprobar qué afirma el inventario, sus fuentes y sus límites.'),(202,'Archivo separado','Sin los documentos del inventario.')")
        db.execute("INSERT INTO repositories(id,project_id,name,local_path) VALUES(11,101,'inventory',?)", (str(folder),))
        db.execute("INSERT INTO tasks(id,project_id,type,title,status) VALUES(1001,101,'research','Examinar el inventario documental','in_progress'),(1002,101,'research','Aceptar un resultado documental sintético','in_progress')")
    runs, research = SQLiteRunStore(database), SQLiteResearchStore(database)
    binding = WorkspaceRegistry(database, host / "sources").bind(101)
    ids = {"alpha": 101, "beta": 202}
    quote = "El inventario sintético registra 20 piezas en total."
    body = "## Objetivo y datos\n\nEntrada: un inventario documental sintético. Salida: un resumen de lo que declara y de lo que falta comprobar.\n\n| Registro | Piezas declaradas |\n| --- | --- |\n| Colección A | 12 |\n| Colección B | 8 |\n| Total declarado | 20 |\n\n## Límite\n\nNo se contaron las piezas físicamente ni se comprobó que el inventario esté actualizado. Una cita exacta permite leer lo declarado; no demuestra que sea correcto."
    for task, accepted in ((1001, False), (1002, True)):
        spec = RunSpec(101, task, "synthetic-documentary-author", runs.context_snapshot(101, task)["context_version"], f"fixture-evidence-{task}", "Leer el inventario documental y conservar sus límites.", "codex")
        run = runs.admit(spec, binding=binding)
        lease, peers = AttemptPeers.claim(runs, 101, run.run_id, "synthetic-never-launched-owner")
        runs.bind_native(lease, thread_id=f"synthetic-never-launched-thread-{task}", turn_id=f"synthetic-never-launched-turn-{task}")
        token = research.issue_grant(project_id=101, task_id=task, agent_id=spec.actor_id, permissions=set(RESEARCH_PERMISSIONS))
        scope = research.authorize(token)
        runs.bind_grant(lease, scope.grant_id)
        source = research.capture_source(scope, "inventory-source", SourceDraft("web", "https://example.org/synthetic-inventory", "Inventario sintético conservado", "Detalle documental repetido para comprobar fragmentos. " * 250 + quote, provenance={"fixture": True, "independently_measured": False}), intent={"synthetic_fixture": True})
        finding = research.record_finding(scope, "inventory-finding", FindingDraft("El inventario declara 20 piezas" if not accepted else "Resultado documental aceptado de ejemplo", body + ("\n\nDetalle de lectura del inventario. " * 400 if not accepted else ""), (EvidenceReference(source["source_id"], quote),)))
        report = research.write_report(scope, "inventory-report", ReportDraft("Resumen del inventario documental" if not accepted else "Resultado documental aceptado", body, (finding["finding_id"],)))
        entry = {"task": task, "run": run.run_id, "source": source["source_id"], "finding": finding["finding_id"], "report": report["artifact_id"], "quote": quote}
        if not accepted:
            for index in range(50):
                catalog_finding = research.record_finding(scope, f"catalog-finding-{index}", FindingDraft(f"Nota documental {index + 1:02d}", "Registro sintético para comprobar paginación y filtros, sin una nueva medición.", (EvidenceReference(source["source_id"], quote),), finding_type="hypothesis"))
                research.write_report(scope, f"catalog-report-{index}", ReportDraft(f"Apunte de inventario {index + 1:02d}", "Registro sintético de catálogo. No acredita revisión independiente.", (catalog_finding["finding_id"],), report_type="summary"))
        else:
            research.propose_result(scope, "synthetic-delivery", ResultDraft((report["artifact_id"],), "Resumen documental sintético.", ("No se repitió el recuento físico.",)))
        for peer in peers.ids.values():
            peers.registry.close(peer)
        runs.finish(lease, native_status="completed", summary="Synthetic documentary fixture; no model or process was launched.")
        if accepted:
            state = runs.result_state(101, run.run_id)
            runs.accept_result(101, run.run_id, operation_key="synthetic-owner-acceptance", candidate_id=state["candidate"]["candidate_id"], candidate_sha256=state["candidate"]["candidate_sha256"], context_version=lease.context_version, review_sha256=state["review_sha256"], acknowledge_limits=True, note="Synthetic documentary fixture, not human evaluation.")
        ids["accepted" if accepted else "draft"] = entry
    with closing(connect(database)) as db, db:
        ids["legacyFinding"] = db.execute("INSERT INTO findings(project_id,task_id,topic,content,agent_id,status,confidence,finding_type,sources_json) VALUES(101,1001,'Declaración histórica sin revisión','Una etiqueta antigua no demuestra certeza.','legacy-fixture','active',0.9,'conclusion','[\"https://example.org/historical-unverified\"]')").lastrowid
        ids["legacyArtifact"] = db.execute("INSERT INTO artifacts(project_id,task_id,type,file_path,description,content) VALUES(101,1001,'code','examples/inventory.py','Archivo histórico de ejemplo','print(20)')").lastrowid
    return ids


def observe(host):
    """Bind source/finding/report bytes and metadata independently of UI success messages."""
    from backend.db.connection import connect

    value = observe_planning(host)
    with closing(connect(host / "source.db")) as db:
        value["sources"] = [dict(row) for row in db.execute("SELECT id,project_id,sha256 FROM research_sources ORDER BY id")]
        value["findings"] = [{"id": row["id"], "status": row["status"], "content_sha256": hashlib.sha256(row["content"].encode()).hexdigest()} for row in db.execute("SELECT id,status,content FROM findings ORDER BY id")]
        value["artifacts"] = [{"id": row["id"], "content_sha256": hashlib.sha256(row["content"].encode()).hexdigest()} for row in db.execute("SELECT id,content FROM artifacts ORDER BY id")]
        value["reports"] = [dict(row) for row in db.execute("SELECT artifact_id,status,content_sha256 FROM research_reports ORDER BY artifact_id")]
    return value


def main():
    """Own a new installed host and evidence browser through closure without copying real credentials."""
    import backend
    from backend.runtime.host_installation import initialize_host

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--retrieval-assets", type=Path, help="Explicit already-prepared pinned local weights; require the positive semantic path")
    args = parser.parse_args()
    if not Path(backend.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError("Use the separately installed product Python")
    output = args.output.resolve()
    output.mkdir(mode=0o700)
    assets = json.loads(args.assets.read_text())
    token = output / "synthetic-account.json"
    with token.open("x") as stream:
        os.chmod(token, 0o600)
        json.dump({"auth_mode": "chatgpt", "tokens": {"access_token": "synthetic.header.signature", "account_id": "synthetic-evidence-review"}}, stream)
    assets.update(token_file=str(token), static_dir=str(ROOT / "frontend/dist"))
    if args.retrieval_assets is not None:
        assets['retrieval_asset_dir'] = str(args.retrieval_assets.resolve(strict=True))
    assets.pop("storage", None)
    host = output / "host"
    initialize_host(host, witness_dir=output / "witness", assets=assets)
    ids = seed(host)
    fixture = output / "fixture.json"
    fixture.write_text(json.dumps(ids, indent=2) + "\n")
    before = observe(host)
    assert before["dispatches"] == 0
    assert all(row["state"] == "closed" for row in before["peers"])
    assert all(row["status"] in ("needs_review", "accepted") for row in before["runs"])
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
        if args.retrieval_assets is not None:
            env['RESEARCHER_E2E_EXPECT_SEMANTIC'] = '1'
        with (output / "browser.log").open("x") as browser_log:
            browser = subprocess.run([str(args.node.resolve(strict=True)), "tests/evidence.e2e.mjs"], cwd=ROOT / "frontend", env=env, stdout=browser_log, stderr=subprocess.STDOUT, check=False)
        result["browser_exit"] = browser.returncode
        assert browser.returncode == 0, "Inspect the original browser log"
        assert observe(host) == before, "Evidence readers must preserve original source/finding/report/run records"
        result["status"] = "passed"
    except BaseException as error:
        result.update(status="failed", error_type=type(error).__name__)
        raise
    finally:
        if process is not None:
            result["service_exit"] = stop(process, log)
        result["after"] = observe(host)
        from backend.db.connection import connect
        with closing(connect(host / 'source.db')) as db:
            result['local_work'] = [dict(row) for row in db.execute('SELECT kind,status,observed_cpu_ms,cpu_ceiling_ms,finished_at FROM runtime_auxiliary_work ORDER BY created_at')]
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"status": result["status"], "receipt": str(output / "result.json")}), flush=True)


if __name__ == "__main__":
    main()
