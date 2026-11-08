"""Mediate the existing business MCP without giving its grant to a model peer."""

import hashlib
import json
from contextlib import asynccontextmanager
from pathlib import Path

TASK_READ_NAMES = frozenset({
    "researcher_project_structure", "researcher_project_structure_read",
    "researcher_task_list", "researcher_task_read", "researcher_task_dependencies",
    "researcher_task_history", "researcher_continuity_read",
})
TASK_WRITE_NAMES = frozenset({"researcher_task_comment", "researcher_continuity_save"})
MESSAGE_NAMES = frozenset({
    "researcher_notices", "researcher_notice_read",
    "researcher_peer_recipients", "researcher_peer_messages", "researcher_peer_message_read",
    "researcher_peer_message_send", "researcher_peer_message_acknowledge",
})

RESEARCH_NAMES = frozenset(
    {
        "researcher_reference_list",
        "researcher_capture_reference",
        "researcher_capture_command",
        "researcher_capture_web",
        "researcher_context7_search",
        "researcher_context7_docs",
        "researcher_capture_spider",
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
        "researcher_result_propose",
        "researcher_report_read",
        "researcher_knowledge_search",
        "researcher_ask_user",
    }
) | TASK_READ_NAMES | TASK_WRITE_NAMES | MESSAGE_NAMES
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
        "researcher_knowledge_search",
        "researcher_wiki_list",
        "researcher_wiki_read",
        "researcher_ask_user",
        "researcher_review_subject",
        "researcher_review_decide",
        "researcher_review_read",
    }
) | TASK_READ_NAMES | MESSAGE_NAMES
INVESTIGATION_NAMES = (RESEARCH_NAMES - {"researcher_report_write"}) | {"researcher_investigation_summary"}
BUSINESS_NAMES = RESEARCH_NAMES
DEVELOPMENT_NAMES = RESEARCH_NAMES - {"researcher_result_propose", "researcher_capture_command"}
CODE_REVIEW_NAMES = REVIEW_NAMES - {
    "researcher_review_subject",
    "researcher_review_decide",
}
ALL_BUSINESS_NAMES = RESEARCH_NAMES | REVIEW_NAMES | INVESTIGATION_NAMES


def _failure(message):
    """Build the native tool-failure envelope as input text without dispatching, retrying or resolving
    a possible durable effect.
    """
    return {"success": False, "contentItems": [{"type": "inputText", "text": message}]}


def catalog_digest(catalog):
    """Fingerprint the exact ordered catalog with deterministic JSON; matching metadata does not itself
    grant permission to call its tools.
    """
    return hashlib.sha256(
        json.dumps(
            catalog, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


class ProjectTools:
    """One pre-admission catalog with explicit host/business dispatch ownership."""

    def __init__(self, business, analysis, *host_tools):
        """Combine host-selected provider catalogs and require globally unique names before recording
        the dispatch map; construction does not call a tool.
        """
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
        """Fingerprint the current combined catalog used for native thread admission."""
        return catalog_digest(self.catalog)

    async def call(self, params):
        """Route known names to their original provider and delegate invalid or unknown envelopes to
        the business boundary for rejection.
        """
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
        """Bind one existing peer, admitted catalog and live authority predicate without expanding
        capabilities or invoking the peer.
        """
        self._peer = peer
        self.catalog = catalog
        self._names = frozenset(tool["name"] for tool in catalog)
        self._active = active

    @property
    def catalog_hash(self):
        """Fingerprint this admitted MCP projection for the native session intent."""
        return catalog_digest(self.catalog)

    async def call(self, params):
        """Validate current authority and the admitted envelope, dispatch once, and project bounded
        text results; late withdrawal or unsupported output requires receipt reconciliation.
        """
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
    """Adapt one existing MCP SDK client while the enclosing business-peer scope records whether SDK
    teardown completed.
    """
    def __init__(self, client):
        """Retain the existing SDK client and start with teardown unconfirmed; the enclosing scope
        alone marks it closed.
        """
        self.client = client
        self.closed = False

    async def list_tools(self):
        """Read capabilities through the already initialized client without opening another MCP
        connection.
        """
        return await self.client.list_tools()

    async def call_tool(self, name, arguments):
        """Forward one call to the existing SDK client without adding retries or changing its operation
        arguments.
        """
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
