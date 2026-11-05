"""Bounded Forgejo publication transport with original-intent PR receipts and explicit remote uncertainty.

This trusted host port is not runtime effect authority. The owner controller must
persist intent before the first POST and own its transport lifetime. It must not
call creation again to retry an unknown write; reconciliation is readonly.
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from urllib.parse import quote

import httpx

from backend.knowledge.reviews import canonical
from backend.runtime.contracts import RunConflict, command_key, text
from backend.runtime.publication_git import PublicationRefIntent
from backend.runtime.remote_publication import (
    RemoteEffectUncertain,
    RemotePushIntent,
    RemotePushObservation,
    RemoteRepository,
)


class RemoteAPIError(RunConflict):
    """A bounded remote read failed without exposing response bodies, credentials or connection details."""


@dataclass(frozen=True)
class RemotePullIntent:
    """Original owner PR request and exact head/base observations, bound to one numeric remote repository identity."""

    operation_key: str
    remote: RemoteRepository
    head_ref: str
    base_ref: str
    head_sha: str
    base_sha: str
    title: str
    body: str

    def __post_init__(self):
        """Require explicit same-repository branch refs, complete Git observations and bounded original prose before any HTTP effect."""
        command_key(self.operation_key)
        RemotePushIntent(
            self.operation_key,
            self.remote,
            self.head_ref,
            None,
            self.head_sha,
            self.base_sha,
        )
        PublicationRefIntent(self.operation_key, self.base_ref, self.base_sha)
        if self.head_ref == self.base_ref:
            raise ValueError("Pull request requires separate head and base branches")
        text(self.title, "Pull request title", 256)
        text(self.body, "Pull request body", 12000)
        if (
            any(c in self.title for c in "\r\n")
            or "<!-- researcher-publication:" in self.body
        ):
            raise ValueError(
                "Pull request text contains ambiguous receipt or title framing"
            )

    @property
    def marker(self):
        """Tie the server-visible receipt to full original repository, refs, candidate and prose, not only a reusable label."""
        return (
            "<!-- researcher-publication:"
            + hashlib.sha256(canonical(asdict(self)).encode()).hexdigest()
            + " -->"
        )

    @property
    def marked_body(self):
        """Append one stable receipt without hiding or rewriting the owner's original PR description."""
        return self.body + "\n\n" + self.marker


@dataclass(frozen=True)
class RemotePullObservation:
    """Original creation evidence and current candidate/base observations; existence is distinct from exact-version eligibility."""

    state: str
    number: int | None
    candidate_current: bool
    observed_head_sha: str | None
    observed_base_sha: str | None
    marker: str
    repository_id: int


@dataclass(frozen=True)
class RemoteMergeObservation:
    """Server PR bookkeeping for a separately proved exact Git target update; current destination and historical merge remain distinct."""

    state: str
    number: int
    merge_sha: str | None
    target_current: bool
    receipt_ref: str
    repository_id: int


class ForgejoPublicationClient:
    """Own a finite async HTTP transport with fixed credential origin, no redirects, environment proxy or blind retries."""

    def __init__(self, api_base, token, *, transport=None):
        """Keep credentials only in the trusted HTTP client, never URLs, process arguments, receipts or model-visible manifests."""
        if (
            not isinstance(token, str)
            or not token
            or len(token) > 4096
            or any(c in token for c in "\r\n\0")
        ):
            raise ValueError("Configured Forgejo credential is unavailable")
        RemoteRepository(
            api_base,
            1,
            "validation/repository",
            api_base[: -len("/api/v1")] + "/validation/repository.git",
        )
        self.api_base = api_base
        self._headers = {
            "Authorization": "token " + token,
            "Accept": "application/json",
            "Accept-Encoding": "identity",
        }
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(20, connect=5),
            trust_env=False,
            follow_redirects=False,
            transport=transport,
        )

    async def __aenter__(self):
        """Make host ownership of the finite HTTP client explicit before starting remote work."""
        return self

    async def __aexit__(self, *_exc):
        """Close local transport without treating that closure as proof that the remote server stopped its operation."""
        await self._client.aclose()

    def _path(self, remote, suffix=""):
        """Bind every request, including its credential, to the exact configured server and canonical repository namespace."""
        if not isinstance(remote, RemoteRepository) or remote.api_base != self.api_base:
            raise RunConflict(
                "Remote repository differs from configured credential origin"
            )
        return self.api_base + "/repos/" + remote.full_name + suffix

    async def _request(self, method, url, *, payload=None, missing=False, empty=False):
        """Read complete bounded uncompressed JSON, suppress raw errors and classify all uncertain remote writes conservatively."""
        try:
            async with self._client.stream(
                method, url, headers=self._headers, json=payload, follow_redirects=False
            ) as response:
                if missing and response.status_code == 404:
                    return None
                if not 200 <= response.status_code < 300:
                    raise RemoteAPIError("Forgejo returned an unsuccessful HTTP status")
                if response.headers.get("content-encoding", "identity").lower() not in (
                    "",
                    "identity",
                ):
                    raise RemoteAPIError(
                        "Forgejo response encoding is outside the bounded JSON contract"
                    )
                data = bytearray()
                async for block in response.aiter_bytes(chunk_size=65536):
                    data.extend(block)
                    if len(data) > 1024 * 1024:
                        raise RemoteAPIError(
                            "Forgejo response exceeded its complete JSON budget"
                        )
                if not data and empty:
                    return {}
                return json.loads(data)
        except (httpx.HTTPError, ValueError, RemoteAPIError) as error:
            if method != "GET":
                raise RemoteEffectUncertain(
                    "Forgejo write outcome requires original-effect observation"
                ) from None
            if isinstance(error, RemoteAPIError):
                raise
            raise RemoteAPIError("Forgejo read could not be completed") from None

    async def verify_remote(self, remote):
        """Require the same numeric server repository and canonical clone URL; a recreated same-name repository cannot inherit its receipt."""
        record = await self._request("GET", self._path(remote))
        if not isinstance(record, dict) or (
            record.get("id"),
            record.get("full_name"),
            record.get("clone_url"),
        ) != (remote.repository_id, remote.full_name, remote.clone_url):
            raise RunConflict(
                "Remote repository identity differs from the original owner observation"
            )
        return remote

    @staticmethod
    def _pull(intent, record):
        """Validate original PR namespace/receipt while preserving changed head/base as historical, ineligible evidence."""
        try:
            head, base = record["head"], record["base"]
            number = record["number"]
            if (
                type(number) is not int
                or number <= 0
                or record["body"] != intent.marked_body
                or head["ref"] != intent.head_ref[len("refs/heads/") :]
                or base["ref"] != intent.base_ref[len("refs/heads/") :]
                or head["repo"]["id"] != intent.remote.repository_id
                or base["repo"]["id"] != intent.remote.repository_id
            ):
                raise ValueError
            RemotePushIntent(
                intent.operation_key,
                intent.remote,
                intent.head_ref,
                None,
                head["sha"],
                base["sha"],
            )
        except (TypeError, KeyError, ValueError) as error:
            raise RunConflict(
                "Remote PR receipt differs from its original repository or branch intent"
            ) from error
        return RemotePullObservation(
            "created",
            number,
            (head["sha"], base["sha"]) == (intent.head_sha, intent.base_sha),
            head["sha"],
            base["sha"],
            intent.marker,
            intent.remote.repository_id,
        )

    async def _find_pull(self, intent):
        """Scan bounded complete pages, rejecting ambiguous receipts and never treating a truncated search as absence."""
        found = []
        for page in range(1, 11):
            records = await self._request(
                "GET",
                self._path(intent.remote, f"/pulls?state=all&limit=50&page={page}"),
            )
            if not isinstance(records, list) or len(records) > 50:
                raise RemoteAPIError("Forgejo PR page is outside its bounded contract")
            for record in records:
                if not isinstance(record, dict):
                    raise RemoteAPIError("Forgejo PR page contains an invalid record")
                if intent.marker in (record.get("body") or ""):
                    found.append(self._pull(intent, record))
            if len(found) > 1:
                raise RunConflict(
                    "Several remote PRs claim the same original publication receipt"
                )
            if len(records) < 50:
                return found[0] if found else None
        raise RemoteAPIError(
            "PR search budget ended before complete original receipt observation"
        )

    async def _branch(self, intent, ref):
        """Read one explicitly encoded branch without allowing a slash, query or ref suffix to change the API route."""
        record = await self._request(
            "GET",
            self._path(
                intent.remote, "/branches/" + quote(ref[len("refs/heads/") :], safe="")
            ),
        )
        try:
            sha = record["commit"]["id"]
        except (TypeError, KeyError) as error:
            raise RemoteAPIError(
                "Forgejo branch response lacks a complete commit observation"
            ) from error
        return sha

    async def create_pull(self, intent):
        """Create once after durable owner effect reservation; an existing exact receipt is returned, while unknown writes require readonly reconciliation."""
        if not isinstance(intent, RemotePullIntent):
            raise TypeError("Typed original PR intent required")
        await self.verify_remote(intent.remote)
        existing = await self._find_pull(intent)
        if existing is not None:
            return existing
        if (
            await self._branch(intent, intent.head_ref),
            await self._branch(intent, intent.base_ref),
        ) != (intent.head_sha, intent.base_sha):
            raise RunConflict(
                "Remote candidate or base differs from the exact owner observation"
            )
        record = await self._request(
            "POST",
            self._path(intent.remote, "/pulls"),
            payload={
                "head": intent.head_ref[len("refs/heads/") :],
                "base": intent.base_ref[len("refs/heads/") :],
                "title": intent.title,
                "body": intent.marked_body,
            },
        )
        try:
            await self.verify_remote(intent.remote)
            return self._pull(intent, record)
        except (RunConflict, RemoteAPIError) as error:
            raise RemoteEffectUncertain(
                "Created PR requires original receipt and repository reconciliation"
            ) from error

    async def reconcile_pull(self, intent, *, original_client_closed):
        """Inspect only original PR evidence after local transport closure; a missing object remains uncertain and never triggers another POST."""
        if original_client_closed is not True:
            raise RunConflict("Original local HTTP client closure must be proved")
        await self.verify_remote(intent.remote)
        found = await self._find_pull(intent)
        await self.verify_remote(intent.remote)
        return found or RemotePullObservation(
            "uncertain",
            None,
            False,
            None,
            None,
            intent.marker,
            intent.remote.repository_id,
        )

    @staticmethod
    def _merge_proof(intent, number, target, proof, *, require_current):
        """Require the exact original atomic base-to-candidate ref receipt, never merely a PR status or a matching branch."""
        if (
            not isinstance(intent, RemotePullIntent)
            or type(number) is not int
            or number <= 0
            or not isinstance(target, RemotePushIntent)
            or not isinstance(proof, RemotePushObservation)
            or target.remote != intent.remote
            or target.target_ref != intent.base_ref
            or target.expected_target_sha != intent.base_sha
            or (target.head_sha, target.base_sha) != (intent.head_sha, intent.base_sha)
            or proof.state != "published"
            or proof.head_sha != intent.head_sha
            or proof.observed_marker_sha != intent.head_sha
            or proof.receipt_ref != target.receipt_ref
            or proof.repository_id != intent.remote.repository_id
            or (require_current and not proof.target_current)
        ):
            raise RunConflict(
                "Exact original Git merge CAS receipt is required before Forgejo bookkeeping"
            )

    @staticmethod
    def _merged(intent, number, target, proof, record):
        """Retain only an exact same-candidate merge record; another merge commit cannot inherit the original accepted version."""
        ForgejoPublicationClient._pull(intent, record)
        merged = record.get("merged") is True
        sha = record.get("merge_commit_sha")
        if merged and sha != intent.head_sha:
            raise RunConflict(
                "Remote PR reports a different merge commit than the original exact target update"
            )
        return RemoteMergeObservation(
            "merged" if merged else "uncertain",
            number,
            sha if merged else None,
            proof.target_current,
            target.receipt_ref,
            intent.remote.repository_id,
        )

    async def record_exact_merge(self, intent, number, target, proof):
        """Record an already-proven exact Git fast-forward via Forgejo manually-merged, without asking its head-only merge API to update a moving base."""
        self._merge_proof(intent, number, target, proof, require_current=True)
        await self.verify_remote(intent.remote)
        url = self._path(intent.remote, f"/pulls/{number}")
        record = await self._request("GET", url)
        observed = self._merged(intent, number, target, proof, record)
        if observed.state == "merged":
            return observed
        if (
            record["head"]["sha"] != intent.head_sha
            or await self._branch(intent, intent.base_ref) != intent.head_sha
        ):
            raise RunConflict(
                "Original PR head or applied Git merge destination changed before bookkeeping"
            )
        await self._request(
            "POST",
            url + "/merge",
            payload={
                "Do": "manually-merged",
                "MergeCommitID": intent.head_sha,
                "head_commit_id": intent.head_sha,
                "force_merge": False,
                "delete_branch_after_merge": False,
                "merge_when_checks_succeed": False,
            },
            empty=True,
        )
        try:
            await self.verify_remote(intent.remote)
            result = self._merged(
                intent, number, target, proof, await self._request("GET", url)
            )
            if result.state != "merged":
                raise RemoteEffectUncertain(
                    "Original exact merge bookkeeping is not confirmed"
                )
            return result
        except (RunConflict, RemoteAPIError) as error:
            raise RemoteEffectUncertain(
                "Original Git effect and merge bookkeeping require separate reconciliation"
            ) from error

    async def reconcile_exact_merge(
        self, intent, number, target, proof, *, original_client_closed
    ):
        """Observe original same-SHA merge bookkeeping only; neither the Git CAS nor the Forgejo POST is replayed."""
        if original_client_closed is not True:
            raise RunConflict("Original local merge client closure must be proved")
        self._merge_proof(intent, number, target, proof, require_current=False)
        await self.verify_remote(intent.remote)
        record = await self._request(
            "GET", self._path(intent.remote, f"/pulls/{number}")
        )
        result = self._merged(intent, number, target, proof, record)
        await self.verify_remote(intent.remote)
        return result
