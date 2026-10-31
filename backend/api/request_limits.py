"""Bound research tool JSON ingress before FastAPI parses the body."""

import asyncio

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class ToolRequestLimits:
    def __init__(
        self, app: ASGIApp, *, max_bytes: int = 1048576, body_timeout: float = 10
    ):
        if max_bytes <= 0 or body_timeout <= 0:
            raise ValueError("Request limits must be positive")
        self.app = app
        self.max_bytes = max_bytes
        self.body_timeout = body_timeout

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        path = scope.get("path", "")
        if (
            scope["type"] != "http"
            or not path.startswith("/api/research-tools/")
            or scope.get("method") not in ("POST", "PUT", "PATCH")
        ):
            return await self.app(scope, receive, send)

        async def reject(status, message):
            await JSONResponse(
                {"error": message, "code": "tool_request_limit"}, status_code=status
            )(scope, receive, send)

        lengths = [
            value
            for name, value in scope.get("headers", [])
            if name.lower() == b"content-length"
        ]
        if lengths:
            if len(lengths) != 1 or not lengths[0].isdigit():
                return await reject(400, "Invalid request content length")
            if int(lengths[0]) > self.max_bytes:
                return await reject(413, "Tool request exceeds the byte limit")
        body = bytearray()
        try:
            async with asyncio.timeout(self.body_timeout):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    body.extend(message.get("body", b""))
                    if len(body) > self.max_bytes:
                        return await reject(413, "Tool request exceeds the byte limit")
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            return await reject(408, "Tool request body exceeded its deadline")
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
