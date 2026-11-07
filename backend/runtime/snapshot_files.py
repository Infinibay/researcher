"""Bounded no-follow filesystem snapshots for private installation backups and restores."""

import hashlib
import os
import stat
import time
from contextlib import contextmanager
from pathlib import Path, PurePosixPath


def relative_name(value):
    """Accept only canonical relative paths; manifests cannot choose paths outside their root."""
    if not isinstance(value, str):
        raise ValueError('Snapshot path must be a string')
    path = PurePosixPath(value)
    if not isinstance(value, str) or not value or path.is_absolute() or '..' in path.parts or str(path) != value or value == '.':
        raise ValueError('Snapshot contains a noncanonical relative path')
    return path


@contextmanager
def open_file(root, relative):
    """Pin each parent and a regular leaf without following source or backup symlinks."""
    parts = relative_name(relative).parts
    handles = []
    try:
        parent = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        handles.append(parent)
        for part in parts[:-1]:
            parent = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
            handles.append(parent)
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent)
        handles.append(fd)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('Snapshot leaf must be a regular file')
        with os.fdopen(os.dup(fd), 'rb') as stream:
            yield stream
    finally:
        for fd in reversed(handles):
            os.close(fd)


class CopyBudget:
    """Bound total copied bytes, entry count and elapsed time for one explicit local operation."""

    def __init__(self, *, max_bytes=20 * 1024**3, max_files=200000, timeout=300):
        """Reject invalid limits before creating partial destination state."""
        if any(type(v) is not int or v <= 0 for v in (max_bytes, max_files, timeout)):
            raise ValueError('Snapshot limits must be positive integers')
        self.max_bytes, self.max_files = max_bytes, max_files
        self.deadline = time.monotonic() + timeout
        self.bytes = 0

    def check(self, *, size=0, entries=0):
        """Fail visibly instead of truncating a file or silently omitting entries."""
        if time.monotonic() > self.deadline or self.bytes + size > self.max_bytes or entries > self.max_files:
            raise ValueError('Snapshot exceeded its time, byte or file budget')


def inventory(root, budget):
    """List regular files, directories and symlinks without traversing a symlink or special device."""
    result = {}

    def walk(fd, prefix):
        """Visit pinned directory entries and capture metadata used to detect concurrent changes."""
        for entry in sorted(os.scandir(fd), key=lambda item: item.name):
            name = prefix + entry.name
            relative_name(name)
            info = entry.stat(follow_symlinks=False)
            item = {'mode': stat.S_IMODE(info.st_mode), 'identity': [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]}
            if stat.S_ISDIR(info.st_mode):
                item['kind'] = 'directory'
                result[name] = item
                budget.check(entries=len(result))
                child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                try:
                    walk(child, name + '/')
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode):
                item.update(kind='file', size=info.st_size)
                result[name] = item
            elif stat.S_ISLNK(info.st_mode):
                item.update(kind='symlink', target=os.readlink(entry.name, dir_fd=fd))
                result[name] = item
            else:
                raise ValueError(f'Stop active services and inspect unsupported filesystem entry: {name}')
            budget.check(entries=len(result))

    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        walk(fd, '')
    finally:
        os.close(fd)
    return result


def copy_regular(root, relative, destination, budget):
    """Stream one stable regular file into a new private destination and return its content hash."""
    digest = hashlib.sha256()
    count = 0
    with open_file(root, relative) as source:
        before = os.fstat(source.fileno())
        budget.check(size=before.st_size)
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        with os.fdopen(fd, 'wb') as target:
            while chunk := source.read(1024 * 1024):
                budget.check(size=len(chunk))
                target.write(chunk)
                digest.update(chunk)
                count += len(chunk)
                budget.bytes += len(chunk)
            target.flush()
            os.fsync(target.fileno())
        after = os.fstat(source.fileno())
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError('Source file changed during snapshot')
    return {'sha256': digest.hexdigest(), 'bytes': count}


def digest_file(root, relative, budget):
    """Hash an existing regular file through pinned no-follow descriptors within the deadline."""
    digest = hashlib.sha256()
    count = 0
    with open_file(root, relative) as stream:
        while chunk := stream.read(1024 * 1024):
            budget.check()
            count += len(chunk)
            if count > budget.max_bytes:
                raise ValueError('Snapshot file exceeded the byte budget')
            digest.update(chunk)
    return {'sha256': digest.hexdigest(), 'bytes': count}
