"""Shared inference session and private control paths for the owned native runtime."""

import os
import re
import stat

from backend.runtime.codex_session import NativeInputRequired

KEN_SERVER = "researcher_ken"
KEN_TOOLS = frozenset(
    {"ken_find", "ken_read", "ken_recall", "ken_related", "ken_remember"}
)
def _private_control(path):
    """Create or validate an owner-only directory for native control state."""
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) & 0o077
    ):
        raise ValueError("Native control directory must be private and user-owned")


class InferenceSession:
    """Route native tool requests through the active host facade and retire on cancel."""

    def __init__(self, native, business, active):
        """Bind the native protocol, frozen business catalog and revocation predicate."""
        self.native = native
        self.business = business
        self.active = active
        self.peers_closed = False

    @property
    def thread_id(self):
        """Return the original native thread identity."""
        return self.native.thread_id

    @property
    def model(self):
        """Return the model confirmed for this native thread."""
        return self.native.thread_configuration["model"]

    @property
    def catalog_hash(self):
        """Return the fingerprint of the frozen host tool catalog."""
        return self.business.catalog_hash

    @property
    def catalog(self):
        """Expose the host tool definitions supplied to the native thread."""
        return self.business.catalog

    @property
    def developer_instructions(self):
        """Expose the exact instructions bound to the native thread."""
        return self.native.developer_instructions

    async def _request(self, request):
        """Reject revoked calls and mediate only supported host tool requests."""
        if not self.active():
            raise NativeInputRequired(request)
        if request["method"] == "item/tool/call":
            return await self.business.call(request.get("params", {}))
        params = request.get("params", {})
        meta = params.get("_meta", {})
        name = re.search(r'tool "([^"]+)"', params.get("message", ""))
        if (
            request["method"] == "mcpServer/elicitation/request"
            and params.get("serverName") == KEN_SERVER
            and meta.get("codex_approval_kind") == "mcp_tool_call"
            and name
            and name.group(1) in KEN_TOOLS
        ):
            return {"action": "accept", "content": {}}
        raise NativeInputRequired(request)

    async def run(self, text, *, on_event=None, on_started=None):
        """Submit one bounded native turn using the active tool mediator."""
        return await self.native.run(
            text, on_event=on_event, on_started=on_started, on_request=self._request
        )

    async def cancel(self):
        """Interrupt generation and close the directly owned RPC peer even on failure."""
        try:
            await self.native.cancel()
        finally:
            # Receipt is not terminal proof. Retire the directly owned native
            # process even if interruption is denied or its receipt is lost.
            await self.native.rpc.aclose()
