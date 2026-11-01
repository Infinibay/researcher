"""Host-owned managed Codex RPC, shared by external-token inference connections.

The deployment supplies an unopened, trusted managed-mode endpoint. Only this
host peer may see managed OAuth storage; inference peers receive access snapshots.
This module does not construct an enrolled endpoint or implement OAuth HTTP.
"""

import asyncio
import hashlib
import math

from backend.runtime.codex_session import SubscriptionRequired
from backend.runtime.subscription_auth import ExternalChatGPTAuth


class _ConsumerWithdrawn(SubscriptionRequired):
    """One consumer stopped; the shared managed operation is not uncertain."""


class HostSubscription:
    """Own one managed account/connection and serialize its credential rotations.

    A cancelled inference consumer cannot cancel an already-owned rotation or
    release its lock. Uncertain managed operations retire this provider rather
    than retrying a possibly applied refresh. Reopen requires explicit host action.
    """

    def __init__(self, source, rpc, *, timeout=6, max_pending=8):
        if (
            isinstance(timeout, bool)
            or not math.isfinite(timeout)
            or not 0 < timeout <= 6
            or type(max_pending) is not int
            or not 1 <= max_pending <= 16
        ):
            raise ValueError("Bounded managed subscription limits required")
        self.source, self.rpc = source, rpc
        self.timeout, self.max_pending = timeout, max_pending
        self._used = False
        self._live = False
        self._account = None
        self._lock = asyncio.Lock()
        self._pending = set()
        self._closing = None

    async def __aenter__(self):
        if self._used:
            raise RuntimeError("Managed subscription owner cannot be reused")
        self._used = True
        try:
            async with asyncio.timeout(self.timeout):
                credential = await asyncio.to_thread(self.source.read)
                self._account = credential.account_id
                await self.rpc.__aenter__()
                await self.rpc.request(
                    "initialize",
                    {
                        "clientInfo": {
                            "name": "researcher-host-auth",
                            "version": "0.1.0",
                        }
                    },
                )
                await self.rpc.notify("initialized")
                self._check_response(
                    await self.rpc.request("account/read", {"refreshToken": False})
                )
                # The managed client may have changed storage while opening.
                await self._snapshot()
            self._live = True
            return self
        except BaseException as error:
            await self.aclose()
            if isinstance(error, asyncio.CancelledError):
                raise
            raise SubscriptionRequired(
                "Managed subscription startup unavailable"
            ) from None

    async def __aexit__(self, *_):
        await self.aclose()

    async def aclose(self):
        self._live = False
        if self._closing is None:
            self._closing = asyncio.create_task(self._shutdown())
            self._closing.add_done_callback(
                lambda done: None if done.cancelled() else done.exception()
            )
        await asyncio.shield(self._closing)

    async def _shutdown(self):
        try:
            # Retire physical control before draining credential callbacks.
            await self.rpc.aclose()
        finally:
            pending = tuple(self._pending)
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            self._account = None

    def connection(self, *, active=lambda: True):
        """Mint one connection's snapshot history under this host authority."""
        if not self._live:
            raise RuntimeError("Managed subscription owner is unavailable")
        last_digest = None

        async def tokens(*, reason=None, account_id=None):
            nonlocal last_digest
            result = await self._resolve(
                reason, account_id, last_digest, auth._can_send
            )
            last_digest = self._digest(result)
            return result

        auth = ExternalChatGPTAuth(
            tokens,
            active=lambda: self._live and active(),
            expected_account_id=self._account,
        )
        return auth

    @staticmethod
    def _digest(credential):
        return hashlib.sha256(credential.access_token.encode()).digest()

    def _check(self, allowed):
        if not self._live or not allowed():
            raise _ConsumerWithdrawn("Managed subscription authority withdrawn")

    @staticmethod
    def _check_response(response):
        if (
            not isinstance(response, dict)
            or (response.get("account") or {}).get("type") != "chatgpt"
            or response.get("requiresOpenaiAuth") is not True
        ):
            raise SubscriptionRequired("Managed subscription account unavailable")

    async def _snapshot(self):
        credential = await asyncio.to_thread(self.source.read)
        if credential.account_id != self._account:
            raise SubscriptionRequired("Managed subscription account changed")
        return credential

    async def _resolve(self, reason, account, digest, allowed):
        self._check(allowed)
        if account != self._account or reason not in (None, "unauthorized"):
            raise SubscriptionRequired("Invalid managed subscription request")
        if len(self._pending) >= self.max_pending:
            raise SubscriptionRequired("Managed subscription capacity reached")
        task = asyncio.create_task(self._work(reason, digest, allowed))
        self._pending.add(task)

        def finished(done):
            self._pending.discard(done)
            # The requesting session may already have been cancelled; consume
            # owned task failures without exposing source/SDK error details.
            if not done.cancelled():
                done.exception()

        task.add_done_callback(finished)
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            if task.cancelled() and not asyncio.current_task().cancelling():
                # Host shutdown cancelled the owned resolution, not this native
                # callback. Fail its connection promptly instead of silently
                # dropping the refresh response until a turn deadline expires.
                raise SubscriptionRequired(
                    "Managed subscription owner closed"
                ) from None
            raise

    async def _work(self, reason, digest, allowed):
        try:
            async with asyncio.timeout(self.timeout), self._lock:
                self._check(allowed)
                before = await self._snapshot()
                self._check(allowed)
                if reason is None or self._digest(before) != digest:
                    return before
                self._check_response(
                    await self.rpc.request(
                        "account/read",
                        {"refreshToken": True},
                        # After host admission the rotation belongs to this
                        # account owner, independently of a consumer's lifetime.
                        _guard=lambda: self._live,
                    )
                )
                after = await self._snapshot()
                if self._digest(after) == digest:
                    raise SubscriptionRequired("Managed subscription did not rotate")
                return after
        except asyncio.CancelledError:
            raise
        except _ConsumerWithdrawn:
            raise
        except Exception:  # noqa: BLE001 — source/SDK errors may contain credentials
            self._live = False
            await self.rpc.aclose()
            raise SubscriptionRequired(
                "Managed subscription refresh unavailable"
            ) from None
