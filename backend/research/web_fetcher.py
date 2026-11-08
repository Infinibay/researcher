"""Public HTTPS source acquisition with robots/rate policy, pinned DNS and bounds.

No proxy credentials, cookies, private destinations or automatic redirects.
Text and PDF snapshots share URL policy; PDF extraction uses the owned worker.
"""

import hashlib
import ipaddress
import re
import socket
import ssl
import time
from contextlib import closing, contextmanager, nullcontext
from html.parser import HTMLParser
from http.client import HTTPException, HTTPSConnection
from threading import Event
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from backend.network_destinations import (
    PublicNetworkError,
    public_address,
    resolve_addresses,
)
from backend.research.models import (
    ResearchForbidden,
    SourceDraft,
    SourceTooLarge,
    SourceUnavailable,
)
from backend.research.web_policy import DEFAULT_WEB_POLICY, MAX_ROBOTS_BYTES, USER_AGENT


def _resolve(host: str, timeout: float) -> list[str]:
    """Translate bounded DNS resolution failures into an explicit source-unavailable result."""
    try:
        return resolve_addresses(host, timeout)
    except PublicNetworkError:
        raise SourceUnavailable(
            "Public source DNS resolution failed or exceeded its deadline"
        ) from None


def _public_address(value: str):
    """Require a public numeric destination and translate address-policy rejection to a source error."""
    try:
        return public_address(value)
    except PublicNetworkError:
        raise SourceUnavailable(
            "Source destination must resolve only to public Internet addresses"
        ) from None


class _DeadlineSSLSocket(ssl.SSLSocket):
    """Bound each network receive, including slow-drip response headers."""

    def _bound_receive(self):
        """Apply the remaining acquisition deadline before each TLS receive, refusing expired reads."""
        deadline = getattr(self, "_source_deadline", None)
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Source deadline exceeded")
            self.settimeout(remaining)

    def recv_into(self, *args, **kwargs):
        """Bound the next TLS read into a caller buffer by the original acquisition deadline."""
        self._bound_receive()
        return super().recv_into(*args, **kwargs)

    def recv(self, *args, **kwargs):
        """Bound the next TLS byte read by the original acquisition deadline."""
        self._bound_receive()
        return super().recv(*args, **kwargs)


class PinnedHTTPSConnection(HTTPSConnection):
    """Use the vetted numeric address while retaining original TLS/Host identity."""

    def __init__(self, host, port, address, timeout, *, context=None):
        """Retain the vetted numeric destination while configuring TLS for the original requested host."""
        self.pinned_address = address
        self.tls_context = context or ssl.create_default_context()
        self.tls_context.set_alpn_protocols(["http/1.1"])
        self.tls_context.sslsocket_class = _DeadlineSSLSocket
        super().__init__(host, port, timeout=timeout, context=self.tls_context)

    def connect(self):
        """Connect to the pinned address using the original TLS hostname and deadline-bounded receives; verification follows the configured context."""
        deadline = time.monotonic() + self.timeout
        raw = socket.create_connection((self.pinned_address, self.port), self.timeout)
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Source connection deadline exceeded")
            raw.settimeout(remaining)
            self.sock = self.tls_context.wrap_socket(raw, server_hostname=self.host)
            self.sock._source_deadline = deadline
        except BaseException:
            raw.close()
            raise


class _HTMLTitle(HTMLParser):
    """Read the page title without using the title parser as a content extractor."""

    def __init__(self):
        """Start a title-only view of the bounded, already decoded HTML."""
        super().__init__(convert_charrefs=True)
        self.title = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        """Begin retaining text only inside a title element."""
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        """Stop title collection at its closing element."""
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        """Retain literal decoded title text only."""
        if self.in_title:
            self.title.append(data)


class PublicWebFetcher:
    """Acquire public HTTPS text/PDF with pinned addresses, bounded I/O and owned lifetime."""

    def __init__(
        self,
        *,
        resolver=_resolve,
        connection_factory=PinnedHTTPSConnection,
        timeout_seconds=12,
        max_bytes=1000000,
        max_redirects=3,
        clock=time.monotonic,
        pdf_parser=None,
        owner=None,
        grant_id=None,
        policy=None,
    ):
        """Bind trusted transport/parser policy and optional host operation ownership."""
        if (owner is None) != (grant_id is None):
            raise ValueError(
                "Web source owner and grant identity must be supplied together"
            )
        if timeout_seconds <= 0 or max_bytes <= 0 or max_redirects < 0:
            raise ValueError("Invalid web acquisition limits")
        self.resolve = resolver
        self.connection_factory = connection_factory
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self.clock = clock
        self.pdf_parser = pdf_parser
        self.owner, self.grant_id = owner, grant_id
        self.policy = DEFAULT_WEB_POLICY if policy is None else policy

    def _remaining(self, deadline, cancelled):
        """Reject withdrawn work before each network/parser step and preserve one deadline."""
        if cancelled.is_set():
            raise ResearchForbidden("Web source authority was withdrawn")
        remaining = deadline - self.clock()
        if remaining <= 0:
            raise SourceUnavailable("Public source acquisition exceeded its deadline")
        return remaining

    @staticmethod
    def _url(url):
        """Validate HTTPS syntax and normalize the request target; DNS address policy is checked separately."""
        if (
            not isinstance(url, str)
            or not 1 <= len(url) <= 4096
            or any(c.isspace() or ord(c) < 32 for c in url)
            or "\\" in url
        ):
            raise SourceUnavailable("Invalid public HTTPS source URL")
        try:
            parsed = urlsplit(url)
            if (
                parsed.scheme != "https"
                or parsed.username is not None
                or parsed.password is not None
                or parsed.port not in (None, 443)
                or not parsed.hostname
            ):
                raise ValueError("Unsupported origin")
            host = parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower()
            if "%" in host:
                raise ValueError("Zone and escaped hostnames are not supported")
            try:
                literal = ipaddress.ip_address(host)
            except ValueError:
                literal = None
            if literal is not None:
                _public_address(host)
                authority = "[" + host + "]" if literal.version == 6 else host
            else:
                labels = host.split(".")
                if (
                    len(labels) < 2
                    or len(host) > 253
                    or any(
                        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part)
                        for part in labels
                    )
                ):
                    raise ValueError("Invalid hostname")
                if re.fullmatch(
                    r"(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+))*", host
                ):
                    raise ValueError("Non-canonical numeric hostname")
                authority = host
            path = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
            query = quote(parsed.query, safe="/%?:@!$&'()*+,;=-._~")
            target = path + ("?" + query if query else "")
            return (
                host,
                target,
                urlunsplit(("https", authority, path, query, "")),
                literal,
            )
        except (ValueError, UnicodeError) as exc:
            raise SourceUnavailable(
                "Only public HTTPS origins on port 443 without credentials are supported"
            ) from exc

    def fetch(self, url: str) -> SourceDraft:
        """Capture a complete public source; no partial body or guessed PDF text is saved."""
        operation = (
            self.owner.operation(self.grant_id) if self.owner else nullcontext(Event())
        )
        with operation as cancelled:
            return self._fetch(url, cancelled)

    def check_access(self, url, *, deadline, cancelled):
        """Check a source target inside an existing owned operation without fetching its page."""
        normalized = self._url(url)[2]
        return self.policy.authorize(
            normalized,
            lambda value: self._robots(value, deadline, cancelled),
            deadline,
            cancelled,
        )

    @contextmanager
    def _response(self, url, deadline, cancelled):
        """Own one rate-limited HTTP exchange after validating and pinning every address."""
        host, target, normalized, literal = self._url(url)
        try:
            addresses = (
                [str(literal)] if literal is not None
                else self.resolve(host, self._remaining(deadline, cancelled))
            )
        except PublicNetworkError:
            raise SourceUnavailable("Public source DNS resolution failed") from None
        if not addresses or len(addresses) > 64:
            raise SourceUnavailable("Public source has no bounded DNS address set")
        vetted = [_public_address(address) for address in addresses]
        address = str(min(vetted, key=lambda value: (value.version, str(value))))
        self.policy.acquire(deadline, cancelled)
        try:
            with closing(self.connection_factory(
                host, 443, address, self._remaining(deadline, cancelled)
            )) as conn:
                conn.request("GET", target, headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,text/plain,application/json,application/pdf",
                    "Accept-Encoding": "identity",
                })
                if conn.sock is not None:
                    conn.sock.settimeout(self._remaining(deadline, cancelled))
                with conn.getresponse() as response:
                    yield conn, response, address, normalized
        except ResearchForbidden:
            raise
        except (OSError, HTTPException) as exc:
            raise SourceUnavailable(
                "Public source connection failed or exceeded its deadline"
            ) from exc

    def _body(self, conn, response, limit, deadline, cancelled):
        """Read a complete identity-encoded body within one byte and time budget."""
        if response.getheader("Content-Encoding", "identity").lower() not in ("", "identity"):
            raise SourceUnavailable("Compressed source responses are not accepted by this bounded text route")
        length = response.getheader("Content-Length")
        if length is not None:
            if not length.isdigit():
                raise SourceUnavailable("Public source returned an invalid length")
            if int(length) > limit:
                raise SourceTooLarge("Public source exceeds the byte limit")
        chunks, size = [], 0
        while size <= limit:
            remaining = self._remaining(deadline, cancelled)
            if conn.sock is not None:
                conn.sock.settimeout(remaining)
            chunk = response.read1(min(65536, limit + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        if size > limit:
            raise SourceTooLarge("Public source exceeds the byte limit")
        if length is not None and size != int(length):
            raise SourceUnavailable(
                "Public source body ended before its declared length; no partial source was saved"
            )
        return b"".join(chunks)

    def _robots(self, url, deadline, cancelled):
        """Load robots via the same owned HTTPS transport, with at most five redirects."""
        current = url
        for hop in range(6):
            with self._response(current, deadline, cancelled) as (conn, reply, _, normalized):
                if reply.status in (301, 302, 303, 307, 308):
                    location = reply.getheader("Location")
                    if hop == 5 or not location or len(location) > 4096:
                        raise SourceUnavailable("robots.txt redirect limit exceeded or missing destination")
                    current = urljoin(normalized, location)
                    continue
                if not 200 <= reply.status < 300:
                    return reply.status, b"", normalized
                if reply.headers.get_content_type() != "text/plain":
                    raise SourceUnavailable("robots.txt must be served as text/plain")
                return reply.status, self._body(
                    conn, reply, MAX_ROBOTS_BYTES, deadline, cancelled
                ), normalized
        raise SourceUnavailable("robots.txt redirect limit exceeded")

    def _fetch(self, url: str, cancelled) -> SourceDraft:
        """Own policy checks, connections and parsing until cancellation cleanup finishes."""
        requested = current = url
        deadline = self.clock() + self.timeout_seconds
        policy_evidence = []
        for hop in range(self.max_redirects + 1):
            host, target, normalized, _ = self._url(current)
            decision = self.check_access(normalized, deadline=deadline, cancelled=cancelled)
            policy_evidence.append({"url": normalized, **decision})
            with self._response(normalized, deadline, cancelled) as (conn, response, address, _):
                if response.status in (301, 302, 303, 307, 308):
                    location = response.getheader("Location")
                    if hop >= self.max_redirects or not location or len(location) > 4096:
                        raise SourceUnavailable("Public source redirect limit exceeded or missing destination")
                    current = urljoin(normalized, location)
                    continue
                if not 200 <= response.status < 300:
                    raise SourceUnavailable(f"Public source returned HTTP {response.status}")
                mime = response.headers.get_content_type()
                if not (mime.startswith("text/") or mime in (
                    "application/json", "application/xml", "application/xhtml+xml",
                    "application/pdf", "application/octet-stream",
                )):
                    raise SourceUnavailable("Public source content type requires a dedicated parser")
                charset = response.headers.get_content_charset() or "utf-8"
                data = self._body(conn, response, self.max_bytes, deadline, cancelled)
            title = host + target
            if mime == "application/pdf" or (
                mime == "application/octet-stream" and data.startswith(b"%PDF-")
            ):
                from backend.research.parser_process import PDFParser

                parser = self.pdf_parser or PDFParser(
                    owner=self.owner, grant_id=self.grant_id
                )
                text, extraction = parser.read(
                    data, max_wall_seconds=self._remaining(deadline, cancelled)
                )
            else:
                if mime == "application/octet-stream" or data.startswith(b"%PDF-"):
                    raise SourceUnavailable(
                        "Unsupported binary or mismatched PDF content type"
                    )
                try:
                    text = data.decode(charset)
                except (LookupError, UnicodeError) as exc:
                    raise SourceUnavailable(
                        "Public source text encoding is unsupported or invalid"
                    ) from exc
                extraction = {"extraction": "decoded-text-v1"}
                if mime in ("text/html", "application/xhtml+xml"):
                    from backend.research.parser_process import DocumentParser

                    heading = _HTMLTitle()
                    heading.feed(text)
                    heading.close()
                    title = " ".join("".join(heading.title).split()) or title
                    parser = (
                        self.pdf_parser.for_format("html") if self.pdf_parser else
                        DocumentParser(format="html", owner=self.owner, grant_id=self.grant_id)
                    )
                    text, extraction = parser.read(
                        text.encode("utf-8"),
                        max_wall_seconds=self._remaining(deadline, cancelled),
                    )
            if len(text.encode("utf-8")) > 200000:
                raise SourceTooLarge(
                    "Extracted source exceeds the text limit; use a bounded document parser"
                )
            self._remaining(deadline, cancelled)
            return SourceDraft(
                kind="web",
                locator=normalized,
                title=title[:300],
                content=text,
                provenance={
                    "requested_url": requested,
                    "byte_sha256": hashlib.sha256(data).hexdigest(),
                    "byte_count": len(data),
                    "mime_type": mime,
                    **extraction,
                    "redirects": hop,
                    "access_policy": policy_evidence,
                    "resolved_public_address": address,
                },
            )
        raise SourceUnavailable("Public source redirect limit exceeded")
