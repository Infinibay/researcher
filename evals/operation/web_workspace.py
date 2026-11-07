"""Run owner web CRUD against a fresh installed service, real SQLite and a synthetic account.

The browser drives forms, not mocked API responses. The private original host is
retained for inspection; this evaluation never opens an operator's existing data.
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


def observe(database):
    """Read durable owner records and prove that the browser did not create inference work."""
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        return {
            "projects": [dict(row) for row in db.execute("SELECT id,name,description FROM projects ORDER BY id")],
            "groups": [dict(row) for row in db.execute("SELECT id,project_id,title FROM epics ORDER BY id")],
            "milestones": [dict(row) for row in db.execute("SELECT id,epic_id,title FROM milestones ORDER BY id")],
            "tasks": [dict(row) for row in db.execute("SELECT id,project_id,epic_id,title,status FROM tasks ORDER BY id")],
            "dependencies": [dict(row) for row in db.execute("SELECT task_id,depends_on_task_id FROM task_dependencies")],
            "corrections": [dict(row) for row in db.execute("SELECT project_id,task_id,version,statement,source_kind FROM runtime_context_revisions ORDER BY version")],
            "files": [dict(row) for row in db.execute("SELECT id,project_id,file_name,file_path FROM reference_files ORDER BY id")],
            "wiki": [dict(row) for row in db.execute("SELECT id,project_id,path,title,content FROM wiki_pages ORDER BY id")],
            "wiki_revisions": [dict(row) for row in db.execute("SELECT page_id,project_id,revision,content FROM wiki_revisions ORDER BY page_id,revision")],
            "runs": db.execute("SELECT COUNT(*) FROM runtime_runs").fetchone()[0],
            "dispatches": db.execute("SELECT COUNT(*) FROM runtime_inference_dispatches").fetchone()[0],
            "integrity": db.execute("PRAGMA integrity_check").fetchone()[0],
        }


def main():
    """Prepare synthetic resources, own the live service/browser, and preserve every result on failure."""
    import backend
    from backend.runtime.host_installation import initialize_host

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--journey", choices=("workspace", "knowledge", "navigation"), default="workspace")
    args = parser.parse_args()
    if not Path(backend.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError("Use the separately installed product Python, without PYTHONPATH")
    output = args.output.absolute()
    output.mkdir(mode=0o700)
    assets = json.loads(args.assets.read_text())
    token = output / "synthetic-account.json"
    with token.open("x") as stream:
        os.chmod(token, 0o600)
        json.dump({"auth_mode": "chatgpt", "tokens": {
            "access_token": "synthetic.header.signature", "account_id": "synthetic-web-evaluation"}}, stream)
    assets["token_file"] = str(token)
    assets["static_dir"] = str(ROOT / "frontend/dist")
    # This trial does not adopt an operator volume or reuse its data paths.
    assets.pop("storage", None)
    host = output / "host"
    initialize_host(host, witness_dir=output / "witness", assets=assets)
    with socket.socket() as binding:
        binding.bind(("127.0.0.1", 0))
        port = binding.getsockname()[1]
    result = {"status": "running", "journey": args.journey, "backend": str(Path(backend.__file__).resolve()),
              "model_turns": 0, "mocked_api_responses": False,
              "web_index_sha256": hashlib.sha256((ROOT / "frontend/dist/index.html").read_bytes()).hexdigest()}
    process = log = None
    try:
        process, log = start(host, output, port, 1)
        keys = list((host / "auth").glob("owner-*.key"))
        if len(keys) != 1:
            raise RuntimeError("Expected one private pairing file for the new host")
        env = {**os.environ, "RESEARCHER_E2E_ORIGIN": f"http://127.0.0.1:{port}",
               "RESEARCHER_E2E_OWNER_FILE": str(keys[0]), "RESEARCHER_E2E_OUTPUT": str(output / "browser")}
        script = args.journey
        if args.journey == "navigation":
            script = "workspace"
            env["RESEARCHER_E2E_NAVIGATION"] = "1"
        with (output / "browser.log").open("x") as browser_log:
            browser = subprocess.run([str(args.node.resolve(strict=True)), f"tests/{script}.e2e.mjs"],
                                     cwd=ROOT / "frontend", env=env,
                                     stdout=browser_log, stderr=subprocess.STDOUT, check=False)
        result["browser_exit"] = browser.returncode
        result["storage"] = observe(host / "source.db")
        assert result["storage"]["runs"] == result["storage"]["dispatches"] == 0
        assert result["storage"]["integrity"] == "ok"
        assert browser.returncode == 0, "Inspect the original browser log and screenshots"
        assert len(result["storage"]["projects"]) == 2
        browser_evidence = json.loads((output / "browser/evidence.json").read_text())
        ids = browser_evidence["identities"]
        if args.journey in ("workspace", "navigation"):
            assert len(result["storage"]["tasks"]) == 2
            assert len(result["storage"]["groups"]) == len(result["storage"]["milestones"]) == 1
            assert len(result["storage"]["dependencies"]) == 1
            assert all(task["project_id"] == ids["alpha"] for task in result["storage"]["tasks"])
            correction, = result["storage"]["corrections"]
            assert (correction["project_id"], correction["task_id"], correction["version"], correction["source_kind"]) == (ids["alpha"], ids["compare"], 2, "user_example")
        else:
            verify_knowledge(result["storage"], browser_evidence)
        result["status"] = "passed"
    except BaseException as error:
        result.update(status="failed", error_type=type(error).__name__)
        raise
    finally:
        if process is not None:
            result["service_exit"] = stop(process, log)
        result["storage_after_close"] = observe(host / "source.db")
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"status": result["status"], "receipt": str(output / "result.json")}), flush=True)


def verify_knowledge(storage, browser):
    """Match stored attachment bytes and wiki versions to the identities observed through the browser."""
    ids = browser["identities"]
    assert not storage["tasks"]
    assert len(storage["files"]) == 2
    for row in storage["files"]:
        expected = browser["attachments"][str(row["project_id"])]
        assert row["file_name"] == "muestra.csv" and row["id"] == expected["id"]
        assert hashlib.sha256(Path(row["file_path"]).read_bytes()).hexdigest() == expected["sha256"]
    assert len(storage["wiki"]) == 3
    assert {(row["project_id"], row["path"]) for row in storage["wiki"]} == {
        (ids["alpha"], "overview"), (ids["beta"], "overview"), (None, "overview")}
    for row in storage["wiki"]:
        expected = browser["documents"][str(row["project_id"]) if row["project_id"] is not None else "global"]
        assert row["id"] == expected["id"] and row["content"] == expected["content"]
    assert len(storage["wiki_revisions"]) == 4


if __name__ == "__main__":
    main()
