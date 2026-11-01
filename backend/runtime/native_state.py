"""Private retained native data; witnessed identities never authorize a replay."""

import hashlib
import json
import os
import stat
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from backend.runtime.authority_journal import AuthorityConflict, AuthorityUncertain
from backend.runtime.contracts import text


def _origin(admission):
    return {
        **{
            key: admission[key]
            for key in (
                "database_identity",
                "attempt_id",
                "fence",
                "project_id",
                "task_id",
                "context_version",
            )
        },
        "workspace_binding": asdict(admission["binding"]),
    }


def _directory(fd):
    info = os.fstat(fd)
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise ValueError("Native state directory must be private and owned")
    return info.st_dev, info.st_ino


def _origin_key(origin):
    return (
        "broker:native-origin:"
        + hashlib.sha256(
            json.dumps(origin, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


@dataclass(frozen=True)
class NativeState:
    state_id: str
    authority_id: str
    path: str
    root_device: int
    root_inode: int
    home_device: int
    home_inode: int

    @property
    def key(self):
        return "broker:native-state:" + self.state_id

    @classmethod
    def provision(cls, journal, registry, peer_id, path):
        """Explicit data creation, separate from reopening or authority bootstrap.

        A failed/uncertain journal commit can leave an orphan directory. Never
        silently adopt/delete it: provision elsewhere or reconcile its receipt.
        """
        admission = registry.admission(peer_id)
        if admission["kind"] != "native" or admission["binding"] is None:
            raise AuthorityConflict("Native state requires original source admission")
        path = Path(path)
        path = path.parent.resolve(strict=True) / path.name
        source = admission["binding"].workspace
        if path.is_relative_to(source) or Path(source).is_relative_to(path):
            raise ValueError("Native state must stay outside source")
        snapshot = journal.load()
        origin = _origin(admission)
        if snapshot.records.get(_origin_key(origin)) is not None:
            raise AuthorityConflict(
                "Original attempt already owns native state; reopen its receipt"
            )
        path.mkdir(mode=0o700)
        home = path / "home"
        home.mkdir(mode=0o700)
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        root_fd = os.open(path, flags)
        try:
            home_fd = os.open("home", flags, dir_fd=root_fd)
            try:
                root_identity, home_identity = _directory(root_fd), _directory(home_fd)
                os.fsync(home_fd)
                os.fsync(root_fd)
            finally:
                os.close(home_fd)
        finally:
            os.close(root_fd)
        parent_fd = os.open(path.parent, flags)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        state = cls(
            uuid4().hex, journal.authority_id, str(path), *root_identity, *home_identity
        )
        journal.commit(
            snapshot,
            transition_id="native-state-create:" + state.state_id,
            puts={
                _origin_key(origin): state.state_id,
                state.key: {
                    "identity": asdict(state),
                    "origin": origin,
                    "grant_id": None,
                    "operation_id": None,
                    "session_intent": None,
                    "thread_id": None,
                    "turn": None,
                },
            },
        )
        return state

    @classmethod
    def load(cls, journal, state_id):
        text(state_id, "native state id", 128)
        record = journal.load().records.get("broker:native-state:" + state_id)
        if record is None:
            raise AuthorityUncertain("Original native state receipt is missing")
        state = cls(**record["identity"])
        state._record(journal, journal.load())
        with state.opened():
            pass
        return state

    @contextmanager
    def opened(self):
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        root_fd = os.open(self.path, flags)
        try:
            if _directory(root_fd) != (self.root_device, self.root_inode):
                raise ValueError("Native state root identity changed")
            home_fd = os.open("home", flags, dir_fd=root_fd)
            try:
                if _directory(home_fd) != (self.home_device, self.home_inode):
                    raise ValueError("Native state home identity changed")
                try:
                    os.stat("auth.json", dir_fd=home_fd, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise ValueError("Native state must not contain auth.json")
                yield home_fd
            finally:
                os.close(home_fd)
        finally:
            os.close(root_fd)

    def _record(self, journal, snapshot):
        record = snapshot.records.get(self.key)
        if (
            journal.authority_id != self.authority_id
            or record is None
            or record["identity"] != asdict(self)
            or snapshot.records.get(_origin_key(record["origin"])) != self.state_id
        ):
            raise AuthorityUncertain("Original native state identity differs")
        return record

    def reservation(self, journal, snapshot, admission, grant_id, operation_id):
        record = self._record(journal, snapshot)
        if record["origin"] != _origin(admission) or record["grant_id"] not in (
            None,
            grant_id,
        ):
            raise AuthorityConflict("Native state belongs to another original attempt")
        previous = record["operation_id"]
        if (
            previous is not None
            and snapshot.records.get("broker:op:" + previous, {}).get(
                "execution_closed"
            )
            is not True
        ):
            raise AuthorityConflict("Previous native state writer is not proved closed")
        # Validate before reserving, and again when opening the mount descriptor.
        with self.opened():
            pass
        return {**record, "grant_id": grant_id, "operation_id": operation_id}

    def _active(self, journal, operation_id):
        snapshot = journal.load()
        record = self._record(journal, snapshot)
        operation = snapshot.records.get("broker:op:" + operation_id, {})
        grant = (
            snapshot.records.get("broker:grant:" + record["grant_id"], {})
            if record["grant_id"]
            else {}
        )
        if (
            record["operation_id"] != operation_id
            or snapshot.records.get("broker:active") != record["grant_id"]
            or grant.get("state") != "active"
            or operation.get("execution_closed")
            or operation.get("gate_sent") is not True
        ):
            raise AuthorityConflict("Native state has no original live writer")
        return snapshot, record

    def prepare_thread(
        self,
        journal,
        operation_id,
        *,
        model,
        catalog_hash,
        developer_instructions,
        resume_thread_id,
    ):
        snapshot, record = self._active(journal, operation_id)
        intent = {
            "model": model,
            "catalog_hash": catalog_hash,
            "instructions_sha256": hashlib.sha256(
                (developer_instructions or "").encode()
            ).hexdigest(),
        }
        if record["session_intent"] is not None:
            if (
                record["session_intent"] != intent
                or record["thread_id"] != resume_thread_id
                or resume_thread_id is None
            ):
                raise AuthorityConflict(
                    "Native session intent differs or its thread receipt is missing"
                )
            return
        if resume_thread_id is not None:
            raise AuthorityConflict("Native resume has no original thread receipt")
        journal.commit(
            snapshot,
            transition_id="native-thread-intent:" + self.state_id,
            puts={self.key: {**record, "session_intent": intent}},
        )

    def bind_thread(self, journal, operation_id, thread_id):
        text(thread_id, "native thread id", 256)
        snapshot, record = self._active(journal, operation_id)
        if record["session_intent"] is None or record["thread_id"] not in (
            None,
            thread_id,
        ):
            raise AuthorityConflict("Native thread differs from original intent")
        if record["thread_id"] is None:
            journal.commit(
                snapshot,
                transition_id="native-thread-bind:" + self.state_id,
                puts={self.key: {**record, "thread_id": thread_id}},
            )

    def reserve_turn(self, journal, operation_id, input_text):
        snapshot, record = self._active(journal, operation_id)
        if record["thread_id"] is None or record["turn"] is not None:
            raise AuthorityConflict(
                "Native attempt dispatch already reserved or thread unknown; reconcile without replay"
            )
        journal.commit(
            snapshot,
            transition_id="native-turn-reserve:" + self.state_id,
            puts={
                self.key: {
                    **record,
                    "turn": {
                        "operation_id": operation_id,
                        "input_sha256": hashlib.sha256(input_text.encode()).hexdigest(),
                    },
                }
            },
        )
