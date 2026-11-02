"""Validate actual readonly candidate Git bytes through the original owned Git port.

These observations do not accept work or prove reviewer understanding. The host
must bind their original operation receipts to the review's fenced attempt.
"""

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path

from backend.runtime.check_workspace import _git
from backend.runtime.contracts import RunConflict
from backend.runtime.development_workspace import _source_identity


@dataclass(frozen=True)
class ReviewGitWitness:
    """Complete observed base/head/tree/diff identity after a clean readonly working-copy check."""

    base_sha: str
    head_sha: str
    tree_sha: str
    diff_sha256: str


async def validate_review_candidate(candidate, *, executor, timeout=30):
    """Require exact Git/diff and unchanged code, allowing only untracked reserved root Ken state within one finite budget."""
    if type(timeout) not in (int, float) or not 0 < timeout <= 300:
        raise ValueError("Review Git validation requires a bounded deadline")
    _source_identity(candidate)
    root = Path(candidate.workspace)
    deadline = time.monotonic() + timeout

    async def git(*arguments):
        """Retain credential-free Git policy, complete bounded output and original physical closure on every query."""
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RunConflict("Review Git validation deadline expired")
        return await _git(executor, root, *arguments, timeout=remaining)

    head = (await git("rev-parse", "--verify", "HEAD^{commit}")).decode("ascii").strip()
    tree = (await git("rev-parse", "--verify", "HEAD^{tree}")).decode("ascii").strip()
    if (head, tree) != (candidate.head_sha, candidate.tree_sha):
        raise RunConflict("Review candidate Git version changed")
    diff = await git(
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--binary",
        "--full-index",
        "--no-color",
        "--no-renames",
        candidate.base_sha,
        head,
        "--",
    )
    sha = hashlib.sha256(diff).hexdigest()
    # Capture already reserves root .ken outside source. Published Ken creates
    # that index during review; retain its evidence without treating it as code.
    # Indexed metadata is never hidden by the matching status path exclusion.
    if await git("ls-files", "-z", "--", ".ken"):
        raise RunConflict("Review candidate tracks reserved Ken metadata")
    if sha != candidate.diff_sha256 or await git(
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        ".",
        ":(top,exclude).ken",
    ):
        raise RunConflict("Review candidate diff or working bytes changed")
    _source_identity(candidate)
    return ReviewGitWitness(candidate.base_sha, head, tree, sha)
