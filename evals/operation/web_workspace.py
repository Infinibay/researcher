"""Run owner web journeys against a fresh installed service and real SQLite.

Accounts are synthetic by default; the explicit projects mode admits up to two
real subscription planning attempts with lower operator ceilings preserved.

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
    """Read durable owner records and inference counts independently of visible browser labels."""
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        return {
            "projects": [dict(row) for row in db.execute("SELECT id,name,description FROM projects ORDER BY id")],
            "groups": [dict(row) for row in db.execute("SELECT id,project_id,title FROM epics ORDER BY id")],
            "milestones": [dict(row) for row in db.execute("SELECT id,epic_id,title FROM milestones ORDER BY id")],
            "tasks": [dict(row) for row in db.execute("SELECT id,project_id,epic_id,title,status FROM tasks ORDER BY id")],
            "dependencies": [dict(row) for row in db.execute("SELECT task_id,depends_on_task_id FROM task_dependencies")],
            "corrections": [dict(row) for row in db.execute("SELECT project_id,task_id,version,statement,source_kind FROM runtime_context_revisions ORDER BY version")],
            "files": [dict(row) for row in db.execute("SELECT id,project_id,file_name,file_path,file_size,file_type FROM reference_files ORDER BY id")],
            "file_operations": [dict(row) for row in db.execute("SELECT project_id,operation_key,kind,state,reference_id,relative_path,request_json FROM reference_file_operations ORDER BY created_at,operation_key")],
            "captured_sources": db.execute("SELECT COUNT(*) FROM research_sources").fetchone()[0],
            "wiki": [dict(row) for row in db.execute("SELECT id,project_id,path,title,content FROM wiki_pages ORDER BY id")],
            "wiki_revisions": [dict(row) for row in db.execute("SELECT page_id,project_id,revision,content FROM wiki_revisions ORDER BY page_id,revision")],
            "runs": db.execute("SELECT COUNT(*) FROM runtime_runs").fetchone()[0],
            "dispatches": db.execute("SELECT COUNT(*) FROM runtime_inference_dispatches").fetchone()[0],
            "native_starts": db.execute("SELECT COUNT(*) FROM runtime_attempts WHERE turn_id IS NOT NULL").fetchone()[0],
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
    parser.add_argument("--journey", choices=("workspace", "knowledge", "wiki", "files", "navigation", "interaction", "projects"), default="workspace")
    parser.add_argument("--live-projects", action="store_true", help="Authorize up to two real subscription planning attempts in the projects journey")
    args = parser.parse_args()
    if (args.journey == 'projects') != args.live_projects:
        parser.error('The projects journey requires --live-projects; other journeys use no real account')
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
    if not args.live_projects:
        assets["token_file"] = str(token)
    else:
        caps = {'wall_seconds':180,'no_progress_seconds':90,'max_turns':1,'max_tool_calls':20,'max_observed_tokens':350000,'max_answer_bytes':20000}
        assets['limits'] = {**assets.get('limits',{}), **{k:min(assets.get('limits',{}).get(k,v),v) for k,v in caps.items()}}
        assets['project_turn_limit'] = min(assets.get('project_turn_limit',2),2)
        assets['project_token_limit'] = min(assets.get('project_token_limit',700000),700000)
        if assets['project_turn_limit'] < 2 or assets['project_token_limit'] < 2*assets['limits']['max_observed_tokens']:
            raise ValueError('Combined Stop/planning journey requires two preparation reservations; supplied project ceilings are too small. No host or model was started.')
    assets["static_dir"] = str(ROOT / "frontend/dist")
    # This trial does not adopt an operator volume or reuse its data paths.
    assets.pop("storage", None)
    host = output / "host"
    initialize_host(host, witness_dir=output / "witness", assets=assets)
    source = host/'sources'/'observations'
    source_before = None
    if args.live_projects:
        source.mkdir()
        (source/'observations.py').write_text('"""List retained observations without exporting files."""\ndef list_observations(records):\n    """Return original records in order."""\n    return list(records)\n')
        source_before = hashlib.sha256((source/'observations.py').read_bytes()).hexdigest()
    with socket.socket() as binding:
        binding.bind(("127.0.0.1", 0))
        port = binding.getsockname()[1]
    result = {"status": "running", "journey": args.journey, "backend": str(Path(backend.__file__).resolve()),
              "model_turns": None if args.live_projects else 0, "maximum_model_turns":2 if args.live_projects else 0, "mocked_api_responses": False,
              "web_index_sha256": hashlib.sha256((ROOT / "frontend/dist/index.html").read_bytes()).hexdigest()}
    process = log = None
    try:
        process, log = start(host, output, port, 1)
        keys = list((host / "auth").glob("owner-*.key"))
        if len(keys) != 1:
            raise RuntimeError("Expected one private pairing file for the new host")
        env = {**os.environ, "RESEARCHER_E2E_ORIGIN": f"http://127.0.0.1:{port}",
               "RESEARCHER_E2E_OWNER_FILE": str(keys[0]), "RESEARCHER_E2E_OUTPUT": str(output / "browser")}
        if args.live_projects:
            env['RESEARCHER_E2E_PROJECT_SOURCE'] = str(source)
        if args.journey == "files":
            env["RESEARCHER_E2E_FILE_FIXTURES"] = str(prepare_file_fixtures(output))
            env["RESEARCHER_E2E_DATABASE"] = str(host / "source.db")
            env["RESEARCHER_E2E_PYTHON"] = sys.executable
        script = args.journey
        if args.journey == "navigation":
            script = "workspace"
            env["RESEARCHER_E2E_NAVIGATION"] = "1"
        if args.journey == "interaction":
            script = "workspace"
            env["RESEARCHER_E2E_INTERACTION"] = "1"
        with (output / "browser.log").open("x") as browser_log:
            browser = subprocess.run([str(args.node.resolve(strict=True)), f"tests/{script}.e2e.mjs"],
                                     cwd=ROOT / "frontend", env=env,
                                     stdout=browser_log, stderr=subprocess.STDOUT, check=False)
        result["browser_exit"] = browser.returncode
        result["storage"] = observe(host / "source.db")
        if not args.live_projects:
            assert result["storage"]["runs"] == result["storage"]["dispatches"] == 0
        assert result["storage"]["integrity"] == "ok"
        assert browser.returncode == 0, "Inspect the original browser log and screenshots"
        assert len(result["storage"]["projects"]) == 2
        browser_evidence = json.loads((output / "browser/evidence.json").read_text())
        ids = browser_evidence["identities"]
        if args.live_projects:
            assert result['storage']['runs'] == 2 and result['storage']['dispatches'] <= 2
            assert source_before == hashlib.sha256((source/'observations.py').read_bytes()).hexdigest()
            result['model_turns'] = result['storage']['native_starts']
            result['source_unchanged'] = True
        elif args.journey in ("workspace", "navigation", "interaction"):
            assert len(result["storage"]["tasks"]) == 2
            assert len(result["storage"]["groups"]) == len(result["storage"]["milestones"]) == 1
            assert len(result["storage"]["dependencies"]) == 1
            assert all(task["project_id"] == ids["alpha"] for task in result["storage"]["tasks"])
            correction, = result["storage"]["corrections"]
            assert (correction["project_id"], correction["task_id"], correction["version"], correction["source_kind"]) == (ids["alpha"], ids["compare"], 2, "user_example")
        elif args.journey == "wiki":
            verify_wiki(result["storage"], browser_evidence)
        elif args.journey == "files":
            verify_files(result["storage"], browser_evidence, host)
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
        if args.live_projects:
            result['model_turns'] = result['storage_after_close']['native_starts']
            result['source_unchanged'] = source_before == hashlib.sha256((source/'observations.py').read_bytes()).hexdigest()
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"status": result["status"], "receipt": str(output / "result.json")}), flush=True)


def verify_files(storage, browser, host):
    """Match scoped original upload receipts to actual retained bytes and explicit deletions/abandonment, independently of UI success labels."""
    assert browser["status"] == "passed" and not browser["errors"]
    assert not storage["tasks"] and not storage["wiki"]
    assert storage["captured_sources"] == 0
    deleted = set(browser["deleted"])
    expected = {row["id"]: row for row in browser["files"] if row["id"] not in deleted}
    actual = {row["id"]: row for row in storage["files"]}
    assert set(actual) == set(expected)
    root = (host / "uploads").resolve(strict=True)
    for file_id, row in actual.items():
        original = expected[file_id]
        assert row["project_id"] == original["project"] and row["file_name"] == original["name"]
        path = Path(row["file_path"])
        assert not path.is_symlink() and path.resolve(strict=True).is_relative_to(root)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == original["sha256"]
    operations = {(row["project_id"], row["operation_key"]): row for row in storage["file_operations"]}
    for original in browser["files"]:
        row = operations[original["project"], original["operation_key"]]
        assert row["kind"] == "upload" and row["state"] == "published" and row["reference_id"] == original["id"]
    for file_id in deleted:
        row = operations[browser["identities"]["alpha"], f"delete:{file_id}"]
        assert row["state"] == "deleted" and file_id not in actual
    abandoned = browser["abandoned"]
    row = operations[abandoned["project_id"], abandoned["operation_key"]]
    assert row["state"] == "abandoned" and row["reference_id"] is None
    path = root / row["relative_path"]
    assert path.resolve(strict=True).is_relative_to(root) and path.read_bytes() == abandoned["expected_bytes"].encode()
    assert all(row["state"] != "pending" for row in operations.values())


def prepare_file_fixtures(output):
    """Reuse real test-format byte builders for a disposable owner journey, without new office dependencies or model calls."""
    from backend.tests.research.pdf_fixtures import pdf_bytes
    from backend.tests.research.structured_fixtures import formats

    root = output / "file-fixtures"
    root.mkdir(mode=0o700)
    values = [("pdf", "application/pdf", pdf_bytes("CSV export preserves id and value.", "The plan does not execute pending tasks.")), *formats()]
    manifest = []
    for extension, mime, content in values:
        path = root / ("original." + extension)
        path.write_bytes(content)
        manifest.append({"name": path.name, "path": str(path), "mime": mime,
                         "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)})
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return path


def verify_wiki(storage, browser):
    """Check real route effects independently: scoped current pages, exact retained history and deletion without losing the original text."""
    ids = browser["identities"]
    assert browser["result"] == "passed" and not browser["errors"]
    assert not storage["tasks"] and not storage["files"]
    assert len(storage["wiki"]) == 58
    pages = {row["id"]: row for row in storage["wiki"]}
    own, foreign = pages[ids["context"]], pages[ids["foreign"]]
    assert own["project_id"] == ids["alpha"] and foreign["project_id"] == ids["beta"]
    assert own["path"] == foreign["path"] == "modernization/context"
    assert foreign["content"] == "OTHER PROJECT SECRET"
    history = sorted(
        (row for row in storage["wiki_revisions"] if row["page_id"] == own["id"]),
        key=lambda row: row["revision"],
    )
    assert [row["revision"] for row in history] == list(range(1, 26))
    assert all(row["project_id"] == ids["alpha"] for row in history)
    assert history[-1]["content"] == own["content"]
    assert "Revisión adicional 20." in own["content"]
    deleted = [row for row in storage["wiki_revisions"] if "<img src=x onerror=window.wikiXss=1>" in row["content"]]
    assert len(deleted) == 1 and deleted[0]["project_id"] == ids["alpha"]
    assert deleted[0]["page_id"] not in pages
    assert sum(row["project_id"] == ids["alpha"] for row in pages.values()) == 56
    globals_ = [row for row in pages.values() if row["project_id"] is None]
    assert len(globals_) == 1 and "Nota global actualizada" in globals_[0]["content"]


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
