"""Snapshot explicitly selected old files as attributed data, without Git metadata, inferred authorship or execution authority."""

import base64
import hashlib
import json
import os
import re
import stat
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from backend.runtime.contracts import InputTooLarge, RunConflict, RunNotFound
from backend.runtime.development_workspace import _source_identity


def selected_paths(paths):
    """Validate a bounded explicit selection; metadata, traversal and recursive discovery never expand its scope."""
    if not isinstance(paths, (tuple, list)) or not 1 <= len(paths) <= 128:
        raise ValueError("Select between one and 128 individual file paths")
    for path in paths:
        if (
            not isinstance(path, str)
            or not path
            or "\0" in path
            or len(path.encode()) > 4096
        ):
            raise ValueError(
                "Selected paths must be nonempty relative UTF-8 file names"
            )
        parts = path.split("/")
        if (
            path.startswith("/")
            or len(parts) > 32
            or any(
                part in ("", ".", "..", ".git", ".ken", ".worktrees") for part in parts
            )
        ):
            raise ValueError(
                "Select canonical relative paths outside execution and Git metadata"
            )
    if len(set(paths)) != len(paths):
        raise ValueError("A selected file path must occur only once")
    return tuple(paths)


@dataclass(frozen=True)
class PriorFilesTarget:
    """Exact owner-observed old source and selected paths; original input may remain explicitly unknown."""

    source_kind: str
    source_id: str
    paths: tuple[str, ...]
    snapshot_sha256: str

    def __post_init__(self):
        """Validate neutral selection identity before receipt lookup or any filesystem operation."""
        if (
            self.source_kind not in ("legacy_worktree", "private_copy")
            or not isinstance(self.source_id, str)
            or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", self.source_id)
        ):
            raise ValueError("Select a recorded legacy worktree or private copy")
        if self.source_kind == "legacy_worktree" and (
            not self.source_id.isdecimal()
            or str(int(self.source_id)) != self.source_id
            or int(self.source_id) <= 0
        ):
            raise ValueError(
                "Legacy worktree selection requires its positive recorded identifier"
            )
        object.__setattr__(self, "paths", selected_paths(self.paths))
        if not isinstance(self.snapshot_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.snapshot_sha256
        ):
            raise ValueError("Selected files require an observed SHA-256 fingerprint")


def _observation(info):
    """Retain actual file identity, mode and change indicators without inferring a Git commit or author."""
    return [
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    ]


@contextmanager
def _directory(path):
    """Pin every directory component from the filesystem root without following symlinks or reopening selected names."""
    path = Path(path)
    if not path.is_absolute() or any(part in (".", "..") for part in path.parts):
        raise RunConflict("Recorded source directory is not canonical")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    with ExitStack() as stack:
        fd = os.open("/", flags)
        stack.callback(os.close, fd)
        for part in path.parts[1:]:
            fd = os.open(part, flags, dir_fd=fd)
            stack.callback(os.close, fd)
        yield fd


def _entry(root, path, remaining):
    """Read one selected regular file, literal symlink target or observed absence with bounded nonblocking descriptors."""
    with ExitStack() as stack:
        parent = root
        parts = PurePosixPath(path).parts
        try:
            for part in parts[:-1]:
                parent = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=parent,
                )
                stack.callback(os.close, parent)
            before = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return {"path": path, "kind": "missing"}, 0
        if stat.S_ISLNK(before.st_mode):
            data = os.fsencode(os.readlink(parts[-1], dir_fd=parent))
            if len(data) > remaining:
                raise InputTooLarge(
                    "Selected file bytes exceed the complete import budget"
                )
            entry = {
                "path": path,
                "kind": "symlink",
                "target_base64": base64.b64encode(data).decode("ascii"),
                "git_mode": "120000",
            }
        elif stat.S_ISREG(before.st_mode):
            if before.st_size > remaining:
                raise InputTooLarge(
                    "Selected file bytes exceed the complete import budget"
                )
            fd = os.open(
                parts[-1],
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                dir_fd=parent,
            )
            stack.callback(os.close, fd)
            if _observation(os.fstat(fd)) != _observation(before):
                raise RunConflict("Selected file changed before acquisition")
            chunks = bytearray()
            while len(chunks) <= remaining:
                chunk = os.read(fd, min(65536, remaining + 1 - len(chunks)))
                if not chunk:
                    break
                chunks.extend(chunk)
            if len(chunks) > remaining:
                raise InputTooLarge(
                    "Selected file bytes exceed the complete import budget"
                )
            data = bytes(chunks)
            if _observation(os.fstat(fd)) != _observation(before):
                raise RunConflict("Selected file changed during acquisition")
            entry = {
                "path": path,
                "kind": "file",
                "content_base64": base64.b64encode(data).decode("ascii"),
                "git_mode": "100755" if before.st_mode & 0o111 else "100644",
            }
        else:
            raise RunConflict(
                "Select individual regular files or literal symlinks; special files and directories are not imported"
            )
        after = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
        if _observation(after) != _observation(before):
            raise RunConflict("Selected source changed during acquisition")
        entry.update(
            bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            observation=_observation(before),
        )
        return entry, len(data)


class FileImports:
    """Resolve stored source identity and observe selected bytes without modifying files, starting processes or assigning historic task ownership."""

    def __init__(self, runs):
        """Reuse existing run persistence; file data will be retained by its ordinary admission receipt."""
        self.runs = runs

    def sources(self, project_id, task_id):
        """List stored candidates for owner selection; a legacy agent label does not demonstrate task ownership or file availability."""
        with self.runs._transaction() as conn:
            self.runs._existing_task(conn, project_id, task_id)
            legacy = [
                {
                    "source_kind": "legacy_worktree",
                    "source_id": str(row["id"]),
                    "repository_id": row["repo_id"],
                    "label": row["agent_id"],
                    "recorded_status": row["status"],
                    "task_relation": "selected_by_owner_not_historically_verified",
                }
                for row in conn.execute(
                    "SELECT * FROM agent_worktrees WHERE project_id=? ORDER BY id",
                    (project_id,),
                )
            ]
            private = [
                {
                    "source_kind": "private_copy",
                    "source_id": row["attempt_id"],
                    "repository_id": json.loads(row["source_json"])["repository_id"],
                    "label": row["run_id"],
                    "recorded_status": row["state"],
                    "task_relation": "recorded_task",
                }
                for row in conn.execute(
                    "SELECT * FROM runtime_development_workspaces WHERE project_id=? AND task_id=? ORDER BY created_at,attempt_id",
                    (project_id, task_id),
                )
            ]
            return legacy + private

    def _source(self, conn, project_id, task_id, binding, kind, identifier):
        """Resolve only host-recorded paths in their true project/repository scope; never use an arbitrary caller path."""
        self.runs._existing_task(conn, project_id, task_id)
        self.runs._check_registration(conn, project_id, binding)
        _source_identity(binding)
        original = None
        expected = None
        if kind == "legacy_worktree":
            row = conn.execute(
                "SELECT * FROM agent_worktrees WHERE id=? AND project_id=? AND repo_id=?",
                (identifier, project_id, binding.repository_id),
            ).fetchone()
            if row is None:
                raise RunNotFound(
                    "Legacy worktree not found in this project and repository"
                )
            agent = row["agent_id"]
            if not agent or Path(agent).name != agent or agent in (".", ".."):
                raise RunConflict(
                    "Legacy worktree has an ambiguous recorded agent path"
                )
            root = Path(binding.workspace) / ".worktrees" / agent
            if str(root) != row["worktree_path"]:
                raise RunConflict(
                    "Legacy worktree is outside its registered repository allocation"
                )
            origin = {
                "kind": "selected_legacy_worktree_files",
                "source_kind": kind,
                "source_id": identifier,
                "project_id": project_id,
                "repository_id": binding.repository_id,
                "recorded_agent_label": agent,
                "recorded_branch_label": row["branch_name"],
                "task_relation": "selected_by_owner_not_historically_verified",
                "original_native_author": "unknown",
            }
        elif kind == "private_copy":
            row = conn.execute(
                "SELECT * FROM runtime_development_workspaces WHERE attempt_id=? AND project_id=? AND task_id=?",
                (identifier, project_id, task_id),
            ).fetchone()
            if row is None:
                raise RunNotFound("Private copy not found in this task")
            source = json.loads(row["source_json"])
            if any(
                source[key] != getattr(binding, key)
                for key in (
                    "repository_id",
                    "registration_path",
                    "workspace",
                    "device",
                    "inode",
                )
            ):
                raise RunConflict("Private files belong to another registered source")
            root = Path(row["allocation"]) / "repository"
            if row["workspace"] is not None and row["workspace"] != str(root):
                raise RunConflict("Private copy differs from its recorded allocation")
            if row["device"] is not None and row["inode"] is not None:
                expected = (row["device"], row["inode"])
            saved = conn.execute(
                "SELECT input_text,input_sha256 FROM runtime_input_snapshots WHERE attempt_id=?",
                (identifier,),
            ).fetchone()
            if saved is not None:
                if (
                    hashlib.sha256(saved["input_text"].encode()).hexdigest()
                    != saved["input_sha256"]
                ):
                    raise RunConflict("Original private input is inconsistent")
                original = json.loads(saved["input_text"])
            origin = {
                "kind": "selected_private_copy_files",
                "source_kind": kind,
                "source_id": identifier,
                "project_id": project_id,
                "repository_id": binding.repository_id,
                "recorded_run_id": row["run_id"],
                "recorded_attempt_id": identifier,
                "recorded_context_version": row["context_version"],
                "task_relation": "recorded_task",
                "original_native_author": "not_asserted_by_file_import",
            }
        else:
            raise ValueError("Select a recorded legacy worktree or private copy")
        return root, origin, original, expected

    def packet(self, conn, project_id, task_id, binding, kind, identifier, paths):
        """Freeze two equal selected-path observations; do not claim an atomic Git tree, ignored-file discovery or physical writer closure."""
        from dataclasses import asdict

        from backend.runtime.code_carryover import _encoded

        paths = selected_paths(paths)
        root, origin, original, expected = self._source(
            conn, project_id, task_id, binding, kind, identifier
        )
        try:
            with _directory(root) as fd:
                info = os.fstat(fd)
                identity = (info.st_dev, info.st_ino)
                if expected is not None and expected != identity:
                    raise RunConflict("Recorded private directory was replaced")
                observations = []
                for _ in range(2):
                    entries = []
                    remaining = 400000
                    for path in paths:
                        entry, size = _entry(fd, path, remaining)
                        remaining -= size
                        entries.append(entry)
                    observations.append(entries)
                if observations[0] != observations[1]:
                    raise RunConflict("Selected files changed between observations")
        except OSError as exc:
            raise RunConflict(
                "Selected source is unavailable, redirected or changed; original files were preserved"
            ) from exc
        snapshot = {
            "schema_version": 1,
            "origin": origin,
            "source": asdict(binding),
            "source_directory_identity": list(identity),
            "original_input": original,
            "original_input_status": "recorded" if original is not None else "unknown",
            "git_ancestry": "not_inspected",
            "selection_scope": "selected_paths_only",
            "stability": "two_equal_fd_observations_not_an_atomic_git_snapshot",
            "files": observations[0],
        }
        encoded = _encoded(snapshot)
        if len(encoded.encode()) > 600000:
            raise InputTooLarge(
                "Complete selected-file packet exceeds its input budget; no files or context were omitted"
            )
        return {
            "snapshot_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
            "snapshot": snapshot,
            "authority": "data_only",
            "acceptance": "not_granted",
            "publication": "not_granted",
            "explanation": "These are owner-selected earlier file bytes. Unlisted files are outside this selection. Observed absence does not prove a historical deletion intent, and unknown original input or author remains unknown. A fresh author must compare and adapt the material under current requirements; new checks, independent review and owner acceptance remain required.",
        }

    def preview(self, project_id, task_id, binding, kind, identifier, paths):
        """Inspect selected data without claiming work, admitting a run or executing Git/config from an old worktree."""
        PriorFilesTarget(kind, identifier, tuple(paths), "0" * 64)
        with self.runs._transaction() as conn:
            return self.packet(
                conn, project_id, task_id, binding, kind, identifier, paths
            )
