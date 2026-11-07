"""Opt-in real HTTP/WS owner-session probe. No inference or external services."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


def record_page(message, result):
    """Retain legitimate catch-up frames while rejecting cross-project or unexpected socket data."""
    assert message['type'] == 'events.page', message
    assert message['project_id'] == 101, message
    assert all(event['project_id'] == 101 for event in message['events'])
    result.setdefault('event_pages', []).append(message)


async def main():
    """Verify owner/tool/anonymous boundaries and actual logout closure with durable event replay enabled."""
    import httpx
    from websockets.asyncio.client import connect as websocket
    from websockets.exceptions import ConnectionClosed, InvalidStatus

    from evals.runtime.run_research import backend, environment

    root = REPO / ".researcher/evaluations" / ("local-access-" + uuid4().hex[:8])
    root.mkdir(parents=True)
    result = {"model_turns_submitted": 0}
    print("Local access integration:", root, flush=True)
    try:
        async with backend(root, environment(), evidence=result) as (store, owner, api, _database):
            async with httpx.AsyncClient(
                base_url=api, trust_env=False, timeout=5
            ) as anonymous:
                for path in [
                    "/api/projects",
                    "/openapi.json",
                    "/api/artifacts?project_id=202",
                ]:
                    assert (await anonymous.get(path)).status_code == 401, path
                assert (
                    await anonymous.get(
                        "/api/projects", headers={"Host": "rebound.example"}
                    )
                ).status_code == 400
                assert (
                    await anonymous.get(
                        "/api/projects", headers={"Origin": "https://hostile.example"}
                    )
                ).status_code == 403
                token = store.issue_grant(
                    project_id=101,
                    task_id=1001,
                    agent_id="researcher-a",
                    permissions={"sources.read"},
                )
                try:
                    headers = {"Authorization": "Bearer " + token}
                    assert (
                        await anonymous.get(
                            "/api/research-tools/references", headers=headers
                        )
                    ).status_code == 200
                    assert (
                        await anonymous.get("/api/projects", headers=headers)
                    ).status_code == 401
                    assert (
                        await anonymous.post(
                            "/api/internal/query",
                            headers=headers,
                            json={"sql_query": "SELECT * FROM projects"},
                        )
                    ).status_code == 401
                    assert (
                        await anonymous.get(
                            "/api/research-tools/references?project_id=202",
                            headers=headers,
                        )
                    ).status_code == 422
                finally:
                    store.revoke_grant(store.authorize(token).grant_id)
                result["anonymous_and_tool_owner_separation"] = "passed"
            assert (await owner.get("/api/projects")).status_code == 200
            no_csrf = {
                "Cookie": "; ".join(
                    f"{key}={value}" for key, value in owner.cookies.items()
                )
            }
            async with httpx.AsyncClient(base_url=api, trust_env=False) as copied:
                assert (
                    await copied.post(
                        "/api/projects", headers=no_csrf, json={"name": "No proof"}
                    )
                ).status_code == 403
            ws_api = api.replace("http:", "ws:") + "/ws?project_id=101"
            try:
                async with websocket(
                    ws_api, origin="http://localhost:8000", proxy=None
                ):
                    raise AssertionError("Anonymous WS accepted")
            except InvalidStatus as exc:
                assert exc.response.status_code == 403
            cookie = no_csrf["Cookie"]
            async with websocket(
                ws_api,
                origin="http://localhost:8000",
                additional_headers={"Cookie": cookie},
                proxy=None,
            ) as ws:
                await ws.send("ping")
                async with asyncio.timeout(5):
                    while True:
                        message = json.loads(await ws.recv())
                        if message == {'type': 'pong'}:
                            break
                        record_page(message, result)
                assert (await owner.delete("/api/session")).status_code == 204
                try:
                    async with asyncio.timeout(5):
                        while True:
                            record_page(json.loads(await ws.recv()), result)
                except ConnectionClosed as exc:
                    assert exc.rcvd.code == 1008
            assert (await owner.get("/api/projects")).status_code == 401
            result["owner_http_csrf_websocket_logout"] = "passed"
        result["owned_backend_terminal"] = True
        result["status"] = "passed"
    except BaseException as exc:
        result["status"] = "failed"
        result["error_type"] = type(exc).__name__
        raise
    finally:
        (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        required=True,
        help="Start temporary local HTTP/WS servers, without model turns",
    )
    parser.parse_args()
    asyncio.run(main())
