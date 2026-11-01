"""Trusted host composition of witnessed reservation, kernel domain and exec gate.

This in-process broker has no network/IPC endpoint or production enrollment.
Its first concrete payload profile is readonly stdlib analysis. It never makes
an LLM turn, accepts product work or grants authority from a storage receipt.
"""

import hashlib
import json
import os
import select
import threading
import time
from dataclasses import asdict, dataclass
from uuid import uuid4

from backend.runtime.authority_journal import AuthorityConflict, AuthorityUncertain
from backend.runtime.broker_profile import AnalysisCapsule
from backend.runtime.contracts import command_key, text
from backend.runtime.execution_domain import DomainIdentity, ExecutionDomain
from backend.runtime.peer_process import NamespaceIdentity, _pidfd, start_ticks


def _digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


@dataclass(frozen=True)
class PeerStart:
    operation_id: str
    state: str
    fresh: bool
    child: object = None


class PeerTransport:
    """Post-gate data endpoints. The broker retains pidfd/reaping ownership."""

    def __init__(self, owner):
        self._wait = owner.wait
        streams = []
        try:
            for stream, mode in (
                (owner.stdin, "wb"),
                (owner.stdout, "rb"),
                (owner.stderr, "rb"),
            ):
                streams.append(os.fdopen(os.dup(stream.fileno()), mode, buffering=0))
        except BaseException:
            for stream in streams:
                stream.close()
            raise
        self.stdin, self.stdout, self.stderr = streams

    def wait(self, *, timeout=5):
        return self._wait(timeout=timeout)

    def close_handles(self):
        for stream in (self.stdin, self.stdout, self.stderr):
            stream.close()


class PeerBroker:
    """One externally supplied, non-reused domain for one original attempt.

    ``run_peer`` owns reserve→spawn→global publication→concrete local bind→G.
    Callers receive a transport only after G and can only recover a receipt on
    retry. ``revoke`` withdraws G before waiting for SQL/constructors. Global
    recovery needs only the journal/domain, never the original project DB.
    Complete actor-origin and endpoint authentication remain deployment work.
    """

    def __init__(self, journal, domain):
        self.journal, self.domain = journal, domain
        self.grant_id = _digest(asdict(domain.identity))
        self._owner = uuid4().hex
        self._withdrawn = threading.Event()
        self._gate_lock = threading.RLock()
        self._decision_lock = threading.Lock()
        self._physical_lock = threading.Lock()
        self._retire_lock = threading.Lock()
        self._physical_closed = None
        self._children = {}
        self._gate_observed = {}

    @property
    def _grant_key(self):
        return "broker:grant:" + self.grant_id

    def _reserve(self, admission, operation_id, intent, peer_id):
        snapshot = self.journal.load()
        active = snapshot.records.get("broker:active")
        grant = snapshot.records.get(self._grant_key)
        attempt_key = "broker:attempt:" + _digest(
            {
                key: admission[key]
                for key in ("database_identity", "attempt_id", "fence")
            }
        )
        reservation = snapshot.records.get(attempt_key)
        if reservation is not None and reservation != self.grant_id:
            raise AuthorityConflict(
                "Original attempt already reserved or retired; a new source attempt is required"
            )
        if reservation is not None and grant is None:
            raise AuthorityUncertain("Attempt reference lost its original domain grant")
        if grant is not None:
            if active != self.grant_id:
                raise AuthorityUncertain("Active concession reference differs")
            if grant["owner"] != self._owner or grant["state"] != "active":
                raise AuthorityConflict(
                    "Execution domain has an earlier owner or tombstone"
                )
            if (grant["database_identity"], grant["attempt_id"], grant["fence"]) != (
                admission["database_identity"],
                admission["attempt_id"],
                admission["fence"],
            ):
                raise AuthorityConflict("Global domain belongs to another attempt")
            if grant["workspace_binding"] != asdict(admission["binding"]):
                raise AuthorityConflict("Global source admission differs")
        else:
            if active is not None:
                raise AuthorityConflict("Another global domain concession is active")
            fence = snapshot.records.get("broker:fence", 0)
            if type(fence) is not int or not 0 <= fence < 2**63 - 1:
                raise AuthorityUncertain("Invalid global authority generation")
            grant = {
                "protocol": 1,
                "owner": self._owner,
                "owner_pid": os.getpid(),
                "owner_start_ticks": start_ticks(os.getpid()),
                "state": "active",
                "global_fence": fence + 1,
                "domain_path": str(self.domain.path),
                "domain_identity": asdict(self.domain.identity),
                "workspace_binding": asdict(admission["binding"]),
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
            }
        operation = {
            "protocol": 1,
            "grant_id": self.grant_id,
            "peer_id": peer_id,
            "intent": intent,
            "state": "starting",
            "namespace": None,
            "gate_sent": False,
            "exit_code": None,
        }
        self.journal.commit(
            snapshot,
            transition_id="broker-reserve:" + operation_id,
            puts={
                self._grant_key: grant,
                "broker:active": self.grant_id,
                "broker:fence": grant["global_fence"],
                attempt_key: self.grant_id,
                "broker:op:" + operation_id: operation,
            },
        )
        return operation

    def _update(self, operation_id, **changes):
        snapshot = self.journal.load()
        grant = snapshot.records[self._grant_key]
        if (
            grant["owner"] != self._owner
            or grant["state"] != "active"
            or snapshot.records.get("broker:active") != self.grant_id
        ):
            raise AuthorityConflict(
                "Global concession no longer authorizes publication"
            )
        key = "broker:op:" + operation_id
        operation = {**snapshot.records[key], **changes}
        self.journal.commit(
            snapshot,
            transition_id="broker-" + operation["state"] + ":" + operation_id,
            puts={key: operation},
        )
        return operation

    @staticmethod
    def _info(fd):
        data = b""
        deadline = time.monotonic() + 3
        while len(data) < 4096:
            if not select.select([fd], [], [], max(0, deadline - time.monotonic()))[0]:
                raise AuthorityUncertain("Peer identity startup deadline exceeded")
            chunk = os.read(fd, 4096 - len(data))
            if not chunk:
                raise AuthorityUncertain("Peer exited before namespace identity")
            data += chunk
            try:
                value = json.loads(data)
                if not isinstance(value, dict):
                    raise TypeError("Invalid namespace info")
                return value
            except json.JSONDecodeError:
                continue
        raise AuthorityUncertain("Peer identity record too large")

    def run_peer(self, registry, peer_id, *, operation_key, code):
        command_key(operation_key)
        text(code, "analysis code", 64000)
        with self._gate_lock:
            original = registry.inspect(peer_id)
            operation_id = _digest(
                {
                    "origin": original["database_identity"],
                    "peer": peer_id,
                    "key": operation_key,
                }
            )
            intent = _digest({"code": code, "profile": "readonly-stdlib-analysis-v1"})
            existing = self.journal.load().records.get("broker:op:" + operation_id)
            if existing is not None:
                if existing["intent"] != intent:
                    raise AuthorityConflict(
                        "Operation key identifies different analysis"
                    )
                return PeerStart(operation_id, existing["state"], False)
            if self._withdrawn.is_set():
                raise AuthorityConflict("Broker admission withdrawn")
            admission = registry.admission(peer_id)
            if admission["binding"] is None or admission["kind"] != "command":
                raise AuthorityConflict(
                    "Analysis broker requires an admitted command peer"
                )
            self._reserve(admission, operation_id, intent, peer_id)
            self._gate_observed[operation_id] = False
            read_fd = write_fd = None
            try:
                if not self._children:
                    self.domain.limit(pids=128, memory_bytes=512 * 1024**2)
                read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
                with AnalysisCapsule(admission["binding"], code, write_fd) as profile:
                    if self._withdrawn.is_set():
                        raise AuthorityConflict("Broker admission withdrawn")
                    child = self.domain.spawn(
                        profile.argv, env=profile.env, pass_fds=profile.pass_fds
                    )
                self._children[operation_id] = child
                os.close(write_fd)
                write_fd = None
                info = self._info(read_fd)
                pid = info.get("child-pid")
                if type(pid) is not int or pid <= 1:
                    raise AuthorityUncertain("Invalid namespace init")
                deadline = time.monotonic() + 2
                while True:
                    try:
                        identity = NamespaceIdentity.capture(
                            pid, expected_parent=child.pid
                        )
                        if identity.init_namespace != info.get("pid-namespace"):
                            raise AuthorityUncertain(
                                "Namespace differs from constructor"
                            )
                        break
                    except (OSError, RuntimeError):
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(0.01)
                self._update(
                    operation_id, state="published", namespace=asdict(identity)
                )
                registry.bind(peer_id, identity)
                # Persist intent before the effect. A lost G/ack is never replayed.
                self._update(operation_id, state="dispatching", gate_sent=None)
                with self._decision_lock:
                    if self._withdrawn.is_set():
                        raise AuthorityConflict("Broker revoked before gate")
                    os.set_blocking(child.stdin.fileno(), False)
                    self._gate_observed[operation_id] = None
                    if os.write(child.stdin.fileno(), b"G") != 1:
                        raise AuthorityUncertain("Gate write incomplete")
                    self._gate_observed[operation_id] = True
                self._update(operation_id, state="released", gate_sent=True)
                return PeerStart(operation_id, "released", True, PeerTransport(child))
            except BaseException:
                revoked = self._withdrawn.is_set()
                with self._decision_lock:
                    self._withdrawn.set()
                try:
                    self._physical()
                except (OSError, RuntimeError):
                    pass
                if revoked:
                    raise AuthorityConflict(
                        "Broker withdrawn during peer startup"
                    ) from None
                raise
            finally:
                for fd in (read_fd, write_fd):
                    if fd is not None:
                        os.close(fd)

    def _physical(self):
        with self._physical_lock:
            if self._physical_closed is None:
                self._physical_closed = self.domain.retire()
            return self._physical_closed

    def revoke(self):
        with self._decision_lock:
            self._withdrawn.set()
        with self._retire_lock:
            # Physical closure cannot wait behind local/global SQL publication.
            try:
                self._physical()
            except (OSError, RuntimeError):
                # Another recovery may already have a durable retirement receipt.
                snapshot = self.journal.load()
                grant = snapshot.records.get(self._grant_key)
                if grant is not None and grant["state"] == "retired":
                    return grant
                raise
            if not self._gate_lock.acquire(timeout=5):
                raise AuthorityUncertain(
                    "Broker constructors/local binds did not drain"
                )
            try:
                for child in self._children.values():
                    try:
                        child.wait(timeout=3)
                    finally:
                        child.close_handles()
                snapshot = self.journal.load()
                grant = snapshot.records.get(self._grant_key)
                if grant is None:
                    return {"state": "retired", "unused": True}
                if grant["state"] == "retired":
                    return grant
                if snapshot.records.get("broker:active") != self.grant_id:
                    raise AuthorityUncertain("Cannot release another active concession")
                puts = {
                    self._grant_key: {
                        **grant,
                        "state": "retired",
                        "domain_removed": True,
                    },
                    "broker:active": None,
                }
                for key, operation in snapshot.records.items():
                    if (
                        key.startswith("broker:op:")
                        and operation["grant_id"] == self.grant_id
                    ):
                        child = self._children.get(key.removeprefix("broker:op:"))
                        puts[key] = {
                            **operation,
                            "state": "closed",
                            "gate_sent": self._gate_observed.get(
                                key.removeprefix("broker:op:"), operation["gate_sent"]
                            ),
                            "exit_code": child._status
                            if child
                            else operation["exit_code"],
                        }
                self.journal.commit(
                    snapshot, transition_id="broker-retire:" + self.grant_id, puts=puts
                )
                return puts[self._grant_key]
            finally:
                self._gate_lock.release()

    @classmethod
    def recover(cls, journal, grant_id):
        """Retire globally known actors without opening or recreating project DB."""
        snapshot = journal.load()
        key = "broker:grant:" + grant_id
        grant = snapshot.records[key]
        if grant["state"] == "retired":
            return grant
        if snapshot.records.get("broker:active") != grant_id:
            raise AuthorityUncertain("Recovery concession reference differs")
        cls._require_dead_owner(grant)
        with ExecutionDomain.open(
            grant["domain_path"], expected=DomainIdentity(**grant["domain_identity"])
        ) as domain:
            domain.retire()
        snapshot = journal.load()
        grant = snapshot.records[key]
        if grant["state"] == "retired":
            return grant
        if snapshot.records.get("broker:active") != grant_id:
            raise AuthorityUncertain("Recovery cannot release another concession")
        puts = {
            key: {**grant, "state": "retired", "domain_removed": True},
            "broker:active": None,
        }
        for op_key, operation in snapshot.records.items():
            if op_key.startswith("broker:op:") and operation["grant_id"] == grant_id:
                puts[op_key] = {**operation, "state": "closed"}
        journal.commit(snapshot, transition_id="broker-recover:" + grant_id, puts=puts)
        return puts[key]

    @staticmethod
    def _require_dead_owner(grant):
        pid = grant.get("owner_pid")
        ticks = grant.get("owner_start_ticks")
        if type(pid) is not int or pid <= 1 or type(ticks) is not int or ticks <= 0:
            raise AuthorityUncertain("Broker owner identity is incomplete")
        try:
            fd = _pidfd(pid)
        except ProcessLookupError:
            return
        try:
            poller = select.poll()
            poller.register(fd, select.POLLIN | select.POLLHUP)
            if poller.poll(0):
                return
            try:
                current = start_ticks(pid)
            except (FileNotFoundError, ProcessLookupError):
                if poller.poll(100):
                    return
                raise AuthorityUncertain("Broker owner visibility is unknown") from None
            if current != ticks:
                return
            raise AuthorityConflict(
                "Original broker is still alive; revoke through its control channel"
            )
        finally:
            os.close(fd)
