"""Exact branch publication and atomic Git receipts through a fresh host-owned executor.

This policy never grants effect authority or launches a host subprocess. Its
controller must persist the owner intent, validate current acceptance and own a
new physical execution domain before calling it. Broker integration and durable
publication admission are separate responsibilities. Remote push/PR is separate.
"""

import hashlib
import re
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from backend.runtime.code_review_git import validate_review_candidate
from backend.runtime.contracts import RunConflict, WorkspaceBinding, command_key, text
from backend.runtime.development_workspace import (
    _POLICY,
    _SHA,
    MAX_OUTPUT_BYTES,
    GitExecutor,
    GitResult,
    _source_identity,
    git_environment,
)


class PublicationUncertain(RunConflict):
    """A ref transaction may have committed; prove original process closure and inspect its marker before any further effect."""


class PublicationGitExecutor(GitExecutor, Protocol):
    """Trusted port whose original broker manifest must bind the complete immutable transaction input and its fresh authority."""

    async def transact(self, command, *, cwd, env, timeout, input_text) -> GitResult:
        """Write bounded fixed Git transaction input, collect complete output and prove original physical execution closure."""
        ...


@dataclass(frozen=True)
class PublicationDirectory:
    """Original Git metadata identity that must be persisted by admission and pinned by the physical executor."""

    path: str
    device: int
    inode: int

    @classmethod
    def capture(cls, path):
        """Capture an actual ordinary directory without adopting a symlink or a redirected path."""
        path = Path(path).absolute()
        try:
            info = path.lstat()
            if path.resolve(strict=True) != path or not stat.S_ISDIR(info.st_mode):
                raise RunConflict(
                    "Publication requires ordinary non-redirected Git metadata"
                )
        except OSError as error:
            raise RunConflict("Publication Git metadata is unavailable") from error
        return cls(str(path), info.st_dev, info.st_ino)


@dataclass(frozen=True)
class PublicationView:
    """Original registration, exact captured candidate and pinned metadata; this data is not acceptance or effect authority."""

    source: WorkspaceBinding
    workspace: str
    device: int
    inode: int
    head_sha: str
    tree_sha: str
    subject_sha256: str
    base_sha: str
    diff_sha256: str
    source_metadata: PublicationDirectory
    candidate_metadata: PublicationDirectory

    def __post_init__(self):
        """Require full same-format Git identities, complete evidence hashes and metadata belonging to these exact views before any command construction."""
        if not isinstance(self.source, WorkspaceBinding):
            raise TypeError("Publication requires an original registered source")
        text(self.workspace, "Publication candidate path", 4096)
        if (
            any(
                not isinstance(value, str) or not _SHA.fullmatch(value)
                for value in (self.base_sha, self.head_sha, self.tree_sha)
            )
            or len({len(self.base_sha), len(self.head_sha), len(self.tree_sha)}) != 1
        ):
            raise ValueError("Publication requires complete same-format Git identities")
        if any(
            not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value)
            for value in (self.diff_sha256, self.subject_sha256)
        ):
            raise ValueError(
                "Publication requires complete candidate/evidence fingerprints"
            )
        for binding, metadata in (
            (self.source, self.source_metadata),
            (self, self.candidate_metadata),
        ):
            if not isinstance(metadata, PublicationDirectory) or metadata.path != str(
                Path(binding.workspace) / ".git"
            ):
                raise ValueError(
                    "Publication metadata must belong to its exact source/candidate"
                )


@dataclass(frozen=True)
class PublicationRefIntent:
    """An original host publication identity and explicitly observed branch; absent is distinct from an unknown destination."""

    publication_id: str
    target_ref: str
    expected_target_sha: str | None

    def __post_init__(self):
        """Forbid ambiguous refs and transaction injection before constructing any Git arguments."""
        command_key(self.publication_id)
        ref = self.target_ref
        if (
            not isinstance(ref, str)
            or len(ref) > 240
            or not re.fullmatch(r"refs/heads/[A-Za-z0-9][A-Za-z0-9._/-]*", ref)
            or ".." in ref
            or ref.endswith(("/", "."))
            or any(
                not part or part.startswith(".") or part.endswith(".lock")
                for part in ref.split("/")
            )
        ):
            raise ValueError("Publication requires an explicit unambiguous branch ref")
        if self.expected_target_sha is not None and (
            not isinstance(self.expected_target_sha, str)
            or not _SHA.fullmatch(self.expected_target_sha)
        ):
            raise ValueError(
                "Publication requires a complete observed target SHA or explicit absence"
            )

    @property
    def receipt_ref(self):
        """Bind the marker namespace to the complete original destination observation as well as its host operation identity."""
        return (
            "refs/researcher/publications/"
            + hashlib.sha256(
                (
                    self.publication_id
                    + "\0"
                    + self.target_ref
                    + "\0"
                    + (self.expected_target_sha or "")
                ).encode("ascii")
            ).hexdigest()
        )


@dataclass(frozen=True)
class PublicationRefObservation:
    """Historical effect evidence with destination currentness separated from whether this request actually published."""

    state: str
    target_current: bool
    observed_target_sha: str | None
    observed_marker_sha: str | None
    head_sha: str
    receipt_ref: str


def _plain_metadata(binding, expected):
    """Reject redirected/shared metadata before a publication port can expose source Git state in writing."""
    source = _source_identity(binding)
    metadata = source / ".git"
    if (
        not isinstance(expected, PublicationDirectory)
        or PublicationDirectory.capture(metadata) != expected
    ):
        raise RunConflict(
            "Publication Git metadata no longer matches its original identity"
        )
    if any(
        (metadata / name).exists()
        for name in (
            "commondir",
            "objects/info/alternates",
            "objects/info/http-alternates",
        )
    ):
        raise RunConflict("Publication requires independent Git metadata")
    return metadata


class _PublicationGit:
    """Bound all reads and the one explicit transaction to a single finite policy deadline and trusted executor."""

    def __init__(self, executor, timeout):
        """Retain the fresh host port without acquiring authority or changing its original lifetime."""
        if type(timeout) not in (int, float) or not 0 < timeout <= 300:
            raise ValueError(
                "Publication requires a finite deadline of at most300seconds"
            )
        self.executor = executor
        self.deadline = time.monotonic() + timeout

    async def run(self, cwd, *arguments, input_text=None):
        """Require complete bounded output and actual closure; a transport failure is never an empty successful read."""
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise RunConflict("Publication Git deadline expired")
        command = (
            str(self.executor.git_binary),
            *_POLICY,
            "-c",
            "uploadpack.packObjectsHook=",
            "-c",
            "transfer.fsckObjects=true",
            *arguments,
        )
        kwargs = {
            "cwd": self.executor.execution_path(Path(cwd)),
            "env": git_environment(Path("/home/actor")),
            "timeout": remaining,
        }
        result = (
            await self.executor.run(command, **kwargs)
            if input_text is None
            else await self.executor.transact(command, input_text=input_text, **kwargs)
        )
        if (
            not isinstance(result, GitResult)
            or not result.local_execution_closed
            or not result.output_complete
            or not isinstance(result.stdout, bytes)
            or len(result.stdout) > MAX_OUTPUT_BYTES
        ):
            raise RunConflict(
                "Publication Git output or physical closure is unconfirmed"
            )
        if result.exit_code != 0:
            raise RunConflict(
                "Publication Git command failed; inspect its original receipt"
            )
        return result.stdout

    async def ref(self, root, name):
        """Read an exact full ref, ignoring longer prefix matches instead of adopting a similarly named branch."""
        output = await self.run(
            root,
            "for-each-ref",
            "--count=2",
            "--format=%(refname)%00%(objectname)",
            name,
        )
        for line in output.splitlines():
            ref, separator, sha = line.partition(b"\0")
            if not separator or not _SHA.fullmatch(sha.decode("ascii")):
                raise RunConflict("Git returned an incomplete ref observation")
            if ref == name.encode("ascii"):
                return sha.decode("ascii")
        return None


def _observation(view, intent, target, marker):
    """Keep an applied request historical if another actor subsequently moves its branch."""
    return PublicationRefObservation(
        "published"
        if marker == view.head_sha
        else "not_applied"
        if marker is None and target == intent.expected_target_sha
        else "uncertain",
        marker == view.head_sha and target == view.head_sha,
        target,
        marker,
        view.head_sha,
        intent.receipt_ref,
    )


async def reconcile_candidate_ref(
    view, intent, *, executor, original_execution_closed, timeout=30
):
    """Observe original atomic effect history only after independently proven original closure; never issue a replacement transaction."""
    if original_execution_closed is not True:
        raise ValueError(
            "Original publication execution closure must be proved before reconciliation"
        )
    _plain_metadata(view.source, view.source_metadata)
    git = _PublicationGit(executor, timeout)
    target = await git.ref(view.source.workspace, intent.target_ref)
    marker = await git.ref(view.source.workspace, intent.receipt_ref)
    _source_identity(view.source)
    _plain_metadata(view.source, view.source_metadata)
    return _observation(view, intent, target, marker)


async def publish_candidate_ref(view, intent, *, executor, timeout=60):
    """Publish one exact candidate to a non-checked-out observed branch with one atomic branch/marker CAS; caller owns durable intent and fresh effect authority."""
    _plain_metadata(view.source, view.source_metadata)
    _plain_metadata(view, view.candidate_metadata)
    if intent.expected_target_sha not in (None, view.base_sha, view.head_sha):
        raise RunConflict(
            "Publication destination is not the accepted base or candidate"
        )
    git = _PublicationGit(executor, timeout)
    await validate_review_candidate(view, executor=executor, timeout=timeout)
    root = view.source.workspace
    target = await git.ref(root, intent.target_ref)
    marker = await git.ref(root, intent.receipt_ref)
    if marker is not None:
        raise PublicationUncertain(
            "Publication marker already exists; reconcile the original effect without replay"
        )
    if target != intent.expected_target_sha:
        raise RunConflict("Publication destination differs from the observed version")
    worktrees = await git.run(root, "worktree", "list", "--porcelain", "-z")
    if b"branch " + intent.target_ref.encode("ascii") in worktrees.split(b"\0"):
        raise RunConflict(
            "Publication destination is checked out; choose an explicit separate branch"
        )
    candidate_path = str(executor.execution_path(Path(view.workspace)))
    await git.run(
        root,
        "fetch",
        "--no-tags",
        "--no-prune",
        "--no-prune-tags",
        "--no-write-fetch-head",
        "--no-auto-maintenance",
        "--refmap=",
        "--",
        candidate_path,
        view.head_sha,
    )
    _source_identity(view.source)
    _source_identity(view)
    _plain_metadata(view.source, view.source_metadata)
    _plain_metadata(view, view.candidate_metadata)
    update = (
        f"create {intent.target_ref} {view.head_sha}"
        if intent.expected_target_sha is None
        else f"update {intent.target_ref} {view.head_sha} {intent.expected_target_sha}"
    )
    transaction = f"start\n{update}\ncreate {intent.receipt_ref} {view.head_sha}\nprepare\ncommit\n"
    try:
        await git.run(root, "update-ref", "--stdin", input_text=transaction)
        target = await git.ref(root, intent.target_ref)
        marker = await git.ref(root, intent.receipt_ref)
        _source_identity(view.source)
        _plain_metadata(view.source, view.source_metadata)
    except Exception as error:
        raise PublicationUncertain(
            "Publication transaction outcome is unknown; close and reconcile its original effect"
        ) from error
    observed = _observation(view, intent, target, marker)
    if observed.state != "published":
        raise PublicationUncertain(
            "Git transaction lacks its original atomic receipt; reconcile without replay"
        )
    return observed
