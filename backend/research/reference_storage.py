"""Confined reference-upload filesystem operations shared by acquisition and owner UI.

Paths come from project metadata, never an arbitrary request path. Every directory
is opened relative to a trusted root without symlinks; a download retains its FD.
"""

import os
import stat
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from backend.research.models import SourceTooLarge, SourceUnavailable


class ReferenceStorage:
    """Own project upload traversal, bounded snapshots and immutable new file creation."""

    def __init__(self, root: Path):
        """Bind the configured upload root without creating it during reads."""
        self.root = Path(root).absolute()

    @contextmanager
    def _directory(self, parts, *, create=False):
        """Pin each directory FD, optionally creating private upload directories."""
        handles = []
        try:
            if create:
                self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            parent = os.open(
                self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
            )
            handles.append(parent)
            for part in parts:
                if create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=parent)
                    except FileExistsError:
                        pass
                parent = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=parent,
                )
                handles.append(parent)
            yield parent
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise SourceUnavailable(
                "Reference storage is unavailable or contains a symlink"
            ) from exc
        finally:
            for fd in reversed(handles):
                os.close(fd)

    def _parts(self, reference):
        """Require the recorded path to belong to this reference's project uploads."""
        try:
            parts = Path(reference.path).relative_to(self.root).parts
        except ValueError as exc:
            raise SourceUnavailable(
                "Reference is outside the configured project uploads"
            ) from exc
        if (
            ".." in parts
            or len(parts) < 3
            or parts[:2] != (str(reference.project_id), "uploads")
        ):
            raise SourceUnavailable(
                "Reference is outside the configured project uploads"
            )
        return parts

    @contextmanager
    def open(self, reference):
        """Yield an already-open regular file; no caller should reopen its pathname."""
        parts = self._parts(reference)
        with self._directory(parts[:-1]) as parent:
            fd = os.open(
                parts[-1],
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                dir_fd=parent,
            )
            try:
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise SourceUnavailable("Reference is not a regular file")
                yield fd
            finally:
                os.close(fd)

    def snapshot(self, reference, *, max_bytes):
        """Return a stable bounded byte revision; never a silently truncated prefix."""
        try:
            with self.open(reference) as fd:
                before = os.fstat(fd)
                if before.st_size > max_bytes:
                    raise SourceTooLarge("Attachment exceeds the configured byte limit")
                data = bytearray()
                while len(data) <= max_bytes:
                    chunk = os.read(fd, min(65536, max_bytes + 1 - len(data)))
                    if not chunk:
                        break
                    data.extend(chunk)
                if len(data) > max_bytes:
                    raise SourceTooLarge("Attachment exceeds the configured byte limit")
                after = os.fstat(fd)
                if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                    after.st_size,
                    after.st_mtime_ns,
                    after.st_ctime_ns,
                ):
                    raise SourceUnavailable(
                        "Attachment changed during acquisition; capture a stable revision"
                    )
                return bytes(data)
        except SourceTooLarge:
            raise
        except OSError as exc:
            raise SourceUnavailable(
                "Attachment is unavailable or contains a symlink"
            ) from exc

    def save(self, project_id, data):
        """Create a private unique file, fsync it, then return its metadata path."""
        if type(project_id) is not int or project_id <= 0:
            raise ValueError("Reference project identity must be positive")
        name = uuid4().hex
        with self._directory((str(project_id), "uploads"), create=True) as parent:
            fd = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600,
                dir_fd=parent,
            )
            try:
                view = memoryview(data)
                while view:
                    written = os.write(fd, view)
                    if written <= 0:
                        raise OSError("Reference write did not advance")
                    view = view[written:]
                os.fsync(fd)
            except BaseException:
                os.unlink(name, dir_fd=parent)
                raise
            finally:
                os.close(fd)
            os.fsync(parent)
        return self.root / str(project_id) / "uploads" / name

    def remove(self, reference):
        """Remove only this project's regular upload; missing files permit metadata cleanup."""
        parts = self._parts(reference)
        try:
            with self._directory(parts[:-1]) as parent:
                entry = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
                if not stat.S_ISREG(entry.st_mode):
                    raise SourceUnavailable("Reference is not a regular file")
                os.unlink(parts[-1], dir_fd=parent)
                os.fsync(parent)
                return True
        except FileNotFoundError:
            return False
