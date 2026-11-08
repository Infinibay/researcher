"""Explicit fresh-install creation; serving/recovery never calls these functions.

This creates storage format, not proof that an existing host has no actors.
Never use it to repair a lost journal or adopt an already running deployment.
"""

import os
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from backend.runtime.authority_journal import (
    WitnessedAuthorityJournal,
    _canonical,
    _envelope,
    _hash,
)
from backend.runtime.peer_process import boot_id, observer_namespace


def _sync_directory(path):
    """Fsync an opened directory and close its descriptor so newly created entries can become durable."""
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _create_file(path):
    """Create a new private regular-file path exclusively without following a final symlink; never adopt existing data."""
    fd = os.open(
        path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600
    )
    os.close(fd)


def initialize_database(database):
    """Create a new private source DB; retain partial files on failure for inspection."""
    from backend.tools.base.db import ensure_migrations

    path = Path(database).absolute()
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
        _sync_directory(directory.parent)
    _create_file(path)
    ensure_migrations(str(path))
    with path.open("rb") as stream:
        os.fsync(stream.fileno())
    _sync_directory(path.parent)
    return path


def initialize_authority(*, database_dir, witness_dir):
    """Create NEW separated stores; no reuse, adoption or missing-witness repair.

    Parents must already exist and be trusted operator paths. Directory separation
    must also be preserved by backup policy; it does not prove host enrollment.
    """
    roots = [Path(p).absolute() for p in (database_dir, witness_dir)]
    roots = [p.parent.resolve(strict=True) / p.name for p in roots]
    database_root, witness_root = roots
    if database_root.is_relative_to(witness_root) or witness_root.is_relative_to(
        database_root
    ):
        raise ValueError(
            "Database and witness directories must be separate, non-overlapping paths"
        )
    if any(os.path.lexists(p) for p in roots):
        raise FileExistsError(
            "Authority directories must be NEW; existing/partial state requires inspection, not initialization"
        )
    for directory in roots:
        directory.mkdir(mode=0o700)
        _sync_directory(directory.parent)
    paths = {
        "database": database_root / "authority.db",
        "witness": witness_root / "authority.log",
        "mutex": witness_root / "authority.lock",
    }
    for path in paths.values():
        _create_file(path)
    authority_id = str(uuid4())
    with closing(sqlite3.connect(paths["database"])) as conn, conn:
        conn.executescript("""
            PRAGMA synchronous=EXTRA;
            PRAGMA user_version=1;
            CREATE TABLE authority_meta(
                id INTEGER PRIMARY KEY CHECK(id=1), authority_id TEXT NOT NULL,
                sequence INTEGER NOT NULL CHECK(sequence>=0), state_hash TEXT NOT NULL,
                transition_id TEXT NOT NULL);
            CREATE TABLE authority_records(key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
        """)
        conn.execute(
            "INSERT INTO authority_meta VALUES(1,?,0,?,'genesis')",
            (authority_id, _hash({})),
        )
    identities = {
        name: {"device": path.stat().st_dev, "inode": path.stat().st_ino}
        for name, path in paths.items()
    }
    header = _envelope(
        {
            "kind": "HEADER",
            "format": 1,
            "authority_id": authority_id,
            "files": identities,
            "boot_id": boot_id(),
            "observer_namespace": observer_namespace(),
        },
        None,
    )
    commit = _envelope(
        {
            "kind": "COMMIT",
            "sequence": 0,
            "state_hash": _hash({}),
            "transition_id": "genesis",
        },
        header["digest"],
    )
    with paths["witness"].open("wb") as stream:
        stream.write(_canonical(header) + b"\n" + _canonical(commit) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    for key in ("database", "mutex"):
        with paths[key].open("rb") as stream:
            os.fsync(stream.fileno())
    for directory in roots:
        _sync_directory(directory)
    config = {name: str(path) for name, path in paths.items()} | {
        "authority_id": authority_id
    }
    with WitnessedAuthorityJournal(**config) as journal:
        journal.load()
    return config
