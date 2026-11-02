"""Compose owned Ken and native sessions; no product admission or inference loop."""

import asyncio
import json
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from backend.runtime.broker_mcp import McpTransportError, broker_mcp
from backend.runtime.broker_stdio import BrokerEndpoint
from backend.runtime.business_mediation import ProjectTools
from backend.runtime.code_mode_probe import probe_code_mode
from backend.runtime.codex_rpc import RpcProtocolError
from backend.runtime.codex_session import NativeInputRequired
from backend.runtime.ken_mediation import KenNotReady, KenTools
from backend.runtime.native_inference import InferenceSession
from backend.runtime.workspaces import PEER_WORKSPACE


def _prepared(endpoint, operation_id):
    broker = endpoint.owner.broker
    records = broker.journal.load().records
    operation = records.get("broker:op:" + operation_id, {})
    manifest = operation.get("runtime_manifest", {})
    installation = endpoint.ken
    expected = {
        "executable": str(installation.executable),
        "tool_root": str(installation.tool_root),
        "python_root": str(installation.python_root),
        "assets": json.loads(json.dumps(installation.assets)),
    }
    if (
        records.get("broker:active") != broker.grant_id
        or operation.get("grant_id") != broker.grant_id
        or operation.get("kind") != "ken"
        or operation.get("exit_code") != 0
        or operation.get("execution_closed") is not True
        or manifest.get("mode") != "prepare"
        or manifest.get("profile") != "readonly-published-ken-v1"
        or manifest.get("installation") != expected
        or manifest.get("model_cache")
        != (
            str(Path(endpoint.model_cache).resolve(strict=True))
            if endpoint.model_cache is not None
            else None
        )
    ):
        raise RpcProtocolError(
            "Ken requires a successful closed preparation in this original attempt"
        )


class BrokerInferenceSession(InferenceSession):
    """Refresh required Ken before dispatch and preserve the native launch policy."""

    def __init__(self, native, tools, active, refresh, endpoint, *, seal=None):
        """Bind host dispatch to this original native endpoint."""
        self._sealed = False
        self._sealing = None
        self._seal = seal
        super().__init__(native, tools, lambda: active() and not self._sealed)
        self._refresh = refresh
        self._endpoint = endpoint

    @property
    def web_search(self):
        """Expose the original manifested native discovery mode to the coordinator."""
        return self._endpoint.web_search

    async def _request(self, request):
        if self.active() and request["method"] == "item/tool/call":
            await self._refresh()
            return await self.business.call(request.get("params", {}))
        # Ken is a host dynamic tool, never a native-owned MCP integration.
        raise NativeInputRequired(request)

    async def run(self, text, *, on_event=None, on_started=None):
        """Run only before capture seals dispatch, retaining the original Ken and native-state admission checks."""
        if self._sealed:
            raise RpcProtocolError("Native session is sealed for candidate capture")
        await self._refresh()
        endpoint = self._endpoint
        if endpoint.native_state is not None:
            if not self.active():
                raise RpcProtocolError("Native attempt authority ended")
            await asyncio.to_thread(
                endpoint.native_state.reserve_turn,
                endpoint.owner.broker.journal,
                endpoint._operation,
                text,
            )
        return await super().run(text, on_event=on_event, on_started=on_started)

    async def seal(self):
        """Disable model dispatch and close its original writers once, leaving the host's broker available for capture."""
        if self._seal is None:
            raise RpcProtocolError("This session has no development capture boundary")
        if self._sealing is None:
            self._sealed = True
            self._sealing = asyncio.create_task(self._seal())
        await asyncio.shield(self._sealing)


@asynccontextmanager
async def broker_inference(
    native,
    ken_endpoint,
    *,
    prepared_operation,
    business,
    analysis,
    active=lambda: True,
    prepare_ken=None,
):
    """Require original successful preparation and Ken readiness before admission.

    Native and Ken endpoints must belong to the same async broker. Business and
    analysis are already-admitted host facades: their actor origin/lifecycle remains
    the caller's responsibility. This does not install a product runtime factory,
    provision domains/accounts, start a turn, or approve any product task.
    """
    endpoint = native.rpc._endpoint
    if (
        not isinstance(endpoint, BrokerEndpoint)
        or not isinstance(ken_endpoint, BrokerEndpoint)
        or endpoint.owner is not ken_endpoint.owner
        or endpoint.host_tools is not True
        or endpoint.code_host is None
        or ken_endpoint.ken is None
        or ken_endpoint.ken_mode != "mcp"
        or native.workspace != PEER_WORKSPACE
        or native.sandbox not in ("read-only", "workspace-write")
        or native.permission_profile is not None
        or (native.resume_thread_id is not None and endpoint.native_state is None)
        or native.thread_id is not None
        or native.dynamic_tools is not None
        or not isinstance(prepared_operation, str)
    ):
        raise RpcProtocolError(
            "Owned native/Ken profiles and an original readonly session required"
        )

    admission = await asyncio.to_thread(endpoint.registry.admission, endpoint.peer_id)
    expected_sandbox = (
        "workspace-write"
        if admission["execution_kind"] == "development"
        else "read-only"
    )
    if native.sandbox != expected_sandbox:
        raise RpcProtocolError(
            "Native filesystem policy differs from its current admitted execution kind"
        )

    def admitted():
        return (
            active()
            and endpoint.owner._closing is None
            and not endpoint.owner.broker._withdrawn.is_set()
        )

    if not admitted():
        raise RpcProtocolError("Ken admission authority ended")
    await asyncio.to_thread(_prepared, ken_endpoint, prepared_operation)
    if not admitted():
        raise RpcProtocolError("Ken admission authority ended")
    async with AsyncExitStack() as ken_scope:
        try:
            if prepare_ken is None:
                peer = await ken_scope.enter_async_context(broker_mcp(ken_endpoint))
                ken = await KenTools.connect(peer, active=admitted)
            else:
                from backend.runtime.ken_development import DevelopmentKen

                ken = await ken_scope.enter_async_context(
                    DevelopmentKen(
                        ken_endpoint,
                        prepare=prepare_ken,
                        validate=_prepared,
                        quiet=analysis.quiescent,
                        active=admitted,
                    )
                )
        except (KenNotReady, McpTransportError):
            raise RpcProtocolError(
                "Ken catalog is not ready for native admission"
            ) from None
        tools = ProjectTools(business, analysis, ken)
        ken_hash = ken.catalog_hash

        async def refresh():
            """Validate the original Ken catalog without reindexing while command control may still be needed."""
            try:
                if prepare_ken is None:
                    current = await KenTools.connect(peer, active=admitted)
                else:
                    await ken.require_ready()
                    current = ken
            except (KenNotReady, McpTransportError):
                raise RpcProtocolError("Ken catalog is no longer ready") from None
            if current.catalog_hash != ken_hash:
                raise RpcProtocolError(
                    "Ken catalog changed; reconcile before a native turn"
                )

        previous = native.before_thread

        async def preflight(rpc):
            """Attest host policy, required Ken and search capability before a thread."""
            if previous is not None:
                await previous(rpc)
            config = (await rpc.request("config/read", {"includeLayers": False}))[
                "config"
            ]
            features = config.get("features", {})
            if (
                config.get("web_search") != endpoint.web_search
                or not all(
                    features.get(name) is True
                    for name in (
                        "code_mode_host",
                        "code_mode_interrupt",
                        "skip_host_skill_discovery",
                    )
                )
                or not all(
                    features.get(name) is False
                    for name in (
                        "code_mode",
                        "shell_tool",
                        "unified_exec",
                        "plugins",
                        "apps",
                        "multi_agent",
                        "hooks",
                        "memories",
                        "daemon_auto_start",
                        "skill_search",
                        "shell_snapshot",
                    )
                )
                or config.get("mcp_servers") not in (None, {})
                or config.get("forced_login_method") != "chatgpt"
                or config.get("model_provider") != "openai"
                or config.get("chatgpt_base_url")
                not in (
                    "https://chatgpt.com/backend-api",
                    "https://chatgpt.com/backend-api/",
                )
            ):
                raise RpcProtocolError("Owned native host-tool configuration mismatch")
            if endpoint.web_search != "disabled":
                from backend.runtime.native_search import NativeSearchUnavailable

                capabilities = await rpc.request("modelProvider/capabilities/read", {})
                if capabilities.get("webSearch") is not True:
                    raise NativeSearchUnavailable(
                        "Configured native web search is unavailable; no fallback was dispatched"
                    )
            await refresh()
            await probe_code_mode(rpc)
            if endpoint.native_state is not None:
                await asyncio.to_thread(
                    endpoint.native_state.prepare_thread,
                    endpoint.owner.broker.journal,
                    endpoint._operation,
                    model=native.model,
                    catalog_hash=tools.catalog_hash,
                    developer_instructions=native.developer_instructions,
                    resume_thread_id=native.resume_thread_id,
                    web_search=endpoint.web_search,
                )
                if native.resume_thread_id is not None:
                    thread = (
                        await rpc.request(
                            "thread/read",
                            {
                                "threadId": native.resume_thread_id,
                                "includeTurns": False,
                            },
                        )
                    )["thread"]
                    if (
                        thread.get("id") != native.resume_thread_id
                        or thread.get("cwd") != str(PEER_WORKSPACE)
                        or thread.get("model") != native.model
                        or thread.get("modelProvider") != "openai"
                    ):
                        raise RpcProtocolError(
                            "Native stored thread metadata differs from original intent"
                        )

        native.before_thread = preflight
        native.dynamic_tools = (
            None if native.resume_thread_id is not None else tools.catalog
        )
        try:
            async with native:
                configured = native.thread_configuration
                if (
                    configured.get("cwd") != str(PEER_WORKSPACE)
                    or configured.get("model") != native.model
                ):
                    raise RpcProtocolError(
                        "Native thread did not retain its admitted workspace/model"
                    )
                if endpoint.native_state is not None:
                    await asyncio.to_thread(
                        endpoint.native_state.bind_thread,
                        endpoint.owner.broker.journal,
                        endpoint._operation,
                        native.thread_id,
                    )

                async def seal_development():
                    """Retire all native, command and Ken peers before reading a candidate; keep original domain ownership."""
                    await native.rpc.aclose()
                    await analysis.aclose()
                    await ken_scope.aclose()

                yield BrokerInferenceSession(
                    native,
                    tools,
                    admitted,
                    refresh,
                    endpoint,
                    seal=seal_development if prepare_ken is not None else None,
                )
        finally:
            # A closed connection is never reusable. Retain its admitted catalog
            # for receipts, but do not leave a callback to a retired MCP scope.
            native.before_thread = previous
