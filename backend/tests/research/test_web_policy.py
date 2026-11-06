"""Exercise robots decisions at the real HTTP reader boundary, without public I/O."""

import pytest
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from backend.research.models import ResearchForbidden, SourceTooLarge, SourceUnavailable
from backend.research.web_fetcher import PublicWebFetcher
from backend.research.web_policy import RobotsRules, WebAccessPolicy
from backend.tests.research.test_web_fetcher import MemoryConnection


def response(body=b"", *, status=200, headers=b""):
    """Encode wire bytes so production header and body parsing remain exercised."""
    return (
        f"HTTP/1.1 {status} Response\r\nContent-Type: text/plain\r\n".encode()
        + f"Content-Length: {len(body)}\r\n".encode()
        + headers
        + b"\r\n"
        + body
    )


class Wire:
    """Supply controlled socket replies and record the requested HTTP resources."""

    def __init__(self, replies):
        """Retain the caller's exact reply sequence for unexpected-I/O detection."""
        self.replies = list(replies)
        self.connections = []

    def connect(self, host, port, address, timeout):
        """Keep real HTTP serialization/parsing while replacing the network socket."""
        conn = MemoryConnection(host, port, address, timeout, self.replies.pop(0))
        self.connections.append(conn)
        return conn

    def fetcher(self, **options):
        """Build the actual source reader with public DNS and controlled wire replies."""
        return PublicWebFetcher(
            resolver=lambda host, timeout: ["93.184.216.34"],
            connection_factory=self.connect,
            **options,
        )

    @property
    def targets(self):
        """Expose requested paths from actual serialized request lines."""
        return [conn.buffer.sent.split(b" ")[1].decode() for conn in self.connections]


def test_default_reader_checks_robots_before_requesting_a_disallowed_page():
    """A missing policy must not turn a denied source into a successful snapshot."""
    wire = Wire([response(b"User-agent: Researcher\nDisallow: /private\n")])
    with pytest.raises(SourceUnavailable, match="robots"):
        wire.fetcher().fetch("https://robots-denial.example.org/private")
    assert wire.targets == ["/robots.txt"]


@pytest.mark.parametrize(("rules", "target", "allowed"), [
    ("User-agent: *\nDisallow: /\nAllow: /public", "/public/article", True),
    ("User-agent: *\nDisallow: /\nAllow: /public", "/private", False),
    ("User-agent: *\nDisallow: /x\nAllow: /x", "/x", True),
    ("User-agent: *\nDisallow: /*.pdf$", "/file.pdf", False),
    ("User-agent: *\nDisallow: /*.pdf$", "/file.pdf?text=1", True),
    ("User-agent: *\nDisallow: /*.pdf$", "/a.pdf/b.pdf", False),
    ("User-agent: *\nDisallow: /private", "/Private", True),
    ("User-agent: *\nDisallow: /café", "/caf%C3%A9", False),
    ("User-agent: *\nDisallow: /%70rivate", "/private", False),
    ("User-agent: *\nDisallow: /a%2Fb", "/a/b", True),
    ("User-agent: *\nDisallow: /x%2Ay", "/x*y", False),
    ("User-agent: *\nDisallow: /x%24", "/x$", False),
    ("User-agent: *\nDisallow: /\nUser-agent: Researcher\nAllow: /public", "/else", True),
    ("User-agent: RESEARCHER\nDisallow: /x\nUser-agent: researcher\nDisallow: /y", "/y", False),
    ("User-agent: *\nDisallow: /\nUser-agent: Researcher\nDisallow:", "/x", True),
    ("Disallow: /\nUser-agent: *\nDisallow: /x # comment\nSitemap: /index\nDisallow: /y", "/y", False),
])
def test_group_selection_path_encoding_and_rule_precedence(rules, target, allowed):
    """Catch first-rule wins, wildcard leaks and confused escaped path identities."""
    assert RobotsRules(rules.encode()).allows(target) is allowed


def test_cache_is_shared_between_readers_but_expires_before_new_policy_decisions():
    """Separate request objects must reuse policy without retaining stale permission."""
    now = [100.0]
    policy = WebAccessPolicy(cache_ttl=10, clock=lambda: now[0])
    rules = b"User-agent: *\nAllow: /\n"
    wire = Wire([
        response(rules), response(b"first"), response(b"second"),
        response(b"User-agent: *\nDisallow: /\n"),
    ])
    first = wire.fetcher(policy=policy, clock=policy.clock).fetch("https://example.org/a")
    second = wire.fetcher(policy=policy, clock=policy.clock).fetch("https://example.org/b")
    assert first.content == "first" and second.content == "second"
    assert first.provenance["access_policy"][0]["cache_hit"] is False
    assert second.provenance["access_policy"][0]["cache_hit"] is True
    assert first.provenance["access_policy"][0]["robots_sha256"] == hashlib.sha256(rules).hexdigest()
    now[0] += 11
    with pytest.raises(SourceUnavailable, match="robots"):
        wire.fetcher(policy=policy, clock=policy.clock).fetch("https://example.org/a")
    assert wire.targets == ["/robots.txt", "/a", "/b", "/robots.txt"]


@pytest.mark.parametrize("status", [429, 500, 503])
def test_robots_server_failure_never_becomes_permission_to_fetch(status):
    """Fail closed when robots cannot be established; do not request the target page."""
    wire = Wire([response(status=status)])
    with pytest.raises(SourceUnavailable, match="robots"):
        wire.fetcher(policy=WebAccessPolicy()).fetch("https://example.org/page")
    assert wire.targets == ["/robots.txt"]


def test_missing_robots_allows_capture_and_each_redirect_checks_the_new_origin():
    """A permitted first origin must not confer permission on a redirected origin."""
    wire = Wire([
        response(status=404),
        response(status=302, headers=b"Location: https://elsewhere.example.org/private\r\n"),
        response(b"User-agent: *\nDisallow: /private\n"),
    ])
    with pytest.raises(SourceUnavailable, match="robots"):
        wire.fetcher(policy=WebAccessPolicy()).fetch("https://example.org/page")
    assert wire.targets == ["/robots.txt", "/page", "/robots.txt"]


def test_robots_redirects_use_original_origin_rules_and_reject_private_destinations():
    """Downloaded rules apply to their requesting authority; redirects cannot bypass SSRF."""
    wire = Wire([
        response(status=302, headers=b"Location: https://cdn.example.org/rules.txt\r\n"),
        response(b"User-agent: *\nDisallow: /private\n"),
    ])
    with pytest.raises(SourceUnavailable, match="robots"):
        wire.fetcher(policy=WebAccessPolicy()).fetch("https://example.org/private")
    assert wire.targets == ["/robots.txt", "/rules.txt"]
    wire = Wire([response(status=302, headers=b"Location: https://127.0.0.1/rules\r\n")])
    with pytest.raises(SourceUnavailable):
        wire.fetcher(policy=WebAccessPolicy()).fetch("https://example.org/page")
    assert wire.targets == ["/robots.txt"]


def test_robots_body_bound_does_not_depend_on_the_smaller_page_limit():
    """Process at least 500 KiB of policy while rejecting oversized policy responses."""
    suffix = b"\nUser-agent: *\nDisallow: /private\n"
    rules = b"#" * (512_000 - len(suffix)) + suffix
    wire = Wire([response(rules)])
    with pytest.raises(SourceUnavailable, match="robots"):
        wire.fetcher(policy=WebAccessPolicy(), max_bytes=20).fetch("https://example.org/private")
    wire = Wire([response(b"#" * 512_001)])
    with pytest.raises(SourceTooLarge):
        wire.fetcher(policy=WebAccessPolicy()).fetch("https://example.org/page")


def test_shared_rate_budget_counts_robots_and_prevents_a_second_reader_request():
    """A newly composed fetcher must not reset the host's HTTP request budget."""
    policy = WebAccessPolicy(requests_per_minute=2)
    wire = Wire([response(status=404), response(b"evidence")])
    assert wire.fetcher(policy=policy).fetch("https://example.org/page").content == "evidence"
    with pytest.raises(SourceUnavailable, match="frequency"):
        wire.fetcher(policy=policy).fetch("https://example.org/page2")
    assert wire.targets == ["/robots.txt", "/page"]


def test_stop_interrupts_a_rate_wait_and_the_budget_recovers_after_its_window():
    """Waiting for a rate slot must not hold cancelled work or retain expired starts."""
    from backend.runtime.live_grants import LiveGrants

    policy = WebAccessPolicy(requests_per_minute=1)
    policy.acquire(time.monotonic() + 120, Event())
    gate = LiveGrants()
    gate.activate("capture")
    waiting = Event()

    class ObservedCancellation:
        """Signal entry into the actual wait while preserving the grant's Stop event."""

        def __init__(self, cancelled):
            """Retain the event issued by the production operation owner."""
            self.cancelled = cancelled

        def is_set(self):
            """Return the original owner's cancellation state."""
            return self.cancelled.is_set()

        def wait(self, timeout):
            """Expose the wait boundary without replacing its cancellation behavior."""
            waiting.set()
            return self.cancelled.wait(timeout)

    original_acquire = policy.acquire

    def observed_acquire(deadline, cancelled):
        """Wrap only wait observation, retaining the real policy's frequency decisions."""
        return original_acquire(deadline, ObservedCancellation(cancelled))

    policy.acquire = observed_acquire
    wire = Wire([])
    web = wire.fetcher(policy=policy, timeout_seconds=120, owner=gate, grant_id="capture")
    with ThreadPoolExecutor() as executor:
        pending = executor.submit(web.fetch, "https://example.org/page")
        assert waiting.wait(1)
        gate.withdraw("capture")
        with pytest.raises(ResearchForbidden):
            pending.result(timeout=1)
    gate.wait_closed("capture", timeout=0.1)
    assert wire.targets == []
    now = [0.0]
    policy = WebAccessPolicy(requests_per_minute=1, clock=lambda: now[0])
    policy.acquire(10, Event())
    now[0] = 61
    policy.acquire(70, Event())
