"""Resolve host repository registrations and revalidate an admitted directory."""

from contextlib import closing
from pathlib import Path

from backend.db.connection import connect
from backend.runtime.contracts import (
    RunConflict,
    RunNotFound,
    WorkspaceBinding,
    WorkspaceChanged,
)


class WorkspaceRegistry:
    def __init__(self, database, root):
        self.database = str(database)
        self.root = Path(root).resolve(strict=True)

    def bind(self, project_id, repository_id=None):
        with closing(connect(self.database)) as conn:
            rows = conn.execute(
                "SELECT * FROM repositories WHERE project_id=? AND status='active'",
                (project_id,),
            ).fetchall()
            if repository_id is not None:
                rows = [row for row in rows if row["id"] == repository_id]
            if not rows:
                raise RunNotFound("No active repository in this project")
            if len(rows) != 1:
                raise RunConflict("Select a repository for this request")
            selected = rows[0]
            try:
                root = Path(selected["local_path"]).resolve(strict=True)
                info = root.stat()
            except (OSError, TypeError, ValueError) as exc:
                raise RunConflict("Repository directory is unavailable") from exc
            if (
                not root.is_dir()
                or root == self.root
                or not root.is_relative_to(self.root)
            ):
                raise RunConflict("Repository is outside the managed workspace root")
            if Path(self.database).resolve().is_relative_to(root):
                raise RunConflict("Repository contains the host database")
            for other in conn.execute(
                "SELECT local_path FROM repositories WHERE project_id<>? AND status='active'",
                (project_id,),
            ):
                path = Path(other[0]).resolve()
                if root.is_relative_to(path) or path.is_relative_to(root):
                    raise RunConflict("Workspace is shared with another project")
            return WorkspaceBinding(
                selected["id"],
                selected["name"],
                selected["local_path"],
                str(root),
                info.st_dev,
                info.st_ino,
                repository_id,
            )

    def select(self, project_id, repository_id=None):
        return Path(self.bind(project_id, repository_id).workspace)

    def validate(self, project_id, binding):
        try:
            current = self.bind(project_id, binding.repository_id)
        except (RunConflict, RunNotFound, OSError) as exc:
            raise WorkspaceChanged(
                "Admitted repository is no longer available"
            ) from exc
        fields = ("repository_id", "registration_path", "workspace", "device", "inode")
        if any(getattr(current, name) != getattr(binding, name) for name in fields):
            raise WorkspaceChanged("Admitted repository directory changed")
        return Path(binding.workspace)
