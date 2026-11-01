"""Compose owned Ken and native sessions; no product admission or inference loop."""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from backend.runtime.broker_mcp import McpTransportError, broker_mcp
from backend.runtime.broker_stdio import BrokerEndpoint
from backend.runtime.business_mediation import ProjectTools
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
    def __init__(self, native, tools, active, refresh):
        super().__init__(native, tools, active)
        self._refresh = refresh

    async def _request(self, request):
        if self.active() and request["method"] == "item/tool/call":
            await self._refresh()
            return await self.business.call(request.get("params", {}))
        # Ken is a host dynamic tool, never a native-owned MCP integration.
        raise NativeInputRequired(request)

    async def run(self, text, *, on_event=None, on_started=None):
        await self._refresh()
        return await super().run(text, on_event=on_event, on_started=on_started)


@asynccontextmanager
async def broker_inference(
    native, ken_endpoint, *, prepared_operation, business, analysis, active=lambda: True
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
        or ken_endpoint.ken is None
        or ken_endpoint.ken_mode != "mcp"
        or native.workspace != PEER_WORKSPACE
        or native.sandbox != "read-only"
        or native.permission_profile is not None
        or native.resume_thread_id is not None
        or native.thread_id is not None
        or native.dynamic_tools is not None
        or not isinstance(prepared_operation, str)
    ):
        raise RpcProtocolError(
            "Owned native/Ken profiles and a fresh readonly session required"
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
    async with broker_mcp(ken_endpoint) as peer:
        try:
            ken = await KenTools.connect(peer, active=admitted)
        except (KenNotReady, McpTransportError):
            raise RpcProtocolError(
                "Ken catalog is not ready for native admission"
            ) from None
        tools = ProjectTools(business, analysis, ken)
        ken_hash = ken.catalog_hash

        async def refresh():
            try:
                current = await KenTools.connect(peer, active=admitted)
            except (KenNotReady, McpTransportError):
                raise RpcProtocolError("Ken catalog is no longer ready") from None
            if current.catalog_hash != ken_hash:
                raise RpcProtocolError(
                    "Ken catalog changed; reconcile before a native turn"
                )

        previous = native.before_thread

        async def preflight(rpc):
            if previous is not None:
                await previous(rpc)
            config = (await rpc.request("config/read", {"includeLayers": False}))[
                "config"
            ]
            features = config.get("features", {})
            if (
                not all(
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
            await refresh()

        native.before_thread = preflight
        native.dynamic_tools = tools.catalog
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
                yield BrokerInferenceSession(native, tools, admitted, refresh)
        finally:
            # A closed connection is never reusable. Retain its admitted catalog
            # for receipts, but do not leave a callback to a retired MCP scope.
            native.before_thread = previous
