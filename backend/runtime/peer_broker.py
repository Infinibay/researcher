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
from pathlib import Path
from uuid import uuid4

from backend.runtime.authority_journal import (
    AuthorityBusy,
    AuthorityConflict,
    AuthorityUncertain,
)
from backend.runtime.broker_profile import (
    AnalysisCapsule,
    CodexAsset,
    KenCapsule,
    NativeCapsule,
    NativeProxyCapsule,
)
from backend.runtime.contracts import command_key, text
from backend.runtime.egress_channel import EgressChannel
from backend.runtime.egress_proxy import EgressPolicy, TunnelProxy
from backend.runtime.execution_domain import DomainIdentity, ExecutionDomain
from backend.runtime.ken_worker import KenInstallation
from backend.runtime.native_network import NativeNetwork
from backend.runtime.peer_process import (
    NamespaceIdentity,
    _pidfd,
    close_namespace,
    start_ticks,
)


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
class BrokerLimits:
    """Trusted host policy for all siblings, selected before any reservation."""

    pids: int = 128
    memory_bytes: int = 512 * 1024**2

    def __post_init__(self):
        if (
            type(self.pids) is not int
            or not 1 <= self.pids <= 1024
            or type(self.memory_bytes) is not int
            or not 64 * 1024**2 <= self.memory_bytes <= 8 * 1024**3
        ):
            raise ValueError("Finite bounded broker limits required")


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

    def __init__(self, journal, domain, *, limits=None):
        if limits is None:
            limits = BrokerLimits()
        if not isinstance(limits, BrokerLimits):
            raise TypeError("Host-selected BrokerLimits required")
        self._limits = limits
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
        self._namespaces = {}
        self._projection_source = None
        self._egress = {}

    def withdraw(self):
        """Withdraw new G decisions immediately; not a durable closure receipt."""
        with self._decision_lock:
            self._withdrawn.set()
            channels = tuple(self._egress.values())
        for channel in channels:
            channel.withdraw()

    @property
    def _grant_key(self):
        return "broker:grant:" + self.grant_id

    def _reserve(
        self, admission, operation_id, intent, peer_id, *, runtime_manifest=None
    ):
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
            if grant.get("limits") != asdict(self._limits):
                raise AuthorityConflict("Shared broker resource policy changed")
        else:
            if active is not None:
                raise AuthorityConflict("Another global domain concession is active")
            fence = snapshot.records.get("broker:fence", 0)
            if type(fence) is not int or not 0 <= fence < 2**63 - 1:
                raise AuthorityUncertain("Invalid global authority generation")
            grant = {
                "protocol": 1,
                "source_database": admission["database_path"],
                "owner": self._owner,
                "owner_pid": os.getpid(),
                "owner_start_ticks": start_ticks(os.getpid()),
                "state": "active",
                "global_fence": fence + 1,
                "domain_path": str(self.domain.path),
                "domain_identity": asdict(self.domain.identity),
                "workspace_binding": asdict(admission["binding"]),
                "limits": asdict(self._limits),
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
            "kind": admission["kind"],
            "intent": intent,
            "state": "starting",
            "namespace": None,
            "gate_sent": False,
            "exit_code": None,
            **(
                {"runtime_manifest": runtime_manifest}
                if runtime_manifest is not None
                else {}
            ),
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
        return self._run(registry, peer_id, operation_key=operation_key, code=code)

    def run_ken(
        self,
        registry,
        peer_id,
        *,
        operation_key,
        installation,
        model_cache=None,
        mode="mcp",
    ):
        if not isinstance(installation, KenInstallation) or mode not in (
            "mcp",
            "prepare",
        ):
            raise TypeError(
                "Inspected Ken installation and fixed operation mode required"
            )
        if installation.assets and model_cache is None:
            raise ValueError("Pinned public Ken model cache required")
        cache = (
            Path(model_cache).resolve(strict=True) if model_cache is not None else None
        )
        return self._run(
            registry,
            peer_id,
            operation_key=operation_key,
            ken=installation,
            model_cache=cache,
            ken_mode=mode,
        )

    def run_native(
        self, registry, peer_id, *, operation_key, asset, network=None, egress=None
    ):
        if not isinstance(asset, CodexAsset):
            raise TypeError("Native launch requires an inspected Codex asset")
        if network is not None and not isinstance(network, NativeNetwork):
            raise TypeError("Native network requires inspected public inputs")
        if egress is not None and (
            not isinstance(egress, EgressPolicy) or network is None
        ):
            raise TypeError(
                "Private native egress requires a policy and public network inputs"
            )
        return self._run(
            registry,
            peer_id,
            operation_key=operation_key,
            asset=asset,
            network=network,
            egress=egress,
        )

    def _run(
        self,
        registry,
        peer_id,
        *,
        operation_key,
        code=None,
        asset=None,
        network=None,
        egress=None,
        ken=None,
        model_cache=None,
        ken_mode="mcp",
    ):
        command_key(operation_key)
        if asset is None and ken is None:
            text(code, "analysis code", 64000)
        kind = "ken" if ken is not None else ("command" if asset is None else "native")
        with self._gate_lock:
            original = registry.inspect(peer_id)
            operation_id = _digest(
                {
                    "origin": original["database_identity"],
                    "peer": peer_id,
                    "key": operation_key,
                }
            )
            manifest = (
                {"code": code, "profile": "readonly-stdlib-analysis-v1"}
                if asset is None
                else {
                    "profile": "readonly-native-codex-connect-v1"
                    if egress is not None
                    else "readonly-native-codex-v1",
                    "asset": asdict(asset),
                    "profile_sha256": hashlib.sha256(
                        Path(__file__).with_name("broker_profile.py").read_bytes()
                    ).hexdigest(),
                    "gate_sha256": hashlib.sha256(
                        Path(__file__).with_name("peer_payload.py").read_bytes()
                    ).hexdigest(),
                    **(
                        {
                            "network": asdict(network),
                            "network_policy_sha256": hashlib.sha256(
                                Path(__file__)
                                .with_name("native_network.py")
                                .read_bytes()
                            ).hexdigest(),
                        }
                        if network is not None
                        else {}
                    ),
                    **(
                        {
                            "egress": asdict(egress),
                            "egress_code_sha256": {
                                name: hashlib.sha256(
                                    Path(__file__).with_name(name).read_bytes()
                                ).hexdigest()
                                for name in (
                                    "proxy_payload.py",
                                    "egress_proxy.py",
                                    "egress_channel.py",
                                )
                            },
                            "destination_code_sha256": hashlib.sha256(
                                Path(__file__)
                                .parents[1]
                                .joinpath("network_destinations.py")
                                .read_bytes()
                            ).hexdigest(),
                        }
                        if egress is not None
                        else {}
                    ),
                }
            )
            if ken is not None:
                manifest = {
                    "profile": "readonly-published-ken-v1",
                    "mode": ken_mode,
                    "installation": {
                        "executable": str(ken.executable),
                        "tool_root": str(ken.tool_root),
                        "python_root": str(ken.python_root),
                        "assets": ken.assets,
                    },
                    "model_cache": str(model_cache)
                    if model_cache is not None
                    else None,
                    "code_sha256": {
                        name: hashlib.sha256(
                            Path(__file__).with_name(name).read_bytes()
                        ).hexdigest()
                        for name in (
                            "ken_worker.py",
                            "broker_profile.py",
                            "peer_payload.py",
                        )
                    },
                }
            manifest["limits"] = asdict(self._limits)
            intent = _digest(manifest)
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
            if admission["binding"] is None or admission["kind"] != kind:
                raise AuthorityConflict(
                    "Broker profile requires its original admitted peer kind"
                )
            self._reserve(
                admission,
                operation_id,
                intent,
                peer_id,
                runtime_manifest=manifest
                if asset is not None or ken is not None
                else None,
            )
            self._projection_source = registry
            self._gate_observed[operation_id] = False
            read_fd = write_fd = None
            try:
                if not self._children:
                    self.domain.limit(**asdict(self._limits))
                read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
                channel = None
                if egress is not None:
                    channel = EgressChannel(TunnelProxy(egress))
                    with self._decision_lock:
                        admitted = not self._withdrawn.is_set()
                        if admitted:
                            self._egress[operation_id] = channel
                    if not admitted:
                        channel.close()
                        raise AuthorityConflict(
                            "Broker withdrew before channel admission"
                        )
                capsule = (
                    KenCapsule
                    if ken is not None
                    else (
                        NativeProxyCapsule
                        if egress is not None
                        else (AnalysisCapsule if asset is None else NativeCapsule)
                    )
                )
                with capsule(
                    admission["binding"],
                    ken if ken is not None else (code if asset is None else asset),
                    write_fd,
                    **({"network": network} if network is not None else {}),
                    **({"channel": channel} if channel is not None else {}),
                    **(
                        {"model_cache": model_cache, "mode": ken_mode}
                        if ken is not None
                        else {}
                    ),
                ) as profile:
                    if self._withdrawn.is_set():
                        raise AuthorityConflict("Broker admission withdrawn")
                    child = self.domain.spawn(
                        profile.argv, env=profile.env, pass_fds=profile.pass_fds
                    )
                    # Retain the born child before any descriptor/context cleanup
                    # can fail. Domain retirement alone is not host-side reaping.
                    self._children[operation_id] = child
                if channel is not None:
                    channel.close_child_end()
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
                self._namespaces[operation_id] = identity
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
                self.withdraw()
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
        self.withdraw()
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
                for channel in self._egress.values():
                    channel.close()
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
                            "execution_closed": True,
                            "closure_reason": "domain_retired",
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

    def close_peer(self, operation_id):
        """Stop one original namespace before waiting for publication/SQL.

        Concession remains active for siblings. This owner retains reaping even
        after the data client closes. Global retirement still belongs to revoke.
        """
        child = self._children.get(operation_id)
        identity = self._namespaces.get(operation_id)
        if child is None or identity is None:
            raise AuthorityConflict("Peer is not owned by this live broker")
        channel = self._egress.get(operation_id)
        if channel is not None:
            channel.withdraw()
        reason = close_namespace(identity, timeout=3)
        child.wait(timeout=3)
        if channel is not None:
            channel.close()
        if not self._gate_lock.acquire(blocking=False):
            raise AuthorityBusy(
                "Peer physically closed; publication must drain before receipt"
            )
        try:
            child.close_handles()
            snapshot = self.journal.load()
            key = "broker:op:" + operation_id
            operation = snapshot.records[key]
            if operation.get("execution_closed") is True:
                return operation
            grant = snapshot.records[self._grant_key]
            if (
                grant["owner"] != self._owner
                or grant["state"] != "active"
                or operation["grant_id"] != self.grant_id
            ):
                raise AuthorityUncertain("Peer retirement authority differs")
            closed = {
                **operation,
                "state": "closed",
                "execution_closed": True,
                "closure_reason": reason,
                "gate_sent": self._gate_observed.get(
                    operation_id, operation["gate_sent"]
                ),
                "exit_code": child._status,
            }
            self.journal.commit(
                snapshot,
                transition_id="broker-close-peer:" + operation_id,
                puts={key: closed},
            )
            return closed
        finally:
            self._gate_lock.release()

    def project_closed(self, *, operation_id=None):
        """Record proved closure in the original source, without another signal.

        A cached registry or durable locator supplies only the source location.
        Read proof from the verified journal, never a caller-supplied closed flag. All
        matched local rows/events commit together or remain visibly incomplete.
        """
        snapshot = self.journal.load()
        grant = snapshot.records.get(self._grant_key)
        if grant is None and operation_id is None:
            return ()
        if grant is None or grant["owner"] != self._owner:
            raise AuthorityConflict("No original broker grant to project")
        return self._project_snapshot(
            snapshot, self.grant_id, self._projection_source, operation_id
        )

    @classmethod
    def project_recovered(cls, journal, grant_id):
        """Project an already-proved global retirement; never recover or signal.

        Separate from recover so losing the source cannot prevent global Stop.
        A locator does not authorize another source or initialize missing state.
        """
        snapshot = journal.load()
        grant = snapshot.records.get("broker:grant:" + grant_id)
        if (
            grant is None
            or grant["state"] != "retired"
            or grant.get("domain_removed") is not True
        ):
            raise AuthorityConflict("Global retirement is not proved")
        return cls._project_snapshot(snapshot, grant_id, None, None)

    @staticmethod
    def _project_snapshot(snapshot, grant_id, source, operation_id):
        grant = snapshot.records["broker:grant:" + grant_id]
        operations = [
            operation
            for key, operation in snapshot.records.items()
            if key.startswith("broker:op:")
            and operation["grant_id"] == grant_id
            and (operation_id is None or key == "broker:op:" + operation_id)
        ]
        if operation_id is not None and (
            len(operations) != 1 or operations[0].get("execution_closed") is not True
        ):
            raise AuthorityConflict("Original operation has no verified closure")
        closed = [op for op in operations if op.get("execution_closed") is True]
        if not closed:
            return ()
        if source is None:
            from backend.runtime.peer_registry import PeerRegistry
            from backend.runtime.sqlite_runs import SQLiteRunStore

            locator = grant.get("source_database")
            if not isinstance(locator, str) or not Path(locator).is_absolute():
                raise AuthorityUncertain("Original source locator is unavailable")
            source = PeerRegistry(SQLiteRunStore(locator))
        results = []
        with source.runs._transaction(write=True) as conn:
            if source._database_identity() != grant["database_identity"]:
                raise AuthorityUncertain("Closure source origin differs")
            for operation in closed:
                peer = source._row(conn, operation["peer_id"])
                source._check_origin(peer)
                attempt = conn.execute(
                    """SELECT r.project_id,r.task_id,a.fence FROM runtime_attempts a
                    JOIN runtime_runs r ON r.id=a.run_id WHERE a.id=?""",
                    (peer["attempt_id"],),
                ).fetchone()
                if (
                    grant["protocol"] != 1
                    or operation["protocol"] != 1
                    or operation["state"] != "closed"
                    or peer["protocol_version"] != 1
                    or peer["attempt_id"] != grant["attempt_id"]
                    or peer["fence"] != grant["fence"]
                    or peer["kind"] != operation.get("kind", "command")
                    or attempt is None
                    or tuple(attempt)
                    != (grant["project_id"], grant["task_id"], grant["fence"])
                ):
                    raise AuthorityUncertain("Closure source attempt differs")
                if peer["init_pid"] is None and (
                    peer["state"] == "bound" or operation["gate_sent"] is not False
                ):
                    raise AuthorityUncertain("Closure source lost its binding")
                if peer["init_pid"] is not None and (
                    operation["namespace"] is None
                    or asdict(NamespaceIdentity.from_record(peer))
                    != operation["namespace"]
                ):
                    raise AuthorityUncertain("Closure source namespace differs")
                if peer["state"] == "closed":
                    results.append(dict(peer))
                else:
                    results.append(source._closed(conn, peer, "broker_verified"))
        return tuple(results)

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
                puts[op_key] = {
                    **operation,
                    "state": "closed",
                    "execution_closed": True,
                    "closure_reason": "domain_recovered",
                }
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
