"""Verify installed agent history/control using synthetic receipts, never model execution.

A stored synthetic turn and dispatch/usage receipt exercise attribution and budget
presentation. They do not represent provider work or an observed native launch.
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
from overview_page import seed as seed_overview
from planning_page import observe as observe_planning

ROOT = Path(__file__).resolve().parents[2]


def seed(host):
    """Add terminal domain runs and one explicitly synthetic usage receipt for actual owner reads."""
    from backend.db.connection import connect
    from backend.runtime.codex_session import ExecutionLimits
    from backend.runtime.contracts import RunSpec
    from backend.runtime.peer_registry import AttemptPeers
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.runtime.workspaces import WorkspaceRegistry

    ids = seed_overview(host)
    database = host / "source.db"
    with closing(connect(database)) as db, db:
        db.execute("INSERT INTO tasks(id,project_id,type,title,status) VALUES(1300,101,'research','Historia sintética sin modelos ejecutados','in_progress')")
    runs = SQLiteRunStore(database)
    binding = WorkspaceRegistry(database, host / "sources").bind(101)
    for index in range(27):
        spec = RunSpec(101, 1300, f"synthetic-history-{index % 3}", runs.context_snapshot(101, 1300)["context_version"], f"fixture-terminal-{index}", "Synthetic terminal history; no model was launched.", "codex")
        run = runs.admit(spec, binding=binding)
        lease, peers = AttemptPeers.claim(runs, 101, run.run_id, "synthetic-never-launched-owner")
        if index == 0:
            runs.bind_thread(lease, thread_id="synthetic-never-launched-measurement")
            runs.reserve_inference(lease, workspace=binding.workspace, catalog_hash="a" * 64, limits=ExecutionLimits(60, 30, 1, 10, 100), model="synthetic-never-launched-model", project_turn_limit=2, project_token_limit=200)
            runs.note_inference_usage(lease, 55)
            runs.settle_inference(lease, observed_tokens=55, native_status="failed")
            ids["measured"] = run.run_id
        for peer in peers.ids.values():
            peers.registry.close(peer)
        runs.finish(lease, native_status="failed", summary="Synthetic terminal fixture; no native process or model was launched.")
        runs.retire_inference(lease, outcome="failed")
        ids["unknown"] = run.run_id
    return ids


def observe(host):
    """Extend the shared independent snapshot with original budget-policy effect counts."""
    from backend.db.connection import connect

    value = observe_planning(host)
    with closing(connect(host / "source.db")) as db:
        value["budget"] = dict(db.execute("SELECT * FROM runtime_project_budgets WHERE project_id=101").fetchone())
        value["policy_changes"] = db.execute("SELECT COUNT(*) FROM runtime_project_budget_changes WHERE project_id=101").fetchone()[0]
    return value


def main():
    """Own a new installed host and owner browser through closure without copying real credentials."""
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
        json.dump({"auth_mode": "chatgpt", "tokens": {"access_token": "synthetic.header.signature", "account_id": "synthetic-agents-review"}}, stream)
    assets.update(token_file=str(token), static_dir=str(ROOT / "frontend/dist"))
    assets.pop("storage", None)
    host = output / "host"
    initialize_host(host, witness_dir=output / "witness", assets=assets)
    ids = seed(host)
    fixture = output / "fixture.json"
    fixture.write_text(json.dumps(ids, indent=2) + "\n")
    before = observe(host)
    assert before["dispatches"] == 1  # Synthetic journal receipt; no inference.
    assert all(row["state"] == "closed" for row in before["peers"])
    assert all(row["status"] in ("needs_review", "accepted", "waiting_input", "failed") for row in before["runs"])
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
            browser = subprocess.run([str(args.node.resolve(strict=True)), "tests/agents.e2e.mjs"], cwd=ROOT / "frontend", env=env, stdout=browser_log, stderr=subprocess.STDOUT, check=False)
        result["browser_exit"] = browser.returncode
        assert browser.returncode == 0, "Inspect the original browser log"
        after = observe(host)
        assert after["groups"] == before["groups"] and after["tasks"] == before["tasks"]
        assert after["dependencies"] == before["dependencies"] and after["peers"] == before["peers"]
        assert after["dispatches"] == before["dispatches"] == 1
        assert after["native_starts"] == before["native_starts"] == 1
        assert len(after["runs"]) == len(before["runs"]) == 30
        expected = {row["id"]: row["status"] for row in before["runs"]}
        expected[ids["question"]["run"]] = "cancelled"
        assert {row["id"]: row["status"] for row in after["runs"]} == expected
        assert after["budget"]["revision"] == before["budget"]["revision"] + 1
        assert after["budget"]["turn_limit"] == 4 and after["budget"]["token_limit"] == 1000
        assert after["policy_changes"] == before["policy_changes"] + 1
        assert after["integrity"] == "ok" and not after["foreign_keys"]
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
