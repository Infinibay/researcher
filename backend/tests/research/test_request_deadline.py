import asyncio

from backend.api.request_limits import ToolRequestLimits


async def test_a_body_that_never_arrives_has_a_bounded_http_timeout():
    async def ordinary_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"Unexpected success"})

    async def no_body():
        await asyncio.Event().wait()

    sent = []

    async def capture(message):
        sent.append(message)

    app = ToolRequestLimits(ordinary_app, body_timeout=0.02)
    await asyncio.wait_for(
        app(
            {
                "type": "http",
                "path": "/api/research-tools/reports",
                "method": "POST",
                "headers": [],
            },
            no_body,
            capture,
        ),
        1,
    )
    assert sent[0]["status"] == 408
