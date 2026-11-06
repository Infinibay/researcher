"""Shared bounded transport for fixed host-configured documentation/scraping providers.

Adapters own endpoint, method and response interpretation. This transport owns
credentials, public DNS/TLS, one request's limits and physical connection closure.
"""

import re
import time
from contextlib import closing, contextmanager, nullcontext
from http.client import HTTPException
from threading import Event

from backend.network_destinations import (
    PublicNetworkError,
    public_address,
    resolve_addresses,
)
from backend.research.models import ResearchForbidden, SourceTooLarge, SourceUnavailable
from backend.research.web_fetcher import PinnedHTTPSConnection


class OwnedProviderTransport:
    """Reuse owned I/O only for the fixed origin and endpoints declared by a host adapter."""

    _host = ""
    _label = "Provider"
    _key_name = ""
    _paths = frozenset()
    _method = "GET"
    _response_bound = 200000
    _status_reasons = {}

    def __init__(
        self,
        *,
        api_key,
        owner=None,
        grant_id=None,
        resolver=resolve_addresses,
        connection_factory=PinnedHTTPSConnection,
        timeout_seconds=12,
        max_bytes=None,
        clock=time.monotonic,
    ):
        """Bind a host credential and fixed adapter policy without acquiring a resource."""
        if not self._host or not self._paths or self._method not in ("GET", "POST"):
            raise ValueError("A concrete fixed-origin provider adapter is required")
        if (owner is None) != (grant_id is None):
            raise ValueError(f"{self._label} owner and grant must be supplied together")
        max_bytes = self._response_bound if max_bytes is None else max_bytes
        if not 0 < timeout_seconds <= 12 or not 0 < max_bytes <= self._response_bound:
            raise ValueError(f"{self._label} requires bounded time and source bytes")
        self._key = api_key
        self.owner, self.grant_id = owner, grant_id
        self.resolve, self.connection_factory = resolver, connection_factory
        self.timeout_seconds, self.max_bytes, self.clock = (
            timeout_seconds,
            max_bytes,
            clock,
        )

    @contextmanager
    def _operation(self):
        """Require a host key and retain ownership through response interpretation and connection cleanup."""
        if not self._key:
            raise SourceUnavailable(
                f"{self._label} is not configured; set {self._key_name} on the host"
            )
        if not isinstance(self._key, str) or not re.fullmatch(
            r"[!-~]{1,4096}", self._key
        ):
            raise SourceUnavailable(
                f"{self._label} host credential has an invalid format"
            )
        ownership = (
            self.owner.operation(self.grant_id) if self.owner else nullcontext(Event())
        )
        with ownership as cancelled:
            yield self.clock() + self.timeout_seconds, cancelled

    def _remaining(self, deadline, cancelled):
        """Fence each boundary against withdrawal and preserve one deadline through DNS, TLS and body reads."""
        if cancelled.is_set():
            raise ResearchForbidden(f"{self._label} operation authority was withdrawn")
        remaining = deadline - self.clock()
        if remaining <= 0:
            raise SourceUnavailable(
                f"{self._label} request exceeded its deadline; no source was saved"
            )
        return remaining

    def _public_addresses(self, host, deadline, cancelled):
        """Validate every bounded DNS answer; a mixed public/private answer cannot choose the public subset."""
        try:
            addresses = self.resolve(host, self._remaining(deadline, cancelled))
            if not addresses or len(addresses) > 64:
                raise SourceUnavailable(f"{self._label} has no bounded DNS address set")
            return [public_address(address) for address in addresses]
        except PublicNetworkError:
            raise SourceUnavailable(
                f"{self._label} requires publicly resolved targets"
            ) from None

    def _request(self, target, deadline, cancelled, *, body=None):
        """Send one bounded request to the adapter's fixed endpoint; never redirect or retry its credentials."""
        if target.split("?", 1)[0] not in self._paths or any(
            ord(c) < 32 for c in target
        ):
            raise SourceUnavailable(f"{self._label} endpoint is not admitted")
        if body is not None and (not isinstance(body, bytes) or len(body) > 32768):
            raise SourceTooLarge(f"{self._label} request body exceeds its byte limit")
        try:
            vetted = self._public_addresses(self._host, deadline, cancelled)
            address = str(min(vetted, key=lambda item: (item.version, str(item))))
            with closing(
                self.connection_factory(
                    self._host, 443, address, self._remaining(deadline, cancelled)
                )
            ) as conn:
                headers = {
                    "Authorization": "Bearer " + self._key,
                    "User-Agent": "Researcher/0.1 provider-reader",
                    "Accept": "application/json,text/plain",
                    "Accept-Encoding": "identity",
                }
                if body is not None:
                    headers["Content-Type"] = "application/json"
                conn.request(self._method, target, body=body, headers=headers)
                if conn.sock is not None:
                    conn.sock.settimeout(self._remaining(deadline, cancelled))
                with conn.getresponse() as response:
                    if response.status != 200:
                        reason = self._status_reasons.get(
                            response.status, "provider request failed"
                        )
                        raise SourceUnavailable(
                            f"{self._label} HTTP {response.status}: {reason}; no automatic retry"
                        )
                    if response.getheader(
                        "Content-Encoding", "identity"
                    ).lower() not in ("", "identity"):
                        raise SourceUnavailable(
                            f"{self._label} returned unsupported content encoding"
                        )
                    length = response.getheader("Content-Length")
                    if length is not None and not length.isdigit():
                        raise SourceUnavailable(
                            f"{self._label} returned an invalid content length"
                        )
                    if length is not None and int(length) > self.max_bytes:
                        raise SourceTooLarge(
                            f"{self._label} response exceeds the source byte limit"
                        )
                    mime = response.headers.get_content_type()
                    if mime not in ("application/json", "text/plain"):
                        raise SourceUnavailable(
                            f"{self._label} returned an unsupported content type"
                        )
                    data = bytearray()
                    while len(data) <= self.max_bytes:
                        remaining = self._remaining(deadline, cancelled)
                        if conn.sock is not None:
                            conn.sock.settimeout(remaining)
                        chunk = response.read1(
                            min(65536, self.max_bytes + 1 - len(data))
                        )
                        if not chunk:
                            break
                        data.extend(chunk)
                    if len(data) > self.max_bytes:
                        raise SourceTooLarge(
                            f"{self._label} response exceeds the source byte limit"
                        )
                    if length is not None and len(data) != int(length):
                        raise SourceUnavailable(
                            f"{self._label} response ended early; no partial source was saved"
                        )
                    self._remaining(deadline, cancelled)
                    return bytes(data), mime
        except ResearchForbidden:
            raise
        except (PublicNetworkError, OSError, HTTPException):
            raise SourceUnavailable(
                f"{self._label} connection failed or exceeded its deadline"
            ) from None
