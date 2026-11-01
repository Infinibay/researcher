"""Bounded host CONNECT forwarding over already-admitted client streams.

No listener is exposed here. An owned private-network helper must deliver its
accepted sockets. This component alone does not remove a native direct-net path.
TLS remains opaque end-to-end; only authority/port and resolved IPs are checked.
"""

import math
import re
import select
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass

from backend.network_destinations import (
    PublicNetworkError,
    public_address,
    resolve_addresses,
)


class _Denied(ValueError):
    pass


class _Withdrawn(RuntimeError):
    pass


def _hostname(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 253:
        raise _Denied("Invalid destination")
    value = value.lower()
    labels = value.split(".")
    if (
        len(labels) < 2
        or labels[-1].isdigit()
        or any(
            re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", p) is None
            for p in labels
        )
    ):
        raise _Denied("Explicit DNS destination required")
    return value


@dataclass(frozen=True)
class EgressPolicy:
    hosts: tuple[str, ...]
    max_tunnels: int = 8
    max_connections: int = 64
    max_bytes: int = 16 * 1024**2
    max_total_bytes: int = 128 * 1024**2
    wall_seconds: float = 180
    idle_seconds: float = 30
    header_seconds: float = 3
    connect_seconds: float = 3

    def __post_init__(self):
        if not isinstance(self.hosts, tuple) or not 1 <= len(self.hosts) <= 16:
            raise ValueError("Explicit bounded destination hosts required")
        object.__setattr__(
            self, "hosts", tuple(sorted({_hostname(h) for h in self.hosts}))
        )
        for value, maximum in (
            (self.max_tunnels, 16),
            (self.max_connections, 1024),
            (self.max_bytes, 64 * 1024**2),
            (self.max_total_bytes, 512 * 1024**2),
        ):
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError("Bounded egress capacities required")
        for value, maximum in (
            (self.wall_seconds, 600),
            (self.idle_seconds, 120),
            (self.header_seconds, 3),
            (self.connect_seconds, 3),
        ):
            if (
                isinstance(value, bool)
                or not math.isfinite(value)
                or not 0 < value <= maximum
            ):
                raise ValueError("Bounded egress deadlines required")

    def request_host(self, header):
        try:
            lines = header.decode("ascii").split("\r\n")
        except UnicodeError:
            raise _Denied("Invalid CONNECT header") from None
        parts = lines[0].split(" ")
        if (
            len(parts) != 3
            or parts[0] != "CONNECT"
            or parts[2] not in ("HTTP/1.1", "HTTP/1.0")
        ):
            raise _Denied("CONNECT required")
        authority = parts[1]
        if not authority.endswith(":443"):
            raise _Denied("TLS port required")
        host = _hostname(authority[:-4])
        if host not in self.hosts:
            raise _Denied("Destination not allowed")
        host_header = None
        for line in lines[1:]:
            if not line:
                continue
            if ":" not in line or any(ord(c) < 32 or ord(c) == 127 for c in line):
                raise _Denied("Invalid CONNECT header")
            key, value = line.split(":", 1)
            if key.lower() not in (
                "host",
                "user-agent",
                "connection",
                "proxy-connection",
            ):
                raise _Denied("Unsupported CONNECT header")
            if key.lower() == "host":
                if host_header is not None:
                    raise _Denied("Duplicate CONNECT authority")
                host_header = value.strip().lower()
        if host_header not in (host, host + ":443"):
            raise _Denied("CONNECT authority mismatch")
        return host


@dataclass(frozen=True)
class TunnelReceipt:
    outcome: str
    uploaded: int
    downloaded: int


def _numeric_dial(address, port, timeout, admit):
    parsed = public_address(address)
    raw = socket.socket(
        socket.AF_INET if parsed.version == 4 else socket.AF_INET6, socket.SOCK_STREAM
    )
    try:
        admit(raw)
        raw.settimeout(timeout)
        raw.connect((str(parsed), port))
        return raw
    except BaseException:
        raw.close()
        raise


class TunnelProxy:
    """One host owner's bounded tunnels and nonblocking retirement authority."""

    def __init__(self, policy, *, resolver=resolve_addresses, dial=_numeric_dial):
        self.policy, self.resolver, self.dial = policy, resolver, dial
        self._lock = threading.Lock()
        self._withdrawn = threading.Event()
        self._sockets = set()
        self._futures = set()
        self._connections = self._bytes = 0
        self._pool = ThreadPoolExecutor(
            policy.max_tunnels, thread_name_prefix="researcher-egress"
        )

    def submit(self, client):
        try:
            if (
                client.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE)
                != socket.SOCK_STREAM
            ):
                raise ValueError("Connected stream required")
            client.getpeername()
            with self._lock:
                if (
                    self._withdrawn.is_set()
                    or len(self._futures) >= self.policy.max_tunnels
                    or self._connections >= self.policy.max_connections
                ):
                    raise RuntimeError("Egress unavailable or at capacity")
                self._sockets.add(client)
                self._connections += 1
                future = self._pool.submit(self._handle, client)
                self._futures.add(future)
        except BaseException:
            client.close()
            raise

        def finished(done):
            with self._lock:
                self._futures.discard(done)

        future.add_done_callback(finished)
        return future

    def _check(self):
        if self._withdrawn.is_set():
            raise _Withdrawn("Egress withdrawn")

    def _admit(self, raw):
        with self._lock:
            if self._withdrawn.is_set():
                raw.close()
                raise _Withdrawn("Egress withdrawn")
            self._sockets.add(raw)

    def withdraw(self):
        with self._lock:
            self._withdrawn.set()
            sockets = tuple(self._sockets)
        for raw in sockets:
            try:
                raw.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            raw.close()

    def close(self, *, timeout=4):
        self.withdraw()
        with self._lock:
            pending = tuple(self._futures)
        _done, unfinished = wait(pending, timeout=timeout)
        self._pool.shutdown(wait=False, cancel_futures=True)
        if unfinished:
            raise RuntimeError("Egress workers have not confirmed closure")

    def _header(self, client, deadline):
        data = bytearray()
        while True:
            self._check()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            client.settimeout(remaining)
            block = client.recv(4096)
            if not block:
                raise _Denied("Incomplete CONNECT header")
            data.extend(block)
            end = data.find(b"\r\n\r\n")
            if (end < 0 and len(data) > 16384) or end > 16380:
                raise _Denied("CONNECT header too large")
            if end >= 0:
                return bytes(data[:end]), bytes(data[end + 4 :])

    def _handle(self, client):
        owned = [client]
        counts = [0, 0]
        established = False
        started = time.monotonic()

        def admit(raw):
            owned.append(raw)
            self._admit(raw)

        try:
            header, tail = self._header(
                client,
                started + min(self.policy.header_seconds, self.policy.wall_seconds),
            )
            host = self.policy.request_host(header)
            addresses = self.resolver(
                host,
                min(
                    self.policy.connect_seconds,
                    started + self.policy.wall_seconds - time.monotonic(),
                ),
            )
            if (
                not isinstance(addresses, (tuple, list))
                or not 1 <= len(addresses) <= 64
            ):
                raise _Denied("Invalid DNS result")
            try:
                parsed = [public_address(value) for value in addresses]
            except PublicNetworkError:
                raise _Denied("Non-public destination") from None
            self._check()
            address = str(min(parsed, key=lambda value: (value.version, int(value))))
            remaining = min(
                self.policy.connect_seconds,
                started + self.policy.wall_seconds - time.monotonic(),
            )
            if remaining <= 0:
                raise TimeoutError
            upstream = self.dial(address, 443, remaining, admit)
            if upstream not in owned:
                admit(upstream)
            self._check()
            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            established = True
            outcome = self._pump(
                client, upstream, tail, counts, started + self.policy.wall_seconds
            )
        except _Withdrawn:
            outcome = "withdrawn"
        except _Denied:
            outcome = "denied"
        except TimeoutError:
            outcome = "deadline"
        except Exception:  # noqa: BLE001 — dependencies may contain sensitive diagnostics
            outcome = "withdrawn" if self._withdrawn.is_set() else "io_error"
        finally:
            if not established and not self._withdrawn.is_set():
                try:
                    client.settimeout(0.05)
                    client.sendall(
                        b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\nContent-Length: 0\r\n\r\n"
                    )
                except OSError:
                    pass
            with self._lock:
                self._sockets.difference_update(owned)
            for raw in owned:
                raw.close()
        return TunnelReceipt(outcome, *counts)

    def _pump(self, client, upstream, tail, counts, deadline):
        client.setblocking(False)
        upstream.setblocking(False)
        peers = {client: upstream, upstream: client}
        buffers = {client: bytearray(), upstream: bytearray(tail)}
        reading = set(peers)
        half_closed = set()
        activity = time.monotonic()
        while reading or any(buffers.values()):
            self._check()
            remaining = min(
                deadline - time.monotonic(),
                self.policy.idle_seconds - (time.monotonic() - activity),
            )
            if remaining <= 0:
                return "deadline"
            with self._lock:
                if (
                    sum(counts) >= self.policy.max_bytes
                    or self._bytes >= self.policy.max_total_bytes
                ):
                    return "byte_limit"
            reads = [raw for raw in reading if len(buffers[peers[raw]]) < 65536]
            writes = [raw for raw in peers if buffers[raw]]
            ready, write_ready, _ = select.select(
                reads, writes, [], min(remaining, 0.1)
            )
            for raw in ready:
                try:
                    data = raw.recv(65536 - len(buffers[peers[raw]]))
                except BlockingIOError:
                    continue
                if data:
                    buffers[peers[raw]].extend(data)
                    activity = time.monotonic()
                else:
                    reading.remove(raw)
            for raw in write_ready:
                with self._lock:
                    self._check()
                    budget = min(
                        self.policy.max_bytes - sum(counts),
                        self.policy.max_total_bytes - self._bytes,
                    )
                    if budget <= 0:
                        return "byte_limit"
                    try:
                        amount = raw.send(buffers[raw][:budget])
                    except BlockingIOError:
                        continue
                    counts[0 if raw is upstream else 1] += amount
                    self._bytes += amount
                del buffers[raw][:amount]
                activity = time.monotonic()
            for raw, target in peers.items():
                if (
                    raw not in reading
                    and not buffers[target]
                    and target not in half_closed
                ):
                    target.shutdown(socket.SHUT_WR)
                    half_closed.add(target)
        return "completed"
