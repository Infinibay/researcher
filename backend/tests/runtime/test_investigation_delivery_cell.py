"""Exercise one real offline code-mode cell across scoped research HTTP/storage.

The JavaScript and evidence are authored fixtures, not a generated explanation or
human-comprehension result. Peer receipts use the existing synthetic storage
fixture; this test does not certify a native containment or subscription boundary.
"""

import asyncio
import json
import struct
import time

import httpx

from backend.tests.runtime.test_investigation import (
    investigation_state,
    summary_packet,
)
from backend.tests.runtime.test_workspace_delivery import owner_client


async def write_frame(process, message):
    """Send one typed frame using the pinned code-host length-prefixed codec."""
    payload = json.dumps(message, separators=(",", ":")).encode()
    process.stdin.write(struct.pack("<I", len(payload)) + payload)
    await process.stdin.drain()


async def read_frame(process):
    """Read one bounded complete frame; the caller owns the overall deadline."""
    size = struct.unpack("<I", await process.stdout.readexactly(4))[0]
    assert 0 < size <= 1048576
    return json.loads(await process.stdout.readexactly(size))


async def operation_response(process, request_id):
    """Observe the matching operation reply after intervening execution events."""
    observed = []
    for _ in range(16):
        message = await read_frame(process)
        observed.append((message.get("type"), message.get("id")))
        if message.get("type") == "operation/response" and message.get("id") == request_id:
            assert message["result"]["status"] == "ok", message
            return message["result"]["value"]
    raise AssertionError(("Missing operation response", request_id, observed))


async def execute_cell(binary, facade, source):
    """Run one fixed offline cell and delegate actual tools without a model round."""
    process = await asyncio.create_subprocess_exec(
        binary.path,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    calls = []
    try:
        async with asyncio.timeout(15):
            await write_frame(process, {
                "type": "connection/hello",
                "supportedVersions": [1],
                "requiredCapabilities": ["session-cell-execution-resource-limits"],
                "optionalCapabilities": [],
            })
            assert (await read_frame(process))["type"] == "connection/ready"
            await write_frame(process, {
                "type": "operation/request", "id": 1,
                "request": {
                    "method": "session/open", "sessionId": "delivery-fixture",
                    "cellExecutionLimits": {
                        "maxYieldTimeMs": 5000, "maxHeapSizeBytes": 64 * 1024**2,
                    },
                },
            })
            opened = await operation_response(process, 1)
            assert opened["type"] == "session/ready", opened
            enabled = [{
                "name": tool["name"],
                "tool_name": {"name": tool["name"], "namespace": None},
                "description": tool["description"], "kind": "function",
                "input_schema": tool["inputSchema"], "output_schema": None,
            } for tool in facade.catalog]
            await write_frame(process, {
                "type": "operation/request", "id": 2,
                "request": {
                    "method": "session/execute", "sessionId": "delivery-fixture",
                    "request": {
                        "tool_call_id": "delivery-fixture", "enabled_tools": enabled,
                        "source": source, "yield_time_ms": 5000,
                        "max_output_tokens": 256,
                    },
                },
            })
            started = False
            result = None
            while not started or result is None:
                message = await read_frame(process)
                if message["type"] == "delegate/request":
                    invocation = message["request"]["invocation"]
                    name = invocation["tool_name"]["name"]
                    calls.append(name)
                    reply = await facade.call({
                        "tool": name, "arguments": invocation["input"],
                    })
                    await write_frame(process, {
                        "type": "delegate/response", "id": message["id"],
                        "result": {
                            "status": "ok",
                            "value": {"type": "tool/result", "result": reply},
                        },
                    })
                    continue
                assert message.get("id") == 2, message
                assert message["result"]["status"] == "ok", message
                value = message["result"]["value"]
                if message["type"] == "operation/response":
                    started = value["type"] == "execution/started"
                elif message["type"] == "execute/initialResponse":
                    result = value
            assert "Result" in result, result
            assert not result["Result"].get("error_text"), result
            assert "DELIVERY_READY" in json.dumps(result), result
            await write_frame(process, {
                "type": "operation/request", "id": 3,
                "request": {
                    "method": "session/shutdown", "sessionId": "delivery-fixture",
                },
            })
            closed = await operation_response(process, 3)
            assert closed["type"] == "session/closed", closed
            process.stdin.close()
            assert await process.wait() == 0
            return calls
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


async def test_one_cell_delivers_typed_result_visible_without_another_model_round(
    coordination, code_host_asset,
):
    """Returned IDs compose through real schemas/HTTP into an owner-readable draft.

    Losing the later native completion leaves acceptance blocked, while the
    selected report remains inspectable without a synthesis model or replay.
    """
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.runtime.business_mediation import BusinessTools
    from backend.runtime.host_business import host_business

    coordination.now[0] = time.time()
    c, run, lease, peers, scope, previous_finding = investigation_state(coordination)
    source_id = c.conn.execute(
        "SELECT source_id FROM finding_sources WHERE finding_id=?", (previous_finding,),
    ).fetchone()[0]
    # The fixture's token is retained by the store helper only as its digest;
    # mint another grant and bind it to the same original author for the API.
    from backend.research.models import RESEARCH_PERMISSIONS

    token = c.research.issue_grant(
        project_id=101, task_id=1001, agent_id=lease.actor_id,
        permissions=set(RESEARCH_PERMISSIONS),
    )
    scope = c.research.authorize(token)
    c.store.bind_grant(lease, scope.grant_id)
    app = create_app(access=LocalAccess(
        pairing_key="workspace-owner-key-at-least-32-characters",
    ))
    app.state.live_grants.activate(scope.grant_id)
    packet = summary_packet(previous_finding)
    source = """
function unwrap(reply) {
  if (!reply.success) throw new Error('Delivery stopped: reconcile original receipts');
  return JSON.parse(reply.contentItems[0].text);
}
const finding = unwrap(await tools.researcher_finding_record(FINDING));
const summary = SUMMARY;
summary.areas[0].finding_ids = [finding.finding_id];
const report = unwrap(await tools.researcher_investigation_summary({
  operation_key: 'one-cell-summary', summary
}));
const proposal = unwrap(await tools.researcher_result_propose({
  operation_key: 'one-cell-proposal', report_ids: [report.artifact_id],
  summary: 'Documentary count and an unresolved measurement method.',
  limitations: ['Documentary inspection only.']
}));
text({status: 'DELIVERY_READY', report_id: report.artifact_id, proposal});
""".replace("FINDING", json.dumps({
        "operation_key": "one-cell-finding", "topic": "Recorded count",
        "content": "The supplied source records 137 units.",
        "evidence": [{"source_id": source_id, "quote": "137 units"}],
    })).replace("SUMMARY", json.dumps(packet))
    async with host_business(
        api_url="http://127.0.0.1", token=token,
        withdraw=lambda: app.state.live_grants.withdraw(scope.grant_id),
        names={"researcher_finding_record", "researcher_investigation_summary",
               "researcher_result_propose"},
        transport=httpx.ASGITransport(app=app),
    ) as peer:
        facade = await BusinessTools.connect(peer)
        assert await execute_cell(code_host_asset, facade, source) == [
            "researcher_finding_record", "researcher_investigation_summary",
            "researcher_result_propose",
        ]
    proposal = c.conn.execute(
        "SELECT snapshot_json FROM runtime_result_proposals WHERE run_id=?", (run.run_id,),
    ).fetchone()
    selected = json.loads(proposal[0])["reports"][0]
    finding_ids = selected["investigation"]["areas"][0]["finding_ids"]
    assert len(finding_ids) == 1 and finding_ids[0] != previous_finding
    assert c.conn.execute("SELECT COUNT(*) FROM research_reports").fetchone()[0] == 1
    assert c.conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == 2
    for peer_id in peers.ids.values():
        peers.registry.close(peer_id)
    c.store.finish(lease, native_status="failed", summary="No later model completion.")
    assert not c.store.result_state(101, run.run_id)["eligible"]
    async with owner_client(app) as owner:
        response = await owner.get(
            f"/api/artifacts/{selected['artifact_id']}", params={"project_id": 101},
        )
    assert response.status_code == 200, response.text
    assert "137 units" in response.json()["content"]
    assert "No measurement protocol was supplied." in response.json()["content"]
    assert c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0] != "done"
    assert c.conn.execute("SELECT COUNT(*) FROM runtime_result_acceptances").fetchone()[0] == 0
