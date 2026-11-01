"""Storage-format fixtures, NOT evidence of a managed host/bootstrap domain."""

import hashlib
import json
import os
import sqlite3
from types import SimpleNamespace


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def envelope(payload, previous=None):
    record = {"payload": payload, "previous": previous}
    record["digest"] = digest(record)
    return record


def provisioned(tmp_path, records=None):
    # A future broker must supply independently proven genesis. Tests only seed
    # its specified on-disk format, with no production bootstrap bypass flag.
    from backend.runtime.peer_process import boot_id, observer_namespace

    database_root, witness_root = (
        tmp_path / "authority-db",
        tmp_path / "external-witness",
    )
    database_root.mkdir(mode=0o700)
    witness_root.mkdir(mode=0o700)
    c = SimpleNamespace(
        database=database_root / "authority.db",
        witness=witness_root / "authority.log",
        mutex=witness_root / "authority.lock",
        authority_id="synthetic-provisioned-authority",
    )
    for path in (c.database, c.witness, c.mutex):
        path.touch(mode=0o600)
    records = records or {}
    with sqlite3.connect(c.database) as conn:
        conn.executescript("""
            PRAGMA user_version=1;
            CREATE TABLE authority_meta(id INTEGER PRIMARY KEY CHECK(id=1), authority_id TEXT NOT NULL,
                sequence INTEGER NOT NULL CHECK(sequence>=0), state_hash TEXT NOT NULL, transition_id TEXT NOT NULL);
            CREATE TABLE authority_records(key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
        """)
        conn.execute(
            "INSERT INTO authority_meta VALUES(1,?,0,?,'genesis')",
            (c.authority_id, digest(records)),
        )
        conn.executemany(
            "INSERT INTO authority_records VALUES(?,?)",
            [(key, canonical(value).decode()) for key, value in records.items()],
        )
    files = {
        name: {"device": path.stat().st_dev, "inode": path.stat().st_ino}
        for name, path in (
            ("database", c.database),
            ("witness", c.witness),
            ("mutex", c.mutex),
        )
    }
    header = envelope(
        {
            "kind": "HEADER",
            "format": 1,
            "authority_id": c.authority_id,
            "files": files,
            "boot_id": boot_id(),
            "observer_namespace": observer_namespace(),
        }
    )
    commit = envelope(
        {
            "kind": "COMMIT",
            "sequence": 0,
            "state_hash": digest(records),
            "transition_id": "genesis",
        },
        header["digest"],
    )
    with c.witness.open("wb") as stream:
        stream.write(canonical(header) + b"\n" + canonical(commit) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    return c


def journal(c):
    from backend.runtime.authority_journal import WitnessedAuthorityJournal

    return WitnessedAuthorityJournal(
        database=c.database,
        witness=c.witness,
        mutex=c.mutex,
        authority_id=c.authority_id,
    )


def fingerprint(c):
    return {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in (("database", c.database), ("witness", c.witness))
    }
