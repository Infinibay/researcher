"""Confined reference-upload filesystem operations shared by acquisition and owner UI.

Paths come from project metadata, never an arbitrary request path. Every directory
is opened relative to a trusted root without symlinks; a download retains its FD.
"""

import os
import hashlib
import re
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
                with_parent = os.open(self.root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
                try:
                    os.fsync(with_parent)
                finally:
                    os.close(with_parent)
            parent = os.open(
                self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
            )
            handles.append(parent)
            for part in parts:
                if create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=parent)
                        os.fsync(parent)
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

    def save(self, project_id, data, *, name=None):
        """Create/fsync one private file; an admitted journal may supply its unique name, never overwrite it."""
        if type(project_id) is not int or project_id <= 0:
            raise ValueError("Reference project identity must be positive")
        journaled = name is not None
        name = name or uuid4().hex
        if not re.fullmatch(r'[a-f0-9]{32}', name):
            raise ValueError('Reference allocation name must be a unique hexadecimal identifier')
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
                if not journaled:
                    os.unlink(name, dir_fd=parent)
                raise
            finally:
                os.close(fd)
            os.fsync(parent)
        return self.root / str(project_id) / "uploads" / name

    @staticmethod
    def _identity(entry):
        """Describe the exact regular-file revision observed before an owner deletion."""
        return [entry.st_dev, entry.st_ino, entry.st_size, entry.st_mtime_ns, entry.st_ctime_ns]

    def identity(self, reference):
        """Observe a confined file revision; a missing file is distinct from an unavailable root."""
        parts = self._parts(reference)
        with self._directory(parts[:-1]) as parent:
            try:
                entry = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                os.fsync(parent)
                return None
            if not stat.S_ISREG(entry.st_mode):
                raise SourceUnavailable('Reference is not a regular file')
            return self._identity(entry)

    def confirm(self, reference, *, size, sha256):
        """Verify and fsync the complete original upload before publishing a database reference."""
        parts = self._parts(reference)
        try:
            with self._directory(parts[:-1]) as parent, self.open(reference) as fd:
                before = os.fstat(fd)
                if before.st_size != size or size > 1000000:
                    raise SourceUnavailable('La carga no conserva el tamaño original; no se publicó el adjunto.')
                digest = hashlib.sha256()
                remaining = size
                while remaining:
                    chunk = os.read(fd, min(65536, remaining))
                    if not chunk:
                        raise SourceUnavailable('La carga está incompleta; no se publicó el adjunto.')
                    digest.update(chunk)
                    remaining -= len(chunk)
                if digest.hexdigest() != sha256 or self._identity(before) != self._identity(os.fstat(fd)):
                    raise SourceUnavailable('Los bytes no coinciden con la carga original; se conservan sin publicarlos.')
                os.fsync(fd)
                os.fsync(parent)
        except OSError as exc:
            raise SourceUnavailable('No se pudo confirmar el archivo original; consulta la operación antes de repetir la carga.') from exc

    def remove(self, reference, *, expected_identity=...):
        """Remove a confined regular file only if its admitted revision still matches; absence is idempotent."""
        parts = self._parts(reference)
        try:
            with self._directory(parts[:-1]) as parent:
                try:
                    entry = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    os.fsync(parent)
                    return False
                if not stat.S_ISREG(entry.st_mode):
                    raise SourceUnavailable("Reference is not a regular file")
                if expected_identity is not ... and expected_identity != self._identity(entry):
                    raise SourceUnavailable('El archivo cambió desde la solicitud de borrado; se conserva para revisión.')
                os.unlink(parts[-1], dir_fd=parent)
                os.fsync(parent)
                return True
        except OSError as exc:
            raise SourceUnavailable('No se pudo confirmar el borrado original; sus datos de recuperación se conservan.') from exc
