"""Mediate the existing business MCP without giving its grant to a model peer."""

import hashlib
import json
from contextlib import asynccontextmanager
from pathlib import Path

RESEARCH_NAMES = frozenset(
    {
        "researcher_reference_list",
        "researcher_capture_reference",
        "researcher_capture_web",
        "researcher_capture_paper",
        "researcher_capture_wiki",
        "researcher_capture_wiki_collection",
        "researcher_wiki_list",
        "researcher_wiki_read",
        "researcher_wiki_write",
        "researcher_source_list",
        "researcher_source_read",
        "researcher_source_structure",
        "researcher_source_search",
        "researcher_source_query",
        "researcher_finding_record",
        "researcher_finding_read",
        "researcher_finding_list",
        "researcher_finding_summary",
        "researcher_finding_query",
        "researcher_review_read",
        "researcher_report_write",
        "researcher_report_read",
        "researcher_ask_user",
    }
)
REVIEW_NAMES = frozenset(
    {
        "researcher_reference_list",
        "researcher_source_list",
        "researcher_source_read",
        "researcher_source_structure",
        "researcher_source_search",
        "researcher_source_query",
        "researcher_finding_read",
        "researcher_finding_list",
        "researcher_finding_summary",
        "researcher_finding_query",
        "researcher_report_read",
        "researcher_wiki_list",
        "researcher_wiki_read",
        "researcher_ask_user",
        "researcher_review_subject",
        "researcher_review_decide",
        "researcher_review_read",
    }
)
BUSINESS_NAMES = RESEARCH_NAMES
ALL_BUSINESS_NAMES = RESEARCH_NAMES | REVIEW_NAMES


def _failure(message):
    return {"success": False, "contentItems": [{"type": "inputText", "text": message}]}


def catalog_digest(catalog):
    return hashlib.sha256(
        json.dumps(
            catalog, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


class ProjectTools:
    """One pre-admission catalog with explicit host/business dispatch ownership."""

    def __init__(self, business, analysis, *host_tools):
        self.business, self.analysis = business, analysis
        providers = (business, analysis, *host_tools)
        self.catalog = [row for provider in providers for row in provider.catalog]
        names = [tool["name"] for tool in self.catalog]
        if len(names) != len(set(names)):
            raise ValueError(
                "Project tool names must be unique before thread admission"
            )
        self._dispatch = {
            row["name"]: provider for provider in providers for row in provider.catalog
        }

    @property
    def catalog_hash(self):
        return catalog_digest(self.catalog)

    async def call(self, params):
        if (
            isinstance(params, dict)
            and isinstance(params.get("tool"), str)
            and params["tool"] in self._dispatch
        ):
            return await self._dispatch[params["tool"]].call(params)
        return await self.business.call(params)


class McpTools:
    """Shared MCP result/authority boundary; subclasses admit their own catalog."""

    def __init__(self, peer, catalog, active):
        self._peer = peer
        self.catalog = catalog
        self._names = frozenset(tool["name"] for tool in catalog)
        self._active = active

    @property
    def catalog_hash(self):
        return catalog_digest(self.catalog)

    async def call(self, params):
        if not self._active():
            return _failure(
                "Attempt authority ended. Do not dispatch or retry effects; reconcile existing receipts."
            )
        if (
            not isinstance(params, dict)
            or params.get("namespace") is not None
            or not isinstance(params.get("tool"), str)
            or params.get("tool") not in self._names
            or not isinstance(params.get("arguments"), dict)
        ):
            return _failure("Unknown project tool or invalid argument envelope")
        result = await self._peer.call_tool(params["tool"], params["arguments"])
        content = []
        for item in result.content:
            if item.type != "text":
                return _failure(
                    "Tool returned an unsupported content type; reconcile its durable receipt before any retry."
                )
            content.append({"type": "inputText", "text": item.text})
        response = {"success": not result.isError, "contentItems": content}
        if len(json.dumps(response, separators=(",", ":")).encode()) > 1000000:
            return _failure(
                "Tool result exceeds the native wire budget. Recover the durable result with a smaller read window; do not repeat the mutation with a new operation key."
            )
        if not self._active():
            return _failure(
                "Attempt ended while the tool ran. A durable effect may already exist; reconcile its operation receipt."
            )
        return response


class BusinessTools(McpTools):
    """Project only the admitted business capability catalog into a native tool session."""

    @classmethod
    async def connect(cls, peer, *, active=lambda: True):
        """Validate unique known tool names before exposing the host-selected capability subset."""
        tools = (await peer.list_tools()).tools
        names = [tool.name for tool in tools]
        if (
            not names
            or len(names) != len(set(names))
            or not set(names) <= ALL_BUSINESS_NAMES
        ):
            raise ValueError(
                "Unexpected business MCP capabilities; native turn was not admitted"
            )
        catalog = [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description or tool.name,
                "inputSchema": tool.inputSchema,
            }
            for tool in tools
        ]
        return cls(peer, catalog, active)


class _BusinessPeer:
    def __init__(self, client):
        self.client = client
        self.closed = False

    async def list_tools(self):
        return await self.client.list_tools()

    async def call_tool(self, name, arguments):
        return await self.client.call_tool(name, arguments)


@asynccontextmanager
async def business_peer(
    *,
    api_url: str,
    token: str,
    script: Path,
    uv: Path,
    cache: Path,
    home: Path,
    peer_owner=None,
):
    """Own only the business MCP child; credentials never enter native config."""
    import asyncio
    import os
    import sys

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    await asyncio.to_thread(home.mkdir, mode=0o700, parents=True, exist_ok=True)
    command = [
        str(uv),
        "run",
        "--offline",
        "--locked",
        "--python",
        sys.executable,
        "--script",
        str(script),
    ]
    if peer_owner is not None:
        command = peer_owner.command("business", command)
    server = StdioServerParameters(
        command=command[0],
        args=command[1:],
        cwd=home,
        env={
            "PATH": os.defpath,
            "HOME": str(home),
            "CODEX_HOME": str(home / ".codex"),
            "SHELL": "/bin/sh",
            "LANG": "C.UTF-8",
            "UV_CACHE_DIR": str(cache),
            "RESEARCHER_API_URL": api_url,
            "RESEARCHER_TOOL_TOKEN": token,
            "FASTMCP_LOG_LEVEL": "WARNING",
        },
    )
    body_error = None
    with open(os.devnull, "w") as errors:  # noqa: ASYNC230 — kernel null device, no disk IO
        async with (
            stdio_client(server, errlog=errors) as streams,
            ClientSession(*streams) as peer,
        ):
            async with asyncio.timeout(20):
                await peer.initialize()
            owned = _BusinessPeer(peer)
            try:
                yield owned
            except BaseException as exc:  # noqa: BLE001 — preserve and re-raise after owned SDK scopes drain
                # Drain the SDK scopes normally and preserve the caller's
                # exception separately. Teardown failures leave closed=False.
                body_error = exc
        owned.closed = True
    if body_error is not None:
        raise body_error
