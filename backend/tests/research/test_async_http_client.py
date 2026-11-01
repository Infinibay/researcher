"""Owned async HTTP must bound work and never replay an uncertain mutation."""

import asyncio
import json

import httpx
import pytest

from backend.research.http_client import ResearcherClientError

TOKEN = "host-only-secret-token"


async def test_async_http_fixed_origin_credentials_and_no_environment_proxy(
    monkeypatch,
):
    from backend.research.async_http_client import AsyncResearcherHTTPClient

    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    seen = []

    async def handle(request):
        seen.append(request)
        return httpx.Response(200, json={"receipt": "saved"})

    async with AsyncResearcherHTTPClient(
        "http://127.0.0.1:8000", TOKEN, transport=httpx.MockTransport(handle)
    ) as client:
        assert await client.request(
            "POST", "/reports", body={"operation_key": "same"}
        ) == {"receipt": "saved"}
        assert seen[0].headers["Authorization"] == "Bearer " + TOKEN
        assert str(seen[0].url) == "http://127.0.0.1:8000/api/research-tools/reports"
        assert json.loads(seen[0].content)["operation_key"] == "same"
    assert client.closed and len(seen) == 1


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(302, headers={"Location": "http://127.0.0.2/private"}),
        httpx.Response(401, json={"detail": TOKEN}),
        httpx.Response(200, content=b"invalid"),
        httpx.Response(200, json=[]),
        httpx.Response(200, content=b"x" * 2048),
        httpx.Response(200, headers={"Content-Encoding": "gzip"}),
    ],
)
async def test_async_failures_never_replay_or_expose_credentials(response):
    from backend.research.async_http_client import AsyncResearcherHTTPClient

    calls = []

    async def handle(request):
        calls.append(request)
        return response

    async with AsyncResearcherHTTPClient(
        "http://127.0.0.1",
        TOKEN,
        response_limit=1024,
        transport=httpx.MockTransport(handle),
    ) as client:
        with pytest.raises(ResearcherClientError) as error:
            await client.request("POST", "/reports", body={"operation_key": "same"})
        assert TOKEN not in str(error.value)
    assert len(calls) == 1


async def test_async_wall_deadline_drains_the_owned_request():
    from backend.research.async_http_client import AsyncResearcherHTTPClient

    done = asyncio.Event()

    async def handle(request):
        try:
            await asyncio.Event().wait()
        finally:
            done.set()

    async with AsyncResearcherHTTPClient(
        "http://127.0.0.1", TOKEN, timeout=0.02, transport=httpx.MockTransport(handle)
    ) as client:
        with pytest.raises(ResearcherClientError, match="receipt"):
            await client.request("GET", "/references")
        assert done.is_set()


async def test_async_close_withdraws_and_drains_capacity_without_waiting_for_backend():
    from backend.research.async_http_client import AsyncResearcherHTTPClient

    reached = asyncio.Event()
    count = [0]

    async def handle(request):
        count[0] += 1
        if count[0] == 8:
            reached.set()
        await asyncio.Event().wait()

    client = await AsyncResearcherHTTPClient(
        "http://127.0.0.1", TOKEN, transport=httpx.MockTransport(handle)
    ).__aenter__()
    pending = [
        asyncio.create_task(client.request("GET", "/references")) for _ in range(8)
    ]
    try:
        await asyncio.wait_for(reached.wait(), 1)
        with pytest.raises(ResearcherClientError, match="capacity"):
            await client.request("GET", "/references")
        await asyncio.wait_for(client.aclose(), 1)
        results = await asyncio.gather(*pending, return_exceptions=True)
        assert all(isinstance(result, ResearcherClientError) for result in results)
        assert client.closed
        with pytest.raises(ResearcherClientError):
            await client.request("GET", "/references")
    finally:
        await client.aclose()
        await asyncio.gather(*pending, return_exceptions=True)


@pytest.mark.parametrize("timeout", [True, 0, float("nan"), float("inf")])
async def test_async_http_requires_finite_host_bounds(timeout):
    from backend.research.async_http_client import AsyncResearcherHTTPClient

    with pytest.raises(ValueError):
        AsyncResearcherHTTPClient("http://127.0.0.1", TOKEN, timeout=timeout)


async def test_async_validation_error_keeps_actionable_detail_without_input_or_token():
    from backend.research.async_http_client import AsyncResearcherHTTPClient

    async def handle(request):
        return httpx.Response(
            422,
            json={
                "detail": [
                    {
                        "loc": ["body", "quote"],
                        "msg": "Quote missing from captured source",
                        "input": TOKEN,
                    }
                ]
            },
        )

    async with AsyncResearcherHTTPClient(
        "http://127.0.0.1", TOKEN, transport=httpx.MockTransport(handle)
    ) as client:
        with pytest.raises(ResearcherClientError) as caught:
            await client.request("POST", "/findings", body={"operation_key": "same"})
        assert "body.quote" in str(caught.value) and "Quote missing" in str(
            caught.value
        )
        assert TOKEN not in str(caught.value)
