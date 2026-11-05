"""Owner-only readonly discovery/history for exact accepted local publications; observation is not remote write permission."""

import asyncio
import json
from dataclasses import asdict

from backend.runtime.contracts import RunConflict
from backend.runtime.publication_git import PublicationRefIntent
from backend.runtime.remote_runtime import RemotePublications


class RemoteDestinations:
    """Translate the registered destination into server evidence without asking the owner to supply internal IDs or credentials."""

    def __init__(self, runs):
        """Reuse scoped durable provenance; no network or process is opened here."""
        self.runs = runs
        self.remote = RemotePublications(runs)

    def subject(self, project_id, local_run_id):
        """Capture current exact accepted provenance and only its registered clone URL before/after a readonly lookup."""
        with self.runs._transaction() as conn:
            local, view = self.remote._root(conn, project_id, local_run_id)
            row = conn.execute(
                "SELECT remote_url FROM repositories WHERE project_id=? AND id=? AND status='active'",
                (project_id, view.source.repository_id),
            ).fetchone()
            if row is None or not row["remote_url"]:
                raise RunConflict(
                    "The accepted repository has no registered remote destination"
                )
            return local["task_id"], local["context_version"], view, row["remote_url"]

    async def observe(self, project_id, local_run_id, target_ref, base_ref, *, client):
        """Derive actual numeric identity and branch observations using bounded GETs; a changed original subject invalidates the preview."""
        PublicationRefIntent("owner-preview", target_ref, None)
        PublicationRefIntent("owner-preview", base_ref, None)
        original = await asyncio.to_thread(self.subject, project_id, local_run_id)
        task_id, context, view, clone_url = original
        remote = await client.discover_remote(clone_url)
        target = await client.observe_branch(remote, target_ref)
        base = await client.observe_branch(remote, base_ref)
        await client.verify_remote(remote)
        if await asyncio.to_thread(self.subject, project_id, local_run_id) != original:
            raise RunConflict(
                "The accepted publication changed during remote observation"
            )
        return {
            "project_id": project_id,
            "task_id": task_id,
            "local_publication_run_id": local_run_id,
            "context_version": context,
            "head_sha": view.head_sha,
            "base_sha": view.base_sha,
            "remote": asdict(remote),
            "target_ref": target_ref,
            "target_sha": target,
            "base_ref": base_ref,
            "observed_base_sha": base,
            "push_allowed": target in (None, view.base_sha, view.head_sha)
            and target_ref != base_ref
            and not target_ref.startswith("refs/heads/researcher-receipts/"),
            "pull_allowed": base == view.base_sha,
            "observed_at": self.runs.clock(),
        }

    def history(self, project_id, local_run_id):
        """Read bounded original remote actions/results even after withdrawal; history does not connect or repeat any effect."""
        with self.runs._transaction() as conn:
            local = self.remote.local._request(conn, project_id, local_run_id)
            view = self.remote.local._view(json.loads(local["view_json"]))
            current = False
            try:
                self.remote._root(conn, project_id, local_run_id)
                current = True
            except RunConflict:
                pass
            ids = [
                row["run_id"]
                for row in conn.execute(
                    "SELECT run_id FROM runtime_remote_publications WHERE project_id=? AND local_publication_run_id=? ORDER BY created_at DESC,rowid DESC LIMIT 101",
                    (project_id, local_run_id),
                )
            ]
            actions = [
                {
                    "run": asdict(
                        self.runs._view(self.runs._row(conn, project_id, run_id))
                    ),
                    "request": self.remote.request(project_id, run_id),
                }
                for run_id in ids[:100]
            ]
            return {
                "project_id": project_id,
                "task_id": local["task_id"],
                "local_publication_run_id": local_run_id,
                "context_version": local["context_version"],
                "head_sha": view.head_sha,
                "base_sha": view.base_sha,
                "acceptance_current": current,
                "actions": actions,
                "truncated": len(ids) > 100,
            }
