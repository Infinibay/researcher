"""Host-owned ChatGPT access credentials; never API-key/provider fallback.

An existing private file supplies a snapshot, not proof of remote entitlement.
Actual OAuth renewal belongs to the host credential lifecycle provider. A reread
of an unchanged token must never be presented as successful renewal.
"""

import asyncio
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from backend.runtime.codex_session import SubscriptionRequired


@dataclass(frozen=True, repr=False)
class ChatGPTCredentials:
    """Carry a validated access-token snapshot with a redacted representation; syntax validation does
    not verify its signature, expiry or remote subscription entitlement.
    """
    access_token: str
    account_id: str
    plan_type: str | None = None

    def __post_init__(self):
        """Validate bounded token/account/plan fields before they can become RPC parameters; never
        perform network authentication here.
        """
        if (
            not isinstance(self.access_token, str)
            or len(self.access_token) > 65536
            or re.fullmatch(
                r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", self.access_token
            )
            is None
            or not isinstance(self.account_id, str)
            or not 1 <= len(self.account_id) <= 256
            or any(c in self.account_id for c in "\r\n\0")
            or self.plan_type is not None
            and (
                not isinstance(self.plan_type, str)
                or not 1 <= len(self.plan_type) <= 64
            )
        ):
            raise SubscriptionRequired("Invalid host subscription credential snapshot")

    def __repr__(self):
        """Return a fixed redacted identity without exposing account or access-token contents."""
        return "<ChatGPTCredentials redacted>"

    def rpc_params(self):
        """Export only the access-token snapshot, account ID and optional plan for private
        authentication RPC; no refresh token or provider fallback is included.
        """
        return {
            "accessToken": self.access_token,
            "chatgptAccountId": self.account_id,
            "chatgptPlanType": self.plan_type,
        }


class ManagedTokenFile:
    """Read an existing CLI-managed file; optionally ask its host to renew it.

    No refresh token or API key crosses this boundary. Without a renewal hook,
    refresh only rereads externally rotated state; the connection must reject an
    unchanged token. This adapter does not implement OAuth renewal by itself.
    """

    def __init__(self, path, *, renew=None):
        """Select an existing absolute credential path and optional host renewal hook without reading,
        creating or modifying credential storage.
        """
        self.path = Path(path).absolute()
        self.renew = renew

    def read(self):
        """Read one bounded private owner-only regular file with stable descriptor/path identity and
        require ChatGPT mode; return only access credentials and sanitize source errors.
        """
        fd = None
        try:
            fd = os.open(
                self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
            )
            before = os.fstat(fd)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_uid != os.getuid()
                or before.st_nlink != 1
                or stat.S_IMODE(before.st_mode) & 0o077
                or not 0 < before.st_size <= 1048576
            ):
                raise SubscriptionRequired(
                    "Host subscription file is not private or bounded"
                )
            data = bytearray()
            while len(data) <= 1048576:
                block = os.read(fd, min(8192, 1048577 - len(data)))
                if not block:
                    break
                data.extend(block)
            after = os.fstat(fd)
            path = self.path.lstat()
            fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
            if (
                len(data) > 1048576
                or any(getattr(before, k) != getattr(after, k) for k in fields)
                or (path.st_dev, path.st_ino) != (before.st_dev, before.st_ino)
            ):
                raise SubscriptionRequired("Host subscription changed during read")
            value = json.loads(data)
            if value.get("auth_mode") != "chatgpt":
                raise SubscriptionRequired("Host login must use a ChatGPT subscription")
            return ChatGPTCredentials(
                value["tokens"]["access_token"], value["tokens"]["account_id"]
            )
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            raise SubscriptionRequired(
                "Host subscription credentials are unavailable or invalid"
            ) from None
        finally:
            if fd is not None:
                os.close(fd)

    async def tokens(self, *, reason=None, account_id=None):
        """Optionally invoke the configured host renewal hook for a refresh reason, then read off the
        event loop; rereading alone does not prove a token rotated.
        """
        if reason is not None and self.renew is not None:
            await self.renew(account_id)
        return await asyncio.to_thread(self.read)


class ExternalChatGPTAuth:
    """One connection's account-bound host credentials, separate from turn events.

    A login receipt confirms local SDK installation, not remote entitlement.
    The source owns actual renewal. This adapter never sends a refresh token,
    chooses another account/provider or replays a client turn.
    """

    METHOD = "account/chatgptAuthTokens/refresh"

    def __init__(
        self,
        tokens,
        *,
        active=lambda: True,
        timeout=8,
        max_refreshes=2,
        expected_account_id=None,
    ):
        """Configure bounded account-bound authentication for one RPC connection, initially unattached
        and without credentials or a login attempt.
        """
        if (
            not callable(tokens)
            or not 0 < timeout <= 8
            or type(max_refreshes) is not int
            or not 1 <= max_refreshes <= 4
        ):
            raise ValueError("Bounded host authentication parameters required")
        self.tokens, self.active = tokens, active
        self.timeout, self.max_refreshes = timeout, max_refreshes
        self.account_id = expected_account_id
        self.failure_code = None
        self._rpc = None
        self._attached = False
        self._login_started = False
        self._digest = None
        self._refreshes = 0
        self._refresh_lock = asyncio.Lock()
        self._withdrawn = False

    def bind(self, rpc):
        """Attach the guarded private refresh handler once to the selected RPC connection without
        starting login or a model turn.
        """
        if self._attached:
            raise RuntimeError("Subscription auth cannot be reused across connections")
        rpc.register_private_request(self.METHOD, self._refresh, allowed=self._can_send)
        self._attached = True
        self._rpc = rpc

    def _reject(self, code):
        """Retain a non-secret failure code and raise a subscription error without copying credential
        payloads into it.
        """
        self.failure_code = code
        raise SubscriptionRequired(
            "Host subscription authentication unavailable: " + code
        )

    def _check_active(self):
        """Reject credential delivery after connection withdrawal or loss of the host activity
        predicate.
        """
        if not self._can_send():
            self._reject("inactive")

    def _can_send(self):
        """Check local connection attachment and current host authority; this predicate does not
        validate remote entitlement.
        """
        return self._rpc is not None and not self._withdrawn and self.active()

    def withdraw(self):
        """Irreversibly stop further credential sends for this connection without cancelling or
        replaying a native turn.
        """
        self._withdrawn = True

    async def _load(self, reason):
        """Load a bounded typed snapshot only while active and preserve the original account; sanitize
        source failures that may contain credentials.
        """
        self._check_active()
        try:
            async with asyncio.timeout(self.timeout):
                result = await self.tokens(reason=reason, account_id=self.account_id)
        except Exception:  # noqa: BLE001 — source errors may contain credentials
            self.failure_code = "credentials_unavailable"
            raise SubscriptionRequired(
                "Host subscription credentials unavailable"
            ) from None
        self._check_active()
        if not isinstance(result, ChatGPTCredentials):
            self._reject("invalid_snapshot")
        if self.account_id is not None and result.account_id != self.account_id:
            self._reject("account_changed")
        return result

    async def login(self):
        """Attempt one guarded access-token login on the bound connection and require its expected
        local receipt; an unconfirmed login is not retried here.
        """
        if self._login_started or self._rpc is None:
            raise RuntimeError("Bind one subscription login to an open connection")
        self._login_started = True
        credential = await self._load(None)
        self.account_id = credential.account_id
        self._digest = hashlib.sha256(credential.access_token.encode()).digest()
        self._check_active()
        try:
            response = await self._rpc.request(
                "account/login/start",
                {"type": "chatgptAuthTokens", **credential.rpc_params()},
                timeout=self.timeout,
                _guard=self._can_send,
            )
        except Exception:  # noqa: BLE001 — RPC errors may echo credential payloads
            self.failure_code = "login_unconfirmed"
            raise SubscriptionRequired(
                "Native subscription login was not confirmed"
            ) from None
        if response.get("type") != "chatgptAuthTokens":
            self._reject("login_mode_changed")

    async def _refresh(self, params):
        """Serialize bounded unauthorized refreshes for the same account and require a changed token
        before replying; never replay the client turn.
        """
        async with asyncio.timeout(self.timeout), self._refresh_lock:
            self._check_active()
            if self.account_id is None or params.get("previousAccountId") not in (
                None,
                self.account_id,
            ):
                self._reject("account_changed")
            if params.get("reason") != "unauthorized":
                self._reject("unsupported_refresh")
            if self._refreshes >= self.max_refreshes:
                self._reject("refresh_limit")
            self._refreshes += 1
            credential = await self._load("unauthorized")
            digest = hashlib.sha256(credential.access_token.encode()).digest()
            if digest == self._digest:
                self._reject("unchanged_credential")
            self._check_active()
            self._digest = digest
            return credential.rpc_params()

    def close(self):
        """Withdraw this connection and clear retained account, token digest and RPC references without
        closing the shared host credential provider.
        """
        self.withdraw()
        self.account_id = None
        self._digest = None
        self._rpc = None
