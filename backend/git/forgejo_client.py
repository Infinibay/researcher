"""Thin wrapper around the Forgejo/Gitea REST API using subprocess curl."""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

from backend.config.settings import settings

logger = logging.getLogger(__name__)


class ForgejoClient:
    """Centralised Forgejo HTTP calls via subprocess curl.

    Reads ``settings.FORGEJO_API_URL``, ``settings.FORGEJO_TOKEN``, and
    ``settings.FORGEJO_OWNER`` for defaults.
    """

    def __init__(self) -> None:
        self._api_url = settings.FORGEJO_API_URL.rstrip("/")
        self._token = settings.FORGEJO_TOKEN
        self._owner = settings.FORGEJO_OWNER

    # ── Helpers ────────────────────────────────────────────────────────

    def _curl(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
    ) -> Any:
        """Execute a curl request and return parsed JSON.

        Raises ``ValueError`` on non-zero exit or HTTP error.
        """
        url = f"{self._api_url}{path}"
        cmd: list[str] = [
            "curl", "-s",
            "-X", method,
            "-H", f"Authorization: token {self._token}",
            "-H", "Content-Type: application/json",
        ]
        if data is not None:
            cmd.extend(["-d", json.dumps(data)])
        cmd.append(url)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=settings.WEB_TIMEOUT,
        )
        if result.returncode != 0:
            raise ValueError(
                f"curl failed (rc={result.returncode}): {result.stderr or result.stdout}"
            )

        try:
            body = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON from Forgejo: {result.stdout[:500]}")

        # Forgejo returns {"message": "..."} on errors
        if isinstance(body, dict) and "message" in body and len(body) <= 2:
            # Allow create_repo to return bodies that have "message" among other keys
            if len(body) == 1 or (len(body) == 2 and "url" in body):
                raise ValueError(f"Forgejo API error: {body['message']}")

        return body

    # ── Public API ─────────────────────────────────────────────────────

    def create_repo(
        self,
        name: str,
        description: str = "",
        private: bool = False,
        owner: str | None = None,
    ) -> dict[str, Any]:
        """Create a new repository.

        When *owner* is provided (an organisation name), posts to
        ``/orgs/{owner}/repos``; otherwise posts to ``/user/repos``
        (the authenticated user's personal namespace).

        Returns the full Forgejo repo object (includes ``clone_url``).
        """
        if owner:
            endpoint = f"/orgs/{owner}/repos"
        else:
            endpoint = "/user/repos"

        body = self._curl("POST", endpoint, {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": False,
        })
        logger.info("Created Forgejo repo '%s' → %s", name, body.get("clone_url"))
        return body

    def get_branches(self, owner_repo: str) -> list[dict[str, Any]]:
        """List branches for a repo.

        *owner_repo* is ``"owner/repo"`` format.
        """
        return self._curl("GET", f"/repos/{owner_repo}/branches")

    def get_ref_sha(self, owner_repo: str, ref: str) -> str:
        """Get the commit SHA for a branch reference."""
        branch = self._curl("GET", f"/repos/{owner_repo}/branches/{ref}")
        return branch["commit"]["id"]

    def get_tree(
        self, owner_repo: str, sha: str, recursive: bool = True
    ) -> dict[str, Any]:
        """Get the git tree for a commit SHA."""
        rec = "true" if recursive else "false"
        return self._curl(
            "GET", f"/repos/{owner_repo}/git/trees/{sha}?recursive={rec}"
        )

    def get_contents(
        self, owner_repo: str, filepath: str, ref: str = "main"
    ) -> dict[str, Any]:
        """Get the contents of a file at a given ref."""
        return self._curl(
            "GET", f"/repos/{owner_repo}/contents/{filepath}?ref={ref}"
        )

    def get_pr_comments(
        self, owner_repo: str, pr_index: int
    ) -> list[dict[str, Any]]:
        """Get comments on a PR (issue comments API)."""
        return self._curl(
            "GET", f"/repos/{owner_repo}/issues/{pr_index}/comments"
        )

    def create_pr_comment(
        self, owner_repo: str, pr_index: int, body: str
    ) -> dict[str, Any]:
        """Post a comment on a PR."""
        return self._curl(
            "POST",
            f"/repos/{owner_repo}/issues/{pr_index}/comments",
            {"body": body},
        )


forgejo_client = ForgejoClient()
