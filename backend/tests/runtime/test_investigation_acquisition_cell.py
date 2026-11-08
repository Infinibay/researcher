"""Validate authored acquisition cells with public Ken and real scoped adapters.

This explicit local integration uses prepared offline Ken resources, not an LLM
or subscription. Command wire peers and original native/business receipts use
the existing synthetic fixtures; kernel containment is tested elsewhere.
"""

import asyncio
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import httpx
import pytest

from backend.tests.runtime.test_investigation import investigation_state
from backend.tests.runtime.test_investigation_delivery_cell import execute_cell
from backend.tests.runtime.test_workspace_delivery import owner_client


def emitted_object(value, status):
    """Recover one structured text emission from the real code-host result."""
    if isinstance(value, str):
        try:
            return emitted_object(json.loads(value), status)
        except ValueError:
            return None
    if isinstance(value, dict):
        if value.get("status") == status:
            return value
        values = value.values()
    elif isinstance(value, list):
        values = value
    else:
        return None
    for item in values:
        found = emitted_object(item, status)
        if found is not None:
            return found
    return None


@pytest.mark.timeout(180)
@pytest.mark.parametrize("mode", ["complete", "truncated", "withdrawn", "changed"])
async def test_real_ken_acquisition_and_delivery_use_canonical_sources_without_base64(
    coordination, code_host_asset, tmp_path, monkeypatch, mode,
):
    """Two authored cells acquire complete actual sources then deliver a typed draft.

    The fixture does not prove that a model will write these programs, interpret
    the sources correctly or finish within its native inference token budget.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    from backend.api import config
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.research.models import RESEARCH_PERMISSIONS
    from backend.runtime.business_mediation import (
        INVESTIGATION_NAMES,
        BusinessTools,
        ProjectTools,
    )
    from backend.runtime.host_business import host_business
    from backend.runtime.ken_mediation import KenTools
    from backend.tests.runtime.test_analysis_tools import tools as analysis_tools

    command = os.environ.get("INFINIBAY_TEST_KEN_COMMAND")
    cache = os.environ.get("INFINIBAY_TEST_KEN_MODEL_CACHE")
    if not command or not cache:
        pytest.skip("Explicit prepared public Ken command/model cache not supplied")
    coordination.now[0] = time.time()
    c, run, lease, peers, _scope, _finding = investigation_state(coordination)
    lease = c.store.heartbeat(lease, lease_seconds=120)
    token = c.research.issue_grant(
        project_id=101, task_id=1001, agent_id=lease.actor_id,
        permissions=set(RESEARCH_PERMISSIONS),
    )
    scope = c.research.authorize(token)
    c.store.bind_grant(lease, scope.grant_id)
    repository = Path(os.environ.get("INFINIBAY_TEST_CASE_ROOT", Path(__file__).resolve().parents[3]))
    code = (repository / "backend/runtime/model_settings.py").read_bytes()
    workspace = tmp_path / "source"
    workspace.mkdir()
    (workspace / "evidence.py").write_bytes(code)
    uploads = tmp_path / "uploads"
    project_uploads = uploads / "101/uploads"
    project_uploads.mkdir(parents=True)
    document = project_uploads / "policy.md"
    document.write_bytes((repository / "docs/architecture/model-configuration.md").read_bytes())
    monkeypatch.setattr(config, "UPLOAD_DIR", str(uploads))
    c.conn.execute(
        "INSERT INTO reference_files(id,project_id,file_name,file_path,file_size,file_type) "
        "VALUES(1,101,'policy.md',?,?,'text/markdown')",
        (str(document), document.stat().st_size),
    )
    c.conn.commit()
    app = create_app(access=LocalAccess(
        pairing_key="workspace-owner-key-at-least-32-characters",
    ))
    app.state.live_grants.activate(scope.grant_id)
    identity = workspace.stat()
    worker = [
        sys.executable, "-I", "-m", "backend.runtime.ken_worker",
        "--ken-command", command, "--model-cache", cache,
        "--workspace", str(workspace),
        "--expected-device", str(identity.st_dev),
        "--expected-inode", str(identity.st_ino),
    ]
    # This selected offline preparation is explicit and uses the actual pinned
    # public package/grammars/model manifests. It never downloads replacements.
    prepare = await asyncio.create_subprocess_exec(
        *worker, "--prepare", stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(prepare.communicate(), 90)
        assert prepare.returncode == 0, (stdout.decode(), stderr.decode())
    finally:
        if prepare.returncode is None:
            prepare.kill()
            await prepare.wait()
    server = StdioServerParameters(command=worker[0], args=worker[1:])
    request = {
        "query": "Find the model settings module that selects a model and reasoning effort pair",
        "path": "evidence.py", "reference": "policy.md",
        "expected_lines": len(code.decode().splitlines()),
        "expected_sha256": "0" * 64 if mode == "changed" else hashlib.sha256(code).hexdigest(),
        "key": "composed-acquisition", "max_calls": 17,
        "output_bytes": 32 if mode == "truncated" else 65536,
    }
    template = (repository / "evals/communication/acquire_evidence.js").read_text()
    assert template.count("const request = __REQUEST__;") == 1
    acquisition = template.replace("const request = __REQUEST__;", "const request = " + json.dumps(request) + ";")
    with open(os.devnull, "w") as errors:  # noqa: ASYNC230 — kernel null device, no file data
        async with (
            stdio_client(server, errlog=errors) as streams,
            ClientSession(*streams) as ken_peer,
            host_business(
                api_url="http://127.0.0.1", token=token,
                withdraw=lambda: app.state.live_grants.withdraw(scope.grant_id),
                names=INVESTIGATION_NAMES, transport=httpx.ASGITransport(app=app),
            ) as business_peer,
            analysis_tools(c, workspace, lease) as analysis,
        ):
            await ken_peer.initialize()
            ken = await KenTools.connect(ken_peer)
            business = await BusinessTools.connect(business_peer)
            facade = ProjectTools(business, analysis, ken)
            if mode == "withdrawn":
                original_call = facade.call

                async def withdraw_at_capture(params):
                    """Withdraw the real API grant at the acquisition write boundary."""
                    if params["tool"] == "researcher_capture_command":
                        app.state.live_grants.withdraw(scope.grant_id)
                    return await original_call(params)

                monkeypatch.setattr(facade, "call", withdraw_at_capture)
            marker = "ACQUISITION_READY" if mode == "complete" else "ACQUISITION_STOPPED"
            acquired = await execute_cell(
                code_host_asset, facade, acquisition,
                marker=marker, yield_ms=30000,
            )
            evidence = emitted_object(acquired["output"], marker)
            assert evidence is not None, acquired["output"]
            output = os.environ.get("INFINIBAY_TEST_EVIDENCE_DIR")
            folder = Path(output) / mode if output else None
            if folder is not None:
                folder.mkdir(parents=True, exist_ok=True)
                (folder / "acquisition.json").write_text(json.dumps(acquired, indent=2) + "\n")
            if mode != "complete":
                assert evidence["reason"] == {
                    "truncated": "command_incomplete",
                    "withdrawn": "tool_refused",
                    "changed": "captured_code_changed",
                }[mode]
                assert c.conn.execute("SELECT COUNT(*) FROM research_reports").fetchone()[0] == 0
                assert c.conn.execute("SELECT COUNT(*) FROM runtime_result_proposals").fetchone()[0] == 0
                if mode == "truncated":
                    assert "researcher_capture_command" not in acquired["calls"]
                    assert c.store.get_job(101, evidence["receipts"]["job_id"]).output_limited
                if mode == "withdrawn":
                    assert "code_source_id" not in evidence["receipts"]
                for peer_id in peers.ids.values():
                    peers.registry.close(peer_id)
                c.store.finish(lease, native_status="failed", summary="Acquisition fixture stopped.")
                assert not c.store.result_state(101, run.run_id)["eligible"]
                return
            sources = evidence["sources"]
            assert len(sources) == 2
            assert all(source["next_offset"] is None for source in sources)
            assert sources[1]["provenance"]["job"]["stdout_sha256"] == hashlib.sha256(code).hexdigest()
            assert code.decode() in sources[1]["content"]
            assert (workspace / "evidence.py").read_bytes() == code
            assert '"base64":' not in json.dumps(evidence)
            assert acquired["calls"].count("researcher_command_start") == 1
            assert "ken_find" in acquired["calls"] and "ken_read" in acquired["calls"]
            reads = [row for row in acquired["invocations"] if row["tool"] == "researcher_command_read"]
            assert reads and all(row["arguments"]["max_bytes"] == 1 for row in reads)
            assert all(len(json.loads(row["response"]["contentItems"][0]["text"])["stdout"]["text"]) <= 1 for row in reads)
            # The model would inspect the emitted code/document here. This
            # authored second cell demonstrates only the dependent-ID contract.
            packet = {
                "title": "Recorded model selection",
                "question": "What input pair does the captured code validate?",
                "scope_includes": ["Inspect the captured model_profile function."],
                "scope_excludes": ["Change settings or check account eligibility."],
                "areas": [{"title": "Input pair", "observations": "The code returns model and reasoning_effort together.", "finding_ids": []}],
                "conclusion": "The captured function validates a model and reasoning-effort pair.",
                "limitations": ["Static source observation, not current account availability."],
                "next_steps": [],
            }
            finding = {
                "operation_key": "composed-finding", "topic": "Model input pair",
                "content": "The captured function returns model and reasoning_effort together.",
                "evidence": [{"source_id": sources[1]["source_id"],
                              "quote": "return {'model':model,'reasoning_effort':reasoning_effort}"}],
            }
            delivery = """
function unwrap(reply) {
  if (!reply.success) throw new Error('Delivery stopped; reconcile original receipts');
  return JSON.parse(reply.contentItems[0].text);
}
const finding = unwrap(await tools.researcher_finding_record(__FINDING__));
const packet = __PACKET__;
packet.areas[0].finding_ids = [finding.finding_id];
const report = unwrap(await tools.researcher_investigation_summary({operation_key:'composed-summary',summary:packet}));
const proposal = unwrap(await tools.researcher_result_propose({operation_key:'composed-proposal',report_ids:[report.artifact_id],summary:packet.conclusion,limitations:packet.limitations}));
text({status:'DELIVERY_READY',report_id:report.artifact_id,proposal});
""".replace("__FINDING__", json.dumps(finding)).replace("__PACKET__", json.dumps(packet))
            delivered = await execute_cell(code_host_asset, facade, delivery)
            result = emitted_object(delivered["output"], "DELIVERY_READY")
            assert result is not None, delivered["output"]
            assert delivered["calls"] == ["researcher_finding_record", "researcher_investigation_summary", "researcher_result_propose"]
            if folder is not None:
                (folder / "delivery.json").write_text(json.dumps(delivered, indent=2) + "\n")
    assert analysis.closed
    assert c.conn.execute("SELECT COUNT(*) FROM runtime_jobs").fetchone()[0] == 1
    job = c.store.get_job(101, evidence["receipts"]["job_id"])
    assert job.local_execution_closed and job.stdout == code
    for peer_id in peers.ids.values():
        peers.registry.close(peer_id)
    c.store.finish(lease, native_status="completed", summary="Authored fixture completion, no model.")
    assert c.store.result_state(101, run.run_id)["eligible"]
    async with owner_client(app) as owner:
        response = await owner.get(f"/api/artifacts/{result['report_id']}", params={"project_id": 101})
    assert response.status_code == 200, response.text
    assert "model and reasoning_effort together" in response.json()["content"]
    assert c.conn.execute("SELECT COUNT(*) FROM runtime_result_acceptances").fetchone()[0] == 0
