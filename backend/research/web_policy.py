"""Host-owned robots rules and a shared, cancellable HTTP request budget.

The policy covers direct public source acquisition. Provider APIs and remote
browser subrequests are separate boundaries; this module cannot police them.
"""

import hashlib
import re
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from threading import Lock
from urllib.parse import quote, urlsplit

from backend.research.models import ResearchForbidden, SourceUnavailable

USER_AGENT = "Researcher/0.1 source-reader"
PRODUCT_TOKEN = "researcher"
MAX_ROBOTS_BYTES = 512_000
_UNRESERVED = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
)


def _normalized(value, *, pattern=False):
    """Compare UTF-8/percent escapes without confusing encoded path separators."""
    value = quote(value, safe="/%?:@!&'()+,;=-._~" + ("*$" if pattern else ""))

    def escape(match):
        """Decode only unreserved ASCII; retain canonical encoded octets otherwise."""
        char = chr(int(match[0][1:], 16))
        return char if char in _UNRESERVED else match[0].upper()

    return re.sub(r"%[0-9a-fA-F]{2}", escape, value)


def _matches(pattern, target):
    """Match anchored glob segments without an attacker-controlled regular expression."""
    exact = pattern.endswith("$")
    if exact:
        pattern = pattern[:-1]
    parts = pattern.split("*")
    if not target.startswith(parts[0]):
        return False
    position = len(parts[0])
    if len(parts) == 1:
        return not exact or position == len(target)
    for index, part in enumerate(parts[1:], 1):
        if exact and index == len(parts) - 1:
            return target.endswith(part) and len(target) - len(part) >= position
        position = target.find(part, position)
        if position < 0:
            return False
        position += len(part)
    return True


class RobotsRules:
    """Parse relevant groups and choose the longest matching allow/disallow rule."""

    def __init__(self, body):
        """Merge exact product groups, falling back to wildcard groups only if absent."""
        groups = []
        agents, rules = [], []
        for line in body.decode("utf-8-sig", errors="replace").splitlines():
            line = line.split("#", 1)[0].strip()
            if ":" not in line or "\ufffd" in line:
                continue
            key, value = (part.strip() for part in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if rules:
                    groups.append((agents, rules))
                    agents, rules = [], []
                if value == "*" or re.fullmatch(r"[a-zA-Z_-]+", value):
                    agents.append(value.lower())
            elif key in ("allow", "disallow") and agents:
                # Empty directives still end the group's user-agent header.
                rules.append((value, key == "allow"))
        groups.append((agents, rules))
        product = (
            PRODUCT_TOKEN
            if any(PRODUCT_TOKEN in names for names, _ in groups)
            else "*"
        )
        self.rules = tuple(
            (_normalized(path, pattern=True), allowed)
            for names, entries in groups
            if product in names
            for path, allowed in entries
            if path and path.startswith(("/", "*"))
        )

    def allows(self, target):
        """Use case-sensitive paths and allow on equally specific matching rules."""
        target = _normalized(target)
        matches = (
            (len(pattern), allowed)
            for pattern, allowed in self.rules
            if _matches(pattern, target)
        )
        return max(matches, default=(0, True))[1]


@dataclass(frozen=True)
class _CachedRules:
    """Retain immutable rules and acquisition evidence within a bounded TTL cache."""

    rules: RobotsRules
    received_at: float
    byte_count: int
    digest: str
    url: str
    status: int


class WebAccessPolicy:
    """Share robots decisions and HTTP starts across readers in one host instance."""

    def __init__(
        self, *, requests_per_minute=20, cache_ttl=3600, clock=time.monotonic
    ):
        """Configure bounded host policy; this is not a model-selectable bypass."""
        if not 1 <= requests_per_minute <= 10_000 or not 0 < cache_ttl <= 86_400:
            raise ValueError("Invalid web rate or robots cache limits")
        self.requests_per_minute = requests_per_minute
        self.cache_ttl = cache_ttl
        self.clock = clock
        self._lock = Lock()
        self._starts = deque()
        self._cache = OrderedDict()
        self._cache_bytes = 0

    def _remaining(self, deadline, cancelled):
        """Keep policy work inside the original request deadline and Stop authority."""
        if cancelled.is_set():
            raise ResearchForbidden("Web source authority was withdrawn")
        remaining = deadline - self.clock()
        if remaining <= 0:
            raise SourceUnavailable("Public source acquisition exceeded its deadline")
        return remaining

    def acquire(self, deadline, cancelled):
        """Reserve one HTTP start, waiting outside the lock only within its deadline."""
        while True:
            remaining = self._remaining(deadline, cancelled)
            with self._lock:
                now = self.clock()
                while self._starts and self._starts[0] <= now - 60:
                    self._starts.popleft()
                if len(self._starts) < self.requests_per_minute:
                    self._starts.append(now)
                    return
                delay = self._starts[0] + 60 - now
            if delay >= remaining:
                raise SourceUnavailable(
                    "Web request frequency limit cannot clear before the acquisition deadline"
                )
            cancelled.wait(delay)

    def authorize(self, url, load_robots, deadline, cancelled):
        """Check an already validated URL before its page request and return evidence."""
        self._remaining(deadline, cancelled)
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        target = parts.path + ("?" + parts.query if parts.query else "")
        if parts.path == "/robots.txt":
            return {"decision": "robots-file", "user_agent": USER_AGENT}
        with self._lock:
            entry = self._cache.get(origin)
            cached = entry is not None and self.clock() - entry.received_at < self.cache_ttl
        if not cached:
            status, body, robots_url = load_robots(origin + "/robots.txt")
            self._remaining(deadline, cancelled)
            if status == 429 or not 200 <= status < 500:
                raise SourceUnavailable(f"robots.txt policy unavailable: HTTP {status}")
            if 400 <= status < 500:
                body = b""
            if len(body) > MAX_ROBOTS_BYTES:
                raise SourceUnavailable("robots.txt exceeds the bounded policy size")
            entry = _CachedRules(
                RobotsRules(body), self.clock(), len(body), hashlib.sha256(body).hexdigest(),
                robots_url, status,
            )
            with self._lock:
                previous = self._cache.pop(origin, None)
                if previous is not None:
                    self._cache_bytes -= previous.byte_count
                self._cache[origin] = entry
                self._cache_bytes += entry.byte_count
                while len(self._cache) > 64 or self._cache_bytes > 4 * 1024 * 1024:
                    _, old = self._cache.popitem(last=False)
                    self._cache_bytes -= old.byte_count
        self._remaining(deadline, cancelled)
        if not entry.rules.allows(target):
            raise SourceUnavailable("robots.txt disallows this source for Researcher")
        return {
            "decision": "allowed", "user_agent": USER_AGENT,
            "robots_url": entry.url, "robots_status": entry.status,
            "robots_sha256": entry.digest, "robots_bytes": entry.byte_count,
            "cache_hit": cached, "requests_per_minute": self.requests_per_minute,
            "rate_scope": "policy-instance",
        }


DEFAULT_WEB_POLICY = WebAccessPolicy()
