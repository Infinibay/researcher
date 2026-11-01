"""Bounded owned async transport to the credential-bound local research API."""

import asyncio
import json
import math

import httpx

from backend.research.http_client import (
    ResearcherClientError,
    ResearcherEndpoint,
    response_error,
)


class AsyncResearcherHTTPClient(ResearcherEndpoint):
    def __init__(
        self, api_url, token, *, timeout=15, response_limit=1048576, transport=None
    ):
        if (
            type(timeout) not in (int, float)
            or not math.isfinite(timeout)
            or not 0 < timeout <= 180
        ):
            raise ValueError("Finite HTTP deadline required")
        if type(response_limit) is not int or not 1 <= response_limit <= 1048576:
            raise ValueError("Bounded HTTP response size required")
        super().__init__(api_url, token, timeout=timeout, response_limit=response_limit)
        self._client = httpx.AsyncClient(
            timeout=timeout,
            trust_env=False,
            follow_redirects=False,
            transport=transport,
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
        )
        self._pending = set()
        self._entered = False
        self._closing = None
        self.closed = False

    async def __aenter__(self):
        if self._entered or self._closing is not None:
            raise ResearcherClientError("Business HTTP scope cannot reopen")
        self._entered = True
        return self

    async def __aexit__(self, *_):
        await self.aclose()

    async def request(self, method, path, *, body=None, query=None):
        if not self._entered or self._closing is not None:
            raise ResearcherClientError("Business HTTP admission ended")
        if len(self._pending) >= 8:
            raise ResearcherClientError("Business HTTP capacity reached")
        url, data, headers = self.prepare_request(method, path, body=body, query=query)
        headers["Accept-Encoding"] = "identity"
        task = asyncio.create_task(self._send(method, url, data, headers))
        self._pending.add(task)
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            if self._closing is not None:
                raise ResearcherClientError(
                    "Business scope closed; no confirmed receipt, reconcile operation_key"
                ) from None
            raise
        finally:
            self._pending.discard(task)

    async def _send(self, method, url, data, headers):
        try:
            async with asyncio.timeout(self.timeout):
                async with self._client.stream(
                    method, url, content=data, headers=headers
                ) as response:
                    if (
                        response.headers.get("content-encoding", "identity").lower()
                        != "identity"
                    ):
                        raise ResearcherClientError(
                            "Backend returned unsupported content encoding"
                        )
                    limit = (
                        self.response_limit
                        if 200 <= response.status_code < 300
                        else min(65536, self.response_limit)
                    )
                    raw = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=16384):
                        if len(raw) + len(chunk) > limit:
                            raise ResearcherClientError(
                                "Tool response exceeds the byte limit; request a smaller page"
                            )
                        raw.extend(chunk)
                    if not 200 <= response.status_code < 300:
                        raise response_error(
                            response.status_code, raw, token=self.token
                        )
        except (httpx.HTTPError, OSError, TimeoutError):
            raise ResearcherClientError(
                "No confirmed backend receipt; reconcile or retry with the same operation_key"
            ) from None
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ResearcherClientError(
                "Backend returned invalid JSON; no receipt is confirmed"
            ) from None
        if not isinstance(result, dict):
            raise ResearcherClientError("Backend returned an invalid tool response")
        return result

    async def aclose(self):
        if self._closing is None:
            self._closing = asyncio.create_task(self._shutdown())
        await asyncio.shield(self._closing)

    async def _shutdown(self):
        pending = tuple(self._pending)
        for task in pending:
            task.cancel()
        async with asyncio.timeout(3):
            await asyncio.gather(*pending, return_exceptions=True)
            await self._client.aclose()
        self.closed = True
