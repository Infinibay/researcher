"""Public HTTPS source acquisition with pinned DNS, manual redirects and bounds.

No proxy credentials, cookies, private destinations or automatic redirects.
This is a text-source adapter; PDF/binary extraction uses a separate capability.
"""

import hashlib
import ipaddress
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import time
from contextlib import closing
from html.parser import HTMLParser
from http.client import HTTPException, HTTPSConnection
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from backend.research.models import SourceDraft, SourceTooLarge, SourceUnavailable


def _resolve(host: str, timeout: float) -> list[str]:
    # Bound libc DNS in its own reaped child, rather than leave a blocked DNS
    # thread behind when a tool deadline expires. No shell or provider env.
    code = "import socket,sys,json; a=sorted({r[4][0] for r in socket.getaddrinfo(sys.argv[1],443,type=socket.SOCK_STREAM)}); assert 0<len(a)<=64; print(json.dumps(a))"
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-c", code, host],
            capture_output=True,
            text=True,
            timeout=min(timeout, 3),
            env={"PATH": os.defpath},
            check=True,
        )
        return json.loads(result.stdout)
    except (subprocess.SubprocessError, ValueError) as exc:
        raise SourceUnavailable(
            "Public source DNS resolution failed or exceeded its deadline"
        ) from exc


def _public_address(value: str):
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise SourceUnavailable("Source DNS returned an invalid address") from exc
    if (
        not address.is_global
        or address.is_multicast
        or address.is_reserved
        or isinstance(address, ipaddress.IPv6Address)
        and (address.sixtofour is not None or address.teredo is not None)
    ):
        raise SourceUnavailable(
            "Source destination must resolve only to public Internet addresses"
        )
    return address


class _DeadlineSSLSocket(ssl.SSLSocket):
    """Bound each network receive, including slow-drip response headers."""

    def _bound_receive(self):
        deadline = getattr(self, "_source_deadline", None)
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Source deadline exceeded")
            self.settimeout(remaining)

    def recv_into(self, *args, **kwargs):
        self._bound_receive()
        return super().recv_into(*args, **kwargs)

    def recv(self, *args, **kwargs):
        self._bound_receive()
        return super().recv(*args, **kwargs)


class PinnedHTTPSConnection(HTTPSConnection):
    """Use the vetted numeric address while retaining original TLS/Host identity."""

    def __init__(self, host, port, address, timeout, *, context=None):
        self.pinned_address = address
        self.tls_context = context or ssl.create_default_context()
        self.tls_context.set_alpn_protocols(["http/1.1"])
        self.tls_context.sslsocket_class = _DeadlineSSLSocket
        super().__init__(host, port, timeout=timeout, context=self.tls_context)

    def connect(self):
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


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.title = []
        self.in_title = False
        self.ignored = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.ignored.append(tag)
        if tag == "title":
            self.in_title = True
        if tag in ("p", "div", "li", "pre", "br", "h1", "h2", "h3", "table", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.ignored and self.ignored[-1] == tag:
            self.ignored.pop()
        if tag == "title":
            self.in_title = False
        if tag in ("p", "div", "li", "pre", "h1", "h2", "h3", "tr"):
            self.parts.append("\n")

    def handle_data(self, data):
        if self.ignored:
            return
        if self.in_title:
            self.title.append(data)
        self.parts.append(data)


class PublicWebFetcher:
    def __init__(
        self,
        *,
        resolver=_resolve,
        connection_factory=PinnedHTTPSConnection,
        timeout_seconds=12,
        max_bytes=1000000,
        max_redirects=3,
        clock=time.monotonic,
    ):
        if timeout_seconds <= 0 or max_bytes <= 0 or max_redirects < 0:
            raise ValueError("Invalid web acquisition limits")
        self.resolve = resolver
        self.connection_factory = connection_factory
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self.clock = clock

    def _remaining(self, deadline):
        remaining = deadline - self.clock()
        if remaining <= 0:
            raise SourceUnavailable("Public source acquisition exceeded its deadline")
        return remaining

    @staticmethod
    def _url(url):
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
        requested = url
        current = url
        deadline = self.clock() + self.timeout_seconds
        for hop in range(self.max_redirects + 1):
            host, target, normalized, literal = self._url(current)
            addresses = (
                [str(literal)]
                if literal is not None
                else self.resolve(host, self._remaining(deadline))
            )
            if not addresses or len(addresses) > 64:
                raise SourceUnavailable("Public source has no bounded DNS address set")
            vetted = [_public_address(address) for address in addresses]
            address = str(min(vetted, key=lambda value: (value.version, str(value))))
            try:
                with closing(
                    self.connection_factory(
                        host, 443, address, self._remaining(deadline)
                    )
                ) as conn:
                    conn.request(
                        "GET",
                        target,
                        headers={
                            "User-Agent": "Researcher/0.1 source-reader",
                            "Accept": "text/html,text/plain,application/json",
                            "Accept-Encoding": "identity",
                        },
                    )
                    if conn.sock is not None:
                        conn.sock.settimeout(self._remaining(deadline))
                    with conn.getresponse() as response:
                        if response.status in (301, 302, 303, 307, 308):
                            location = response.getheader("Location")
                            if (
                                hop >= self.max_redirects
                                or not location
                                or len(location) > 4096
                            ):
                                raise SourceUnavailable(
                                    "Public source redirect limit exceeded or missing destination"
                                )
                            current = urljoin(normalized, location)
                            continue
                        if not 200 <= response.status < 300:
                            raise SourceUnavailable(
                                f"Public source returned HTTP {response.status}"
                            )
                        if response.getheader(
                            "Content-Encoding", "identity"
                        ).lower() not in ("", "identity"):
                            raise SourceUnavailable(
                                "Compressed source responses are not accepted by this bounded text route"
                            )
                        length = response.getheader("Content-Length")
                        if length is not None:
                            if not length.isdigit():
                                raise SourceUnavailable(
                                    "Public source returned an invalid length"
                                )
                            if int(length) > self.max_bytes:
                                raise SourceTooLarge(
                                    "Public source exceeds the byte limit"
                                )
                        mime = response.headers.get_content_type()
                        if not (
                            mime.startswith("text/")
                            or mime
                            in (
                                "application/json",
                                "application/xml",
                                "application/xhtml+xml",
                            )
                        ):
                            raise SourceUnavailable(
                                "Public source content type requires a dedicated parser"
                            )
                        charset = response.headers.get_content_charset() or "utf-8"
                        chunks = []
                        size = 0
                        while size <= self.max_bytes:
                            remaining = self._remaining(deadline)
                            if conn.sock is not None:
                                conn.sock.settimeout(remaining)
                            chunk = response.read1(
                                min(65536, self.max_bytes + 1 - size)
                            )
                            if not chunk:
                                break
                            chunks.append(chunk)
                            size += len(chunk)
                        if size > self.max_bytes:
                            raise SourceTooLarge("Public source exceeds the byte limit")
                        data = b"".join(chunks)
            except (OSError, HTTPException) as exc:
                raise SourceUnavailable(
                    "Public source connection failed or exceeded its deadline"
                ) from exc
            try:
                text = data.decode(charset)
            except (LookupError, UnicodeError) as exc:
                raise SourceUnavailable(
                    "Public source text encoding is unsupported or invalid"
                ) from exc
            title = host + target
            if mime in ("text/html", "application/xhtml+xml"):
                parser = _HTMLText()
                parser.feed(text)
                parser.close()
                text = "\n".join(
                    line.strip()
                    for line in "".join(parser.parts).splitlines()
                    if line.strip()
                )
                title = " ".join("".join(parser.title).split()) or title
            if len(text.encode("utf-8")) > 200000:
                raise SourceTooLarge(
                    "Extracted source exceeds the text limit; use a bounded document parser"
                )
            self._remaining(deadline)
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
                    "extraction": "html-text-v1"
                    if mime in ("text/html", "application/xhtml+xml")
                    else "decoded-text-v1",
                    "redirects": hop,
                    "resolved_public_address": address,
                },
            )
        raise SourceUnavailable("Public source redirect limit exceeded")
