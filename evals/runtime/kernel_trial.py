"""Account-free native command evaluations using fresh product storage and real broker domains.

Only the command profile is opened: no account file, model dispatch or historical
authority is adopted. Each independent owner has its own explicit authority.
"""

import asyncio
import json
import os
import select
import sqlite3
from contextlib import asynccontextmanager, closing
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4


@dataclass
class KernelTrial:
    """Own the synthetic source and original physical domain of one diagnostic attempt."""

    root: Path
    workspace: Path
    database: Path
    authority: dict
    asset: object
    cgroup_parent: Path
    project_id: int
    task_id: int
    broker_limits: object = None

    @asynccontextmanager
    async def open(self):
        """Claim one bound source and close its broker/domain before projecting diagnostic completion."""
        from backend.runtime.authority_journal import WitnessedAuthorityJournal
        from backend.runtime.broker_stdio import AsyncPeerBroker
        from backend.runtime.contracts import RunSpec
        from backend.runtime.execution_domain import ExecutionDomain
        from backend.runtime.peer_broker import PeerBroker
        from backend.runtime.peer_registry import AttemptPeers
        from backend.runtime.sqlite_runs import SQLiteRunStore
        from backend.runtime.workspaces import WorkspaceRegistry

        self.store = SQLiteRunStore(self.database)
        binding = WorkspaceRegistry(self.database, self.root / 'sources').bind(self.project_id, 11)
        context = self.store.context_snapshot(self.project_id, self.task_id)
        self.run = self.store.admit(RunSpec(self.project_id, self.task_id, 'diagnostic', context['context_version'],
                                           'kernel-evaluation', 'Account-free native command evaluation', 'codex'), binding=binding)
        self.lease, self.peers = AttemptPeers.claim(self.store, self.project_id, self.run.run_id, 'kernel-evaluation-owner', lease_seconds=120)
        self.domain_path = self.cgroup_parent / ('researcher-eval-command-' + uuid4().hex)
        self.domain_path.mkdir(mode=0o700)
        lifecycle = {'domain_removed': False, 'all_peers_closed': False, 'model_turns': 0}
        try:
            with ExecutionDomain.open(self.domain_path) as domain, WitnessedAuthorityJournal(**self.authority) as storage:
                (self.root / 'domain.json').write_text(json.dumps({'path': str(self.domain_path), 'identity': asdict(domain.identity)}, indent=2) + '\n')
                self.storage = storage
                self.broker = PeerBroker(storage, domain, limits=self.broker_limits)
                async with AsyncPeerBroker(self.broker) as owner:
                    self.owner = owner
                    yield self
        finally:
            await self.peers.aclose()
            lifecycle.update(domain_removed=not self.domain_path.exists(), all_peers_closed=self.peers.closed())
            if lifecycle['all_peers_closed']:
                current = self.store.get(self.project_id, self.run.run_id)
                outcome = 'cancelled' if current.cancel_requested else 'failed'
                lifecycle['run_status'] = self.store.retire_inference(self.lease, outcome=outcome).status
            (self.root / 'lifecycle.json').write_text(json.dumps(lifecycle, indent=2) + '\n')

    def commands(self):
        """Open the current product's command adapter under this original broker and source lease."""
        from backend.runtime.native_commands import broker_command_executor

        return broker_command_executor(owner=self.owner, registry=self.peers.registry,
                                       lease=self.lease, workspace=self.workspace, asset=self.asset)


def prepare(root, codex_binary, cgroup_parent, *, project_id=101, task_id=1001, broker_limits=None):
    """Validate account-free host resources and create fresh source storage and independent authority."""
    from backend.runtime.bootstrap import initialize_authority, initialize_database
    from backend.runtime.broker_profile import CodexAsset
    from backend.runtime.native_commands import VERSION, _version
    from backend.runtime.peer_broker import BrokerLimits

    root = Path(root).absolute()
    if root.exists():
        raise FileExistsError('Kernel evaluation needs a NEW private trial directory')
    if broker_limits is not None and not isinstance(broker_limits, BrokerLimits):
        raise ValueError('Expected validated explicit broker limits')
    parent = Path(cgroup_parent).resolve(strict=True)
    if not parent.is_relative_to('/sys/fs/cgroup') or not os.access(parent, os.W_OK) or not {'memory', 'pids'} <= set((parent / 'cgroup.subtree_control').read_text().split()):
        raise ValueError('Supply an existing delegated cgroup v2 parent with memory/pids controllers')
    asset = CodexAsset.inspect(codex_binary)
    if _version(Path(asset.path), {'PATH': os.defpath, 'LANG': 'C.UTF-8', 'HOME': '/nonexistent', 'CODEX_HOME': '/nonexistent'}) != VERSION:
        raise ValueError('Unsupported command executable version; no peer was started')
    root.mkdir(mode=0o700, parents=True)
    workspace = root / 'sources' / 'workspace'
    workspace.mkdir(mode=0o700, parents=True)
    database = initialize_database(root / 'source.db')
    authority = initialize_authority(database_dir=root / 'authority', witness_dir=root / 'witness')
    with closing(sqlite3.connect(database)) as db, db:
        db.execute('INSERT INTO projects(id,name) VALUES(?,?)', (project_id, 'Synthetic kernel evaluation'))
        db.execute("INSERT INTO tasks(id,project_id,type,title,status) VALUES(?,?,'research','Account-free diagnostic','in_progress')", (task_id, project_id))
        db.execute("INSERT INTO repositories(id,project_id,name,local_path) VALUES(11,?,'synthetic-source',?)", (project_id, str(workspace)))
    (root / 'preparation.json').write_text(json.dumps({'format': 1, 'purpose': 'synthetic-kernel-evaluation',
        'authority': authority, 'native_sha256': asset.sha256, 'native_version': VERSION,
        'project_id': project_id, 'task_id': task_id, 'model_turns': 0}, indent=2) + '\n')
    return KernelTrial(root, workspace, database, authority, asset, parent, project_id, task_id, broker_limits)


async def wait_output(worker, handle, marker, *, timeout=10):
    """Wait for an actual native stdout event on this original job; never infer readiness from time."""
    async with asyncio.timeout(timeout):
        while True:
            worker._changed.clear()
            state = worker._commands[handle.job_id]
            if marker in state.stdout:
                return
            if state.task is not None and state.task.done():
                raise RuntimeError('Command ended before its required readiness output')
            await worker._changed.wait()


def pin_peer(worker):
    """Pin the recorded host namespace init for observation, verifying its original process identity."""
    from backend.runtime.peer_process import _pidfd, start_ticks

    row = worker.peers.inspect(worker.peer_id)
    fd = _pidfd(row['init_pid'])
    try:
        if start_ticks(row['init_pid']) != row['start_ticks']:
            raise RuntimeError('Original command peer identity changed before observation')
        return fd
    except BaseException:
        os.close(fd)
        raise


async def wait_closed(fd, *, timeout=5):
    """Observe termination through an already-pinned pidfd, without signaling a numeric PID."""
    poller = select.poll()
    poller.register(fd, select.POLLIN | select.POLLHUP)
    if not await asyncio.to_thread(poller.poll, int(timeout * 1000)):
        raise TimeoutError('Original command namespace has not terminated')


async def wait_empty(domain_path, *, timeout=5):
    """Observe the entire original cgroup draining; namespace-init death alone is not this barrier."""
    async with asyncio.timeout(timeout):
        while 'populated 0' not in (domain_path / 'cgroup.events').read_text().splitlines():
            await asyncio.sleep(.01)


def arguments(parser):
    """Require explicit command binary and delegated cgroup without loading a subscription file."""
    parser.add_argument('--codex-binary', type=Path, required=True)
    parser.add_argument('--cgroup-parent', type=Path, required=True)
    return parser.parse_args()
