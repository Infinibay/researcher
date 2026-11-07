"""Witnessed storage for a provisioned host authority; never a launch permit.

There is deliberately no create/bootstrap API. A managed host domain must provide
genesis and keep the witness outside its database restore domain. Loading may
complete a durable PREPARE's database writes, but never executes/replays actors.
The future broker owns grants, actor authentication, bootstrap and release policy.
"""

import fcntl
import hashlib
import io
import json
import os
import re
import sqlite3
import stat
import threading
from contextlib import closing, contextmanager, nullcontext
from dataclasses import dataclass
from pathlib import Path

from backend.runtime.peer_process import boot_id, observer_namespace

MAX_RECORD_BYTES = 256 * 1024
MAX_STATE_BYTES = 8 * 1024 * 1024
MAX_RECORDS = 100000
MAX_LINE_BYTES = 1024 * 1024
MAX_JOURNAL_BYTES = 128 * 1024 * 1024
MAX_HISTORY_CACHE_BYTES = 8 * 1024 * 1024
MAX_DATABASE_BYTES = 128 * 1024 * 1024
MAX_SEQUENCE = 2**63 - 1


class AuthorityUncertain(RuntimeError):
    """Missing, inconsistent or unverified state must not be reinitialized."""


class AuthorityConflict(RuntimeError):
    """The expected state or operation identity no longer describes this write."""


class AuthorityBusy(RuntimeError):
    """Contention is not a new installation or proof of closure."""


class AuthorityCapacity(RuntimeError):
    """A provisioned checkpoint/capacity change is needed; never discard history."""


@dataclass(frozen=True)
class AuthoritySnapshot:
    sequence: int
    state_hash: str
    records: dict
    recovered: tuple[str, ...] = ()


@dataclass(frozen=True)
class CommitReceipt:
    sequence: int
    state_hash: str
    transition_id: str
    fresh: bool


@dataclass
class _History:
    commit: dict
    pending: dict | None
    head: str
    receipts: dict
    valid_end: int
    torn_tail: bool


def _canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def _hash(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _decode(raw):
    return json.loads(raw, object_pairs_hook=_unique, parse_constant=_nonfinite)


def _nonfinite(_value):
    raise ValueError("Nonfinite JSON")


def _sequence(value):
    return type(value) is int and 0 <= value <= MAX_SEQUENCE


def _state_digest(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _key(value):
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or not value.isprintable()
    ):
        raise ValueError("Invalid authority record key")


def _operation_id(value):
    if (
        not isinstance(value, str)
        or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value)
        or value == "genesis"
    ):
        raise ValueError("Invalid authority transition ID")


def _delta(puts, deletes):
    if not isinstance(puts, dict) or not isinstance(deletes, (tuple, list)):
        raise TypeError("Expected record puts and deletes")
    for key, value in puts.items():
        _key(key)
        if len(_canonical(value)) > MAX_RECORD_BYTES:
            raise AuthorityCapacity("Authority record exceeds its bounded format")
    for key in deletes:
        _key(key)
    if len(set(deletes)) != len(deletes) or set(puts) & set(deletes):
        raise ValueError("Record writes must not overlap")
    # Serialize now, before any write. No shared caller-owned mutable values.
    return _decode(_canonical(puts)), sorted(deletes)


def _apply(records, puts, deletes):
    result = {key: value for key, value in records.items() if key not in deletes}
    result.update(puts)
    if len(result) > MAX_RECORDS or len(_canonical(result)) > MAX_STATE_BYTES:
        raise AuthorityCapacity(
            "Authority state requires a provisioned capacity change"
        )
    return result


def _envelope(payload, previous):
    record = {"payload": payload, "previous": previous}
    record["digest"] = _hash(record)
    return record


def _intent(prepare):
    return _hash(
        {key: prepare[key] for key in ("from_sequence", "from_hash", "puts", "deletes")}
    )


class WitnessedAuthorityJournal:
    """Open-only CAS storage. Commit receipts acknowledge data, never effects.

    ``load`` verifies actual SQL rows and reconciles an interrupted witnessed
    transition forward. ``commit`` deduplicates the original intent, even after
    later transitions. The expected authority ID comes from external provision,
    not from adopting a project DB or treating absent files as a fresh install.
    """

    def __init__(self, *, database, witness, mutex, authority_id):
        """Bind original private files and an empty, bounded cache of verified witness bytes."""
        if not isinstance(authority_id, str) or not 1 <= len(authority_id) <= 128:
            raise ValueError("An externally provisioned authority ID is required")
        self.authority_id = authority_id
        self._pid = os.getpid()
        self._local = threading.RLock()
        self._fds = {}
        self._paths = {}
        self._history_cache = None
        try:
            for name, supplied in (
                ("database", database),
                ("witness", witness),
                ("mutex", mutex),
            ):
                path = Path(supplied).absolute()
                # Resolve ancestors but do not follow a symlink leaf.
                path = path.parent.resolve(strict=True) / path.name
                self._paths[name] = path
                flags = os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC
                if name == "witness":
                    flags |= os.O_APPEND
                self._fds[name] = os.open(path, flags)
            self._identities = {
                name: self._identity(os.fstat(fd)) for name, fd in self._fds.items()
            }
            if len({tuple(value.values()) for value in self._identities.values()}) != 3:
                raise AuthorityUncertain("Authority files must be distinct")
            self._check_files()
        except BaseException as exc:
            self.close()
            if isinstance(exc, (OSError, ValueError)):
                raise AuthorityUncertain(
                    "Authority state is missing or not private; no bootstrap performed"
                ) from exc
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        """Release original descriptors and cached evidence without acquiring an inherited post-fork lock."""
        # A vanished parent thread may own the inherited RLock. Closing copies
        # after fork must not wait on it or unlock the parent's flock.
        with self._local if self._pid == os.getpid() else nullcontext():
            for fd in self._fds.values():
                os.close(fd)
            self._fds.clear()
            self._history_cache = None

    @staticmethod
    def _identity(info):
        return {"device": info.st_dev, "inode": info.st_ino}

    def _check_files(self):
        if self._pid != os.getpid() or len(self._fds) != 3:
            raise AuthorityUncertain("Reopen authority handles after fork or close")
        for name, path in self._paths.items():
            info = os.fstat(self._fds[name])
            current = path.stat(follow_symlinks=False)
            parent = path.parent.stat()
            if (
                not stat.S_ISREG(info.st_mode)
                or not stat.S_ISREG(current.st_mode)
                or info.st_uid != os.geteuid()
                or parent.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) & 0o077
                or stat.S_IMODE(parent.st_mode) & 0o077
                or info.st_nlink != 1
                or self._identity(current) != self._identities[name]
            ):
                raise AuthorityUncertain("Authority file identity or ownership changed")
            if name == "database" and info.st_size > MAX_DATABASE_BYTES:
                raise AuthorityCapacity("Authority database capacity exceeded")

    @contextmanager
    def _operation(self):
        # Check before acquiring an inherited Python lock, not just after it.
        if self._pid != os.getpid():
            raise AuthorityUncertain("Reopen authority handles after fork")
        with self._local:
            locked = False
            try:
                self._check_files()
                try:
                    fcntl.flock(self._fds["mutex"], fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise AuthorityBusy("Authority mutation is already owned") from exc
                locked = True
                self._check_files()
                with closing(self._connection()) as conn:
                    try:
                        yield conn
                    finally:
                        if conn.in_transaction:
                            conn.rollback()
                self._check_files()
            except sqlite3.OperationalError as exc:
                if getattr(exc, "sqlite_errorcode", None) in (
                    sqlite3.SQLITE_BUSY,
                    sqlite3.SQLITE_LOCKED,
                ):
                    raise AuthorityBusy(
                        "Authority SQL requires reconciliation after contention"
                    ) from exc
                raise AuthorityUncertain(
                    "Authority SQL state cannot be verified"
                ) from exc
            except (
                OSError,
                sqlite3.DatabaseError,
                KeyError,
                TypeError,
                IndexError,
                RecursionError,
            ) as exc:
                raise AuthorityUncertain(
                    "Authority storage cannot be verified"
                ) from exc
            finally:
                if locked:
                    fcntl.flock(self._fds["mutex"], fcntl.LOCK_UN)

    def _connection(self):
        conn = sqlite3.connect(
            self._paths["database"].as_uri() + "?mode=rw",
            uri=True,
            isolation_level=None,
            timeout=0,
        )
        try:
            conn.row_factory = sqlite3.Row
            if (
                conn.execute("PRAGMA journal_mode").fetchone()[0] != "delete"
                or conn.execute("PRAGMA user_version").fetchone()[0] != 1
            ):
                raise AuthorityUncertain("Unsupported provisioned authority format")
            # EXTRA also synchronizes rollback-journal deletion. Do not reuse the
            # project's WAL/NORMAL connection policy for this separate journal.
            conn.execute("PRAGMA synchronous=EXTRA")
            if conn.execute("PRAGMA synchronous").fetchone()[0] != 3:
                raise AuthorityUncertain(
                    "Required authority durability policy unavailable"
                )
            self._check_files()
            return conn
        except BaseException:
            conn.close()
            raise

    def _state(self, conn):
        rows = conn.execute("SELECT * FROM authority_meta").fetchall()
        if (
            len(rows) != 1
            or rows[0]["id"] != 1
            or rows[0]["authority_id"] != self.authority_id
        ):
            raise AuthorityUncertain("Authority enrollment differs")
        meta = rows[0]
        sizes = conn.execute(
            f"SELECT key,length(CAST(value_json AS BLOB)) AS bytes FROM authority_records LIMIT {MAX_RECORDS + 1}"
        ).fetchall()
        if (
            len(sizes) > MAX_RECORDS
            or any(row["bytes"] > MAX_RECORD_BYTES for row in sizes)
            or sum(row["bytes"] for row in sizes) > MAX_STATE_BYTES
        ):
            raise AuthorityCapacity("Authority SQL records exceed their bounded format")
        records = {}
        try:
            for row in conn.execute(
                "SELECT key,value_json FROM authority_records ORDER BY key"
            ):
                _key(row["key"])
                value = _decode(row["value_json"])
                if _canonical(value).decode() != row["value_json"]:
                    raise ValueError("Noncanonical authority row")
                records[row["key"]] = value
            actual = _hash(_apply(records, {}, []))
        except (ValueError, TypeError) as exc:
            raise AuthorityUncertain(
                "Authority rows are not valid canonical state"
            ) from exc
        if (
            type(meta["sequence"]) is not int
            or not 0 <= meta["sequence"] <= MAX_SEQUENCE
            or actual != meta["state_hash"]
        ):
            raise AuthorityUncertain(
                "Actual authority rows differ from their recorded state hash"
            )
        return AuthoritySnapshot(meta["sequence"], actual, records), meta[
            "transition_id"
        ]

    def _history(self):
        """Validate actual witness bytes, reusing only an identical previously verified prefix.

        Every call reads the current file; timestamps and size alone never prove
        integrity. The unchanged prefix retains its chain/semantic validation,
        while appended records and live enrollment are checked anew. Oversized
        histories use the original streaming path without retaining a buffer.
        SQL rows and cross-store agreement remain verified by the caller.
        """
        size = os.fstat(self._fds["witness"]).st_size
        if size > MAX_JOURNAL_BYTES:
            raise AuthorityCapacity("Authority witness needs a provisioned checkpoint")
        previous = None
        commit = pending = None
        receipts = {}
        valid_end = 0
        torn = False
        buffered = None
        with os.fdopen(os.dup(self._fds["witness"]), "rb") as disk:
            disk.seek(0)
            if size <= MAX_HISTORY_CACHE_BYTES:
                candidate = disk.read(MAX_HISTORY_CACHE_BYTES + 1)
                if len(candidate) <= MAX_HISTORY_CACHE_BYTES:
                    buffered = candidate
            stream = io.BytesIO(buffered) if buffered is not None else disk
            stream.seek(0)
            cached = self._history_cache
            self._history_cache = None
            if buffered is not None and cached is not None and buffered.startswith(cached[0]):
                prefix, history = cached
                self._header(_decode(prefix.split(b"\n", 1)[0])["payload"])
                previous = history.head
                commit, pending = history.commit, history.pending
                receipts = dict(history.receipts)
                valid_end = history.valid_end
                stream.seek(valid_end)
            while raw := stream.readline(MAX_LINE_BYTES + 1):
                if len(raw) > MAX_LINE_BYTES:
                    raise AuthorityCapacity(
                        "Authority witness record exceeds its format"
                    )
                if not raw.endswith(b"\n"):
                    torn = True
                    break
                try:
                    record = _decode(raw)
                    if (
                        set(record) != {"payload", "previous", "digest"}
                        or record["previous"] != previous
                        or record["digest"]
                        != _hash({"payload": record["payload"], "previous": previous})
                    ):
                        raise ValueError("Broken witness chain")
                    payload = record["payload"]
                    if previous is None:
                        self._header(payload)
                    elif payload["kind"] == "PREPARE":
                        if commit is None or pending is not None:
                            raise ValueError("Unordered witness prepare")
                        self._prepare(payload, commit)
                        if payload["transition_id"] in receipts:
                            raise ValueError("Repeated witness identity")
                        pending = payload
                    elif payload["kind"] == "COMMIT":
                        if set(payload) != {
                            "kind",
                            "sequence",
                            "state_hash",
                            "transition_id",
                        }:
                            raise ValueError("Invalid commit")
                        if not _sequence(payload["sequence"]) or not _state_digest(
                            payload["state_hash"]
                        ):
                            raise ValueError("Invalid committed sequence/hash")
                        if commit is None:
                            if (
                                payload["sequence"] != 0
                                or payload["transition_id"] != "genesis"
                            ):
                                raise ValueError("Missing genesis commit")
                        elif pending is None or (
                            payload["sequence"],
                            payload["state_hash"],
                            payload["transition_id"],
                        ) != (
                            pending["sequence"],
                            pending["state_hash"],
                            pending["transition_id"],
                        ):
                            raise ValueError("Commit without prepared intent")
                        if pending is not None:
                            receipts[payload["transition_id"]] = (
                                _intent(pending),
                                CommitReceipt(
                                    payload["sequence"],
                                    payload["state_hash"],
                                    payload["transition_id"],
                                    False,
                                ),
                            )
                        commit, pending = payload, None
                    else:
                        raise ValueError("Unknown witness record")
                    previous = record["digest"]
                    valid_end += len(raw)
                except (ValueError, TypeError, KeyError) as exc:
                    raise AuthorityUncertain(
                        "Authority witness is corrupt or inconsistent"
                    ) from exc
        if commit is None:
            raise AuthorityUncertain(
                "Authority genesis is missing; no bootstrap performed"
            )
        history = _History(commit, pending, previous, receipts, valid_end, torn)
        if buffered is not None:
            self._history_cache = (buffered[:valid_end], history)
        return history

    def _header(self, payload):
        """Require the live kernel/observer enrollment for every normal authority operation."""
        self._validate_header(payload, expected_boot=boot_id(), expected_observer=observer_namespace())

    def _validate_header(self, payload, *, expected_boot, expected_observer):
        """Check exact provisioned file identity and header shape against explicitly selected observations."""
        if not isinstance(payload, dict) or not isinstance(payload.get("files"), dict):
            raise AuthorityUncertain("Invalid authority enrollment shape")
        if (
            type(payload.get("format")) is not int
            or type(payload.get("observer_namespace")) is not int
        ):
            raise AuthorityUncertain("Invalid authority enrollment types")
        for identity in payload["files"].values():
            if not isinstance(identity, dict) or any(
                type(value) is not int for value in identity.values()
            ):
                raise AuthorityUncertain("Invalid authority file identity types")
        if payload != {
            "kind": "HEADER",
            "format": 1,
            "authority_id": self.authority_id,
            "files": self._identities,
            "boot_id": expected_boot,
            "observer_namespace": expected_observer,
        }:
            raise AuthorityUncertain(
                "Authority files, kernel or observer differ from enrollment"
            )

    @staticmethod
    def _prepare(payload, commit):
        if set(payload) != {
            "kind",
            "from_sequence",
            "from_hash",
            "sequence",
            "state_hash",
            "transition_id",
            "puts",
            "deletes",
        }:
            raise ValueError("Invalid prepare")
        _operation_id(payload["transition_id"])
        if (
            not _sequence(payload["sequence"])
            or not _sequence(payload["from_sequence"])
            or not _state_digest(payload["from_hash"])
            or (payload["from_sequence"], payload["from_hash"], payload["sequence"])
            != (commit["sequence"], commit["state_hash"], commit["sequence"] + 1)
        ):
            raise ValueError("Invalid prepared predecessor")
        puts, deletes = _delta(payload["puts"], payload["deletes"])
        if (
            puts != payload["puts"]
            or deletes != payload["deletes"]
            or not re.fullmatch(r"[a-f0-9]{64}", payload["state_hash"])
        ):
            raise ValueError("Noncanonical prepare")

    def _append_record(self, payload, previous):
        raw = _canonical(_envelope(payload, previous)) + b"\n"
        if (
            len(raw) > MAX_LINE_BYTES
            or os.fstat(self._fds["witness"]).st_size + len(raw) > MAX_JOURNAL_BYTES
        ):
            raise AuthorityCapacity(
                "Authority witness capacity reached; history retained"
            )
        self._check_files()
        offset = 0
        while offset < len(raw):
            written = os.write(self._fds["witness"], raw[offset:])
            if written <= 0:
                raise OSError("Authority witness write made no progress")
            offset += written
        os.fsync(self._fds["witness"])
        return _hash({"payload": payload, "previous": previous})

    def _sync_database(self):
        os.fsync(self._fds["database"])
        fd = os.open(
            self._paths["database"].parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
        )
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _write_database(self, conn, prepare):
        for key in prepare["deletes"]:
            conn.execute("DELETE FROM authority_records WHERE key=?", (key,))
        conn.executemany(
            "INSERT INTO authority_records VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
            [
                (key, _canonical(value).decode())
                for key, value in prepare["puts"].items()
            ],
        )
        conn.execute(
            "UPDATE authority_meta SET sequence=?,state_hash=?,transition_id=? WHERE id=1",
            (prepare["sequence"], prepare["state_hash"], prepare["transition_id"]),
        )
        current, _ = self._state(conn)
        if current.state_hash != prepare["state_hash"]:
            raise AuthorityUncertain(
                "Authority SQL mutation differs from prepared intent"
            )
        self._check_files()
        conn.commit()
        self._sync_database()

    def _verified(self, conn):
        recovered = []
        while True:
            conn.execute("BEGIN IMMEDIATE")
            snapshot, transition = self._state(conn)
            history = self._history()
            pending = history.pending
            expected = history.commit if pending is None else pending
            current_matches = (snapshot.sequence, snapshot.state_hash, transition) == (
                expected["sequence"],
                expected["state_hash"],
                expected["transition_id"],
            )
            previous_matches = pending is not None and (
                snapshot.sequence,
                snapshot.state_hash,
                transition,
            ) == (
                history.commit["sequence"],
                history.commit["state_hash"],
                history.commit["transition_id"],
            )
            if not current_matches and not previous_matches:
                raise AuthorityUncertain(
                    "Authority restore/rewind or unwitnessed SQL state detected"
                )
            if pending is not None and previous_matches:
                target = _apply(snapshot.records, pending["puts"], pending["deletes"])
                if _hash(target) != pending["state_hash"]:
                    raise AuthorityUncertain(
                        "Prepared delta does not produce its state hash"
                    )
            # A partial final append can be removed only after cross-store
            # agreement. A complete corrupt record or rewind preserves evidence.
            if history.torn_tail:
                os.ftruncate(self._fds["witness"], history.valid_end)
            os.fsync(self._fds["witness"])
            if pending is None:
                self._sync_database()
                return AuthoritySnapshot(
                    snapshot.sequence,
                    snapshot.state_hash,
                    snapshot.records,
                    tuple(recovered),
                ), history
            if previous_matches:
                self._write_database(conn, pending)
            else:
                conn.rollback()
                self._sync_database()
            self._append_record(
                {
                    "kind": "COMMIT",
                    "sequence": pending["sequence"],
                    "state_hash": pending["state_hash"],
                    "transition_id": pending["transition_id"],
                },
                history.head,
            )
            recovered.append(pending["transition_id"])

    def load(self):
        with self._operation() as conn:
            snapshot, _ = self._verified(conn)
            return snapshot

    @contextmanager
    def frozen_snapshot(self):
        """Hold verified authority storage against mutations while an offline backup captures both stores.

        This grants no actor authority. Callers must reject live concessions and
        must not call other journal operations while holding this context.
        """
        failure = None
        with self._operation() as conn:
            snapshot, _ = self._verified(conn)
            try:
                yield snapshot
            except BaseException as exc:
                # The external copy can fail without implying corrupt authority.
                failure = (exc, exc.__traceback__)
        if failure is not None:
            raise failure[0].with_traceback(failure[1])

    def commit(self, expected, *, transition_id, puts, deletes=()):
        _operation_id(transition_id)
        puts, deletes = _delta(puts, deletes)
        if not isinstance(expected, AuthoritySnapshot):
            raise TypeError("Expected a verified authority snapshot")
        if not _sequence(expected.sequence) or not _state_digest(expected.state_hash):
            raise ValueError("Invalid expected authority sequence/hash")
        intent = {
            "from_sequence": expected.sequence,
            "from_hash": expected.state_hash,
            "puts": puts,
            "deletes": deletes,
        }
        with self._operation() as conn:
            current, history = self._verified(conn)
            prior = history.receipts.get(transition_id)
            if prior is not None:
                if prior[0] != _hash(intent):
                    raise AuthorityConflict(
                        "Transition ID already identifies another intent"
                    )
                return prior[1]
            if (current.sequence, current.state_hash) != (
                expected.sequence,
                expected.state_hash,
            ):
                raise AuthorityConflict("Authority state changed before mutation")
            if current.sequence == MAX_SEQUENCE:
                raise AuthorityCapacity("Authority sequence exhausted")
            state = _apply(current.records, puts, deletes)
            prepare = {
                "kind": "PREPARE",
                **intent,
                "sequence": current.sequence + 1,
                "state_hash": _hash(state),
                "transition_id": transition_id,
            }
            commit = {
                key: prepare[key] for key in ("sequence", "state_hash", "transition_id")
            }
            commit["kind"] = "COMMIT"
            prepared_head = _hash({"payload": prepare, "previous": history.head})
            prepare_bytes = len(_canonical(_envelope(prepare, history.head))) + 1
            commit_bytes = len(_canonical(_envelope(commit, prepared_head))) + 1
            if (
                prepare_bytes > MAX_LINE_BYTES
                or os.fstat(self._fds["witness"]).st_size + prepare_bytes + commit_bytes
                > MAX_JOURNAL_BYTES
            ):
                raise AuthorityCapacity(
                    "Reserve capacity for both prepare and commit before writing"
                )
            head = self._append_record(prepare, history.head)
            self._write_database(conn, prepare)
            self._append_record(commit, head)
            return CommitReceipt(
                commit["sequence"], commit["state_hash"], transition_id, True
            )
