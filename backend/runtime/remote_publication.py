"""Exact remote Git publication protocol over trusted owned ports; this module neither grants runtime authority nor starts a host subprocess.

Remote effect uncertainty differs from local process closure: a server may finish
an issued write after its client exits. Only positive original remote evidence
can settle that uncertainty; absent refs are not permission to replay.
"""

import hashlib
import re
from dataclasses import asdict, dataclass
from urllib.parse import urlsplit

from backend.knowledge.reviews import canonical
from backend.runtime.code_review_git import validate_review_candidate
from backend.runtime.contracts import RunConflict, command_key
from backend.runtime.development_workspace import _SHA
from backend.runtime.publication_git import (
    PublicationRefIntent,
    _plain_metadata,
    _PublicationGit,
)

_RECEIPTS = "refs/heads/researcher-receipts/"
_REMOTE_POLICY = (
    "-c",
    "protocol.https.allow=always",
    "-c",
    "http.followRedirects=false",
    "-c",
    "http.sslVerify=true",
    "-c",
    "push.recurseSubmodules=no",
    "-c",
    "push.autoSetupRemote=false",
)


class RemoteEffectUncertain(RunConflict):
    """An issued remote effect may have applied; retain its original identity and observe instead of blindly repeating it."""


@dataclass(frozen=True)
class RemoteRepository:
    """Configured server namespace and numeric repository identity; clone URLs cannot silently redirect credentials to another origin."""

    api_base: str
    repository_id: int
    full_name: str
    clone_url: str

    def __post_init__(self):
        """Require an exact canonical HTTPS origin/path binding and a positive server-side identity, without embedded credentials."""
        try:
            parsed = urlsplit(self.api_base)
            port = parsed.port
        except (TypeError, ValueError) as error:
            raise ValueError("Invalid configured remote server") from error
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or not self.api_base.endswith("/api/v1")
            or parsed.hostname.encode("idna").decode() != parsed.hostname
            or port == 0
            or len(self.api_base) > 2048
        ):
            raise ValueError(
                "Remote publication requires a canonical configured HTTPS API origin"
            )
        if type(self.repository_id) is not int or self.repository_id <= 0:
            raise ValueError("Remote repository requires its positive server identity")
        if (
            not isinstance(self.full_name, str)
            or len(self.full_name) > 240
            or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", self.full_name
            )
            or ".." in self.full_name
        ):
            raise ValueError("Remote repository requires one explicit owner/name")
        if (
            self.clone_url
            != self.api_base[: -len("/api/v1")] + "/" + self.full_name + ".git"
        ):
            raise ValueError(
                "Remote clone URL differs from its exact configured API namespace"
            )


@dataclass(frozen=True)
class RemotePushIntent:
    """Original accepted commit, observed remote target and stable operation identity, distinct from local publication or a moving branch name."""

    operation_key: str
    remote: RemoteRepository
    target_ref: str
    expected_target_sha: str | None
    head_sha: str
    base_sha: str

    def __post_init__(self):
        """Require complete same-format Git identities and forbid adopting an arbitrary remote version as the accepted base."""
        command_key(self.operation_key)
        if not isinstance(self.remote, RemoteRepository):
            raise TypeError("Exact remote repository binding required")
        PublicationRefIntent(
            self.operation_key, self.target_ref, self.expected_target_sha
        )
        if (
            any(
                not isinstance(value, str) or not _SHA.fullmatch(value)
                for value in (self.head_sha, self.base_sha)
            )
            or len(self.head_sha) != len(self.base_sha)
            or self.expected_target_sha not in (None, self.base_sha, self.head_sha)
            or self.target_ref.startswith(_RECEIPTS)
        ):
            raise ValueError(
                "Remote push requires the accepted exact base/head and an explicit separate destination"
            )

    @property
    def query_arguments(self):
        """Build only the exact original target/marker query for the trusted transport profile."""
        return (
            *_REMOTE_POLICY,
            "ls-remote",
            "--refs",
            "--",
            self.remote.clone_url,
            self.target_ref,
            self.receipt_ref,
        )

    @property
    def push_arguments(self):
        """Build the complete one-shot atomic remote ref CAS, without an unconstrained force or another refspec."""
        return (
            *_REMOTE_POLICY,
            "push",
            "--porcelain",
            "--atomic",
            "--no-verify",
            f"--force-with-lease={self.target_ref}:{self.expected_target_sha or ''}",
            f"--force-with-lease={self.receipt_ref}:",
            "--",
            self.remote.clone_url,
            f"{self.head_sha}:{self.target_ref}",
            f"{self.head_sha}:{self.receipt_ref}",
        )

    @property
    def receipt_ref(self):
        """Bind a remote atomic receipt to complete repository identity, candidate and original target observation."""
        return _RECEIPTS + hashlib.sha256(canonical(asdict(self)).encode()).hexdigest()


@dataclass(frozen=True)
class RemotePushObservation:
    """Positive original effect history, separate from whether the remote branch still points at that accepted candidate."""

    state: str
    target_current: bool
    observed_target_sha: str | None
    observed_marker_sha: str | None
    head_sha: str
    receipt_ref: str
    repository_id: int


async def _identity(executor, remote):
    """Require the trusted transport to revalidate original server identity; a URL alone cannot adopt a recreated repository."""
    if await executor.verify_remote(remote) != remote:
        raise RunConflict("Remote repository no longer has its original identity")


async def _refs(git, view, intent):
    """Observe only the two complete remote refs, rejecting partial, duplicate or malformed server output."""
    output = await git.run(view.source.workspace, *intent.query_arguments)
    refs = {}
    for line in output.splitlines():
        sha, separator, name = line.partition(b"\t")
        try:
            sha, name = sha.decode("ascii"), name.decode("ascii")
        except UnicodeError as error:
            raise RunConflict(
                "Remote refs are not complete ASCII Git identities"
            ) from error
        if (
            not separator
            or not _SHA.fullmatch(sha)
            or len(sha) != len(intent.head_sha)
            or name not in (intent.target_ref, intent.receipt_ref)
            or name in refs
        ):
            raise RunConflict("Remote returned ambiguous or malformed ref evidence")
        refs[name] = sha
    return refs.get(intent.target_ref), refs.get(intent.receipt_ref)


def _observed(intent, target, marker):
    """Never turn absent remote evidence into proof that a previously issued write cannot still apply."""
    return RemotePushObservation(
        "published" if marker == intent.head_sha else "uncertain",
        marker == intent.head_sha and target == intent.head_sha,
        target,
        marker,
        intent.head_sha,
        intent.receipt_ref,
        intent.remote.repository_id,
    )


async def push_candidate_remote(view, intent, *, executor, timeout=60):
    """Push exact accepted SHA plus operation receipt atomically with real remote CAS; caller must durably own one original effect before invoking."""
    if not isinstance(intent, RemotePushIntent) or (view.head_sha, view.base_sha) != (
        intent.head_sha,
        intent.base_sha,
    ):
        raise RunConflict("Remote intent differs from the exact accepted candidate")
    _plain_metadata(view.source, view.source_metadata)
    await _identity(executor, intent.remote)
    await validate_review_candidate(view, executor=executor, timeout=timeout)
    git = _PublicationGit(executor, timeout)
    await git.run(
        view.source.workspace,
        "merge-base",
        "--is-ancestor",
        intent.base_sha,
        intent.head_sha,
    )
    target, marker = await _refs(git, view, intent)
    if marker is not None:
        raise RemoteEffectUncertain(
            "Original remote receipt already exists; observe without repeating push"
        )
    if target != intent.expected_target_sha:
        raise RunConflict("Remote destination changed from its original observation")
    try:
        await git.run(view.source.workspace, *intent.push_arguments)
        await _identity(executor, intent.remote)
        target, marker = await _refs(git, view, intent)
        _plain_metadata(view.source, view.source_metadata)
    except Exception as error:
        raise RemoteEffectUncertain(
            "Remote transaction outcome requires original-effect observation"
        ) from error
    result = _observed(intent, target, marker)
    if result.state != "published":
        raise RemoteEffectUncertain("Remote push lacks its original atomic receipt")
    return result


async def reconcile_remote_push(
    view, intent, *, executor, original_client_closed, timeout=30
):
    """Read original remote receipt after local client closure, never infer remote server termination or issue another push."""
    if original_client_closed is not True:
        raise RunConflict("Original local publication client closure must be proved")
    _plain_metadata(view.source, view.source_metadata)
    await _identity(executor, intent.remote)
    git = _PublicationGit(executor, timeout)
    target, marker = await _refs(git, view, intent)
    await _identity(executor, intent.remote)
    _plain_metadata(view.source, view.source_metadata)
    return _observed(intent, target, marker)
